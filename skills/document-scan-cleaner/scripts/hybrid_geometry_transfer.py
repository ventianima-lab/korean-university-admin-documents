#!/usr/bin/env python3
"""Transfer ImageGen page geometry while rendering only original document pixels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import img2pdf
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


register_heif_opener()
A4_PIXELS = (2480, 3508)


def load_source(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def load_reference(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode reference: {path}")
    return image


def parse_rotations(values: list[str]) -> dict[int, int]:
    result: dict[int, int] = {}
    for value in values:
        try:
            index_text, degrees_text = value.split(":", 1)
            index, degrees = int(index_text), int(degrees_text)
        except ValueError as exc:
            raise SystemExit(f"Invalid --rotate value {value}; expected INDEX:DEGREES") from exc
        if index < 1 or degrees not in (90, 180, 270):
            raise SystemExit(f"Invalid --rotate value {value}")
        result[index] = degrees
    return result


def rotate(image: np.ndarray, degrees: int) -> np.ndarray:
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def downscale(image: np.ndarray, maximum: int = 1600) -> tuple[np.ndarray, float]:
    scale = min(1.0, maximum / max(image.shape[:2]))
    if scale == 1.0:
        return image, scale
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), scale


def estimate_homography(source: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, dict]:
    source_small, source_scale = downscale(source)
    reference_small, reference_scale = downscale(reference)
    sift = cv2.SIFT_create(nfeatures=12000, contrastThreshold=0.018)
    source_keys, source_desc = sift.detectAndCompute(cv2.cvtColor(source_small, cv2.COLOR_BGR2GRAY), None)
    reference_keys, reference_desc = sift.detectAndCompute(cv2.cvtColor(reference_small, cv2.COLOR_BGR2GRAY), None)
    if source_desc is None or reference_desc is None:
        raise ValueError("Not enough features for geometry matching")

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    forward = matcher.knnMatch(source_desc, reference_desc, k=2)
    reverse = matcher.knnMatch(reference_desc, source_desc, k=2)
    forward_good = [first for first, second in forward if first.distance < 0.73 * second.distance]
    reverse_good = {
        first.queryIdx: first.trainIdx
        for first, second in reverse
        if first.distance < 0.73 * second.distance
    }
    # Repeated Hangul and table cells can produce a very confident but incorrect
    # one-way match.  Mutual ratio matches greatly reduce that failure mode.
    good = [match for match in forward_good if reverse_good.get(match.trainIdx) == match.queryIdx]
    if len(good) < 50:
        raise ValueError(f"Only {len(good)} reliable feature matches")
    source_points = np.float32([source_keys[m.queryIdx].pt for m in good])
    reference_points = np.float32([reference_keys[m.trainIdx].pt for m in good])
    small_h, inlier_mask = cv2.findHomography(
        source_points, reference_points, cv2.RANSAC, 4.0,
        maxIters=15000, confidence=0.999,
    )
    if small_h is None or inlier_mask is None:
        raise ValueError("Homography estimation failed")
    inliers = int(inlier_mask.sum())
    ratio = float(inlier_mask.mean())
    if inliers < 50 or ratio < 0.35:
        raise ValueError(f"Weak geometry: {inliers} inliers, ratio {ratio:.3f}")

    source_matrix = np.diag([source_scale, source_scale, 1.0])
    reference_matrix = np.diag([reference_scale, reference_scale, 1.0])
    full_h = np.linalg.inv(reference_matrix) @ small_h @ source_matrix
    stats = {"matches": len(good), "inliers": inliers, "inlier_ratio": round(ratio, 4)}
    return full_h, stats


def paper_mask(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    light = lab[:, :, 0]
    _, binary = cv2.threshold(light, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros(light.shape, dtype=np.uint8)
    if not contours:
        mask[:] = 255
        return mask
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < image.shape[0] * image.shape[1] * 0.45:
        mask[:] = 255
        return mask
    hull = cv2.convexHull(contour)
    cv2.fillConvexPoly(mask, hull, 255)
    mask = cv2.dilate(mask, np.ones((17, 17), np.uint8), iterations=1)
    return mask


def safe_warp(source: np.ndarray, reference: np.ndarray, homography: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Warp into the reference coordinate system, never into the source-corner hull.

    The generated reference is used only as an axis-aligned coordinate frame.  A
    fixed reference canvas prevents the photographed trapezoid from becoming the
    output page shape.  References are generated with the complete page present,
    so pixels outside this frame are camera/desk context rather than page content.
    """
    ref_h, ref_w = reference.shape[:2]
    width = ref_w
    height = ref_h
    adjusted = homography
    warped = cv2.warpPerspective(
        source, adjusted, (width, height), flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
    )
    mask = cv2.warpPerspective(
        paper_mask(source), adjusted, (width, height), flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )
    return warped, mask


def enhance_and_fit(warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
    composite = np.full_like(warped, 255)
    # Remove a narrow edge ring from the photographed sheet.  It contains desk
    # shadows and dark paper edges, not document content.
    inner_mask = cv2.erode(mask, np.ones((13, 13), np.uint8), iterations=1)
    if cv2.countNonZero(inner_mask) == 0:
        raise ValueError("Paper mask is empty after geometry transfer")
    composite[inner_mask > 0] = warped[inner_mask > 0]
    page = composite

    lab = cv2.cvtColor(page, cv2.COLOR_BGR2LAB)
    light, a, b = cv2.split(lab)
    sigma = max(40.0, min(page.shape[:2]) / 16.0)
    background = cv2.GaussianBlur(light, (0, 0), sigmaX=sigma, sigmaY=sigma)
    flat = cv2.divide(light, np.maximum(background, 1), scale=255)
    light = cv2.addWeighted(light, 0.08, flat, 0.92, 0)
    valid_light = light[inner_mask > 0]
    low, high = np.percentile(valid_light, (0.25, 98.0))
    light = np.clip((light.astype(np.float32) - low) * 252.0 / max(high - low, 1) + 3, 0, 255).astype(np.uint8)
    # Keep original chroma for colored seals but neutralize weak paper color casts.
    chroma = cv2.max(cv2.absdiff(a, 128), cv2.absdiff(b, 128))
    preserve = np.clip((chroma.astype(np.float32) - 5.0) / 24.0, 0.0, 1.0)
    a = np.clip(128 + (a.astype(np.float32) - 128) * (0.25 + 0.75 * preserve), 0, 255).astype(np.uint8)
    b = np.clip(128 + (b.astype(np.float32) - 128) * (0.25 + 0.75 * preserve), 0, 255).astype(np.uint8)
    page = cv2.cvtColor(cv2.merge((light, a, b)), cv2.COLOR_LAB2BGR)
    # Snap only locally-normalized, near-neutral paper pixels to white.  Colored
    # seals/signatures and every darker source mark remain sourced from the photo.
    neutral_paper = (light >= 238) & (chroma <= 9)
    page[neutral_paper] = 255
    page[inner_mask == 0] = 255

    canvas_w, canvas_h = A4_PIXELS
    margin = 50
    ratio = min((canvas_w - margin * 2) / page.shape[1], (canvas_h - margin * 2) / page.shape[0])
    resized = cv2.resize(page, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_LANCZOS4)
    canvas = np.full((canvas_h, canvas_w, 3), 255, dtype=np.uint8)
    left = (canvas_w - resized.shape[1]) // 2
    top = (canvas_h - resized.shape[0]) // 2
    canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
    return canvas


def save_pdf(images: list[Path], pdf_path: Path) -> None:
    a4 = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
    layout = img2pdf.get_layout_fun(pagesize=a4, fit=img2pdf.FitMode.into)
    pdf_path.write_bytes(img2pdf.convert([str(path) for path in images], layout_fun=layout))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, type=Path)
    parser.add_argument("--reference", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--rotate", action="append", default=[])
    parser.add_argument("--output-rotate", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if len(args.source) != len(args.reference):
        raise SystemExit("--source and --reference counts must match")
    rotations = parse_rotations(args.rotate)
    output_rotations = parse_rotations(args.output_rotate)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    report = []
    for index, (source_path, reference_path) in enumerate(zip(args.source, args.reference), start=1):
        source = rotate(load_source(source_path), rotations.get(index, 0))
        reference = load_reference(reference_path)
        homography, stats = estimate_homography(source, reference)
        warped, mask = safe_warp(source, reference, homography)
        final = enhance_and_fit(warped, mask)
        final = rotate(final, output_rotations.get(index, 0))
        output = args.output_dir / f"{index:02d}_{source_path.stem}_하이브리드스캔.jpg"
        ok, encoded = cv2.imencode(".jpg", final, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise OSError(f"Failed to encode {output}")
        output.write_bytes(encoded.tobytes())
        outputs.append(output)
        report.append({"page": index, "source": str(source_path), "reference": str(reference_path), "output": str(output), **stats})
    if args.pdf:
        args.pdf.parent.mkdir(parents=True, exist_ok=True)
        save_pdf(outputs, args.pdf)
    print(json.dumps({"pages": report, "pdf": str(args.pdf) if args.pdf else None}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

