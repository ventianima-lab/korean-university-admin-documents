#!/usr/bin/env python3
"""Deterministically turn document photographs into scan-style images and PDF."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import img2pdf
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


register_heif_opener()


def order_quad(points: np.ndarray) -> np.ndarray:
    pts = points.reshape(4, 2).astype(np.float32)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).ravel()
    return np.array([
        pts[np.argmin(sums)],
        pts[np.argmin(diffs)],
        pts[np.argmax(sums)],
        pts[np.argmax(diffs)],
    ], dtype=np.float32)


def angle_cosine(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ab = a - b
    cb = c - b
    denom = max(float(np.linalg.norm(ab) * np.linalg.norm(cb)), 1e-6)
    return abs(float(np.dot(ab, cb)) / denom)


def find_document_quad(image: np.ndarray) -> tuple[np.ndarray | None, float]:
    height, width = image.shape[:2]
    scale = min(1.0, 1800.0 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    median = float(np.median(gray))
    lower = int(max(0, 0.55 * median))
    upper = int(min(255, 1.45 * median + 20))
    edges = cv2.Canny(gray, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

    _, bright = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel, iterations=3)

    contours = []
    for mask in (edges, bright):
        found, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours.extend(found)

    image_area = float(small.shape[0] * small.shape[1])
    best = None
    best_score = 0.0

    # Prefer the outer bright sheet. Document photos often contain a printed
    # rectangular border that is easier to detect than the actual paper edge.
    # Considering the largest external bright region first prevents cropping
    # away stamps or notes outside that printed border.
    external, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(external, key=cv2.contourArea, reverse=True)[:5]:
        area = float(cv2.contourArea(contour))
        if area < image_area * 0.40:
            continue
        perimeter = cv2.arcLength(contour, True)
        candidates = []
        for epsilon in (0.015, 0.025, 0.04, 0.06):
            approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                candidates.append(order_quad(approx))
        if not candidates:
            rect = cv2.minAreaRect(contour)
            candidates.append(order_quad(cv2.boxPoints(rect)))
        for quad in candidates:
            polygon_area = float(abs(cv2.contourArea(quad.astype(np.float32))))
            if polygon_area < image_area * 0.42:
                continue
            # Area dominates the score so an inner form border cannot beat the sheet.
            score = min(0.99, polygon_area / image_area)
            if score > best_score:
                best = quad / scale
                best_score = score

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
        area = float(cv2.contourArea(contour))
        if area < image_area * 0.22 or area > image_area * 0.995:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        quad = order_quad(approx)
        angles = [
            angle_cosine(quad[(i - 1) % 4], quad[i], quad[(i + 1) % 4])
            for i in range(4)
        ]
        rectangularity = max(0.0, 1.0 - max(angles))
        score = (area / image_area) * (0.45 + 0.35 * rectangularity)
        if score > best_score:
            best = quad / scale
            best_score = score
    return best, best_score


def warp_document(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = order_quad(quad)
    width = int(round(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl))))
    height = int(round(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl))))
    width = max(width, 400)
    height = max(height, 400)
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), destination)
    warped = cv2.warpPerspective(
        image, matrix, (width, height), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    border = max(2, int(round(min(width, height) * 0.003)))
    if width > border * 4 and height > border * 4:
        warped = warped[border:-border, border:-border]
    return warped


def normalize_illumination(image: np.ndarray, mode: str) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    light, a, b = cv2.split(lab)
    sigma = max(28.0, min(image.shape[:2]) / 18.0)
    background = cv2.GaussianBlur(light, (0, 0), sigmaX=sigma, sigmaY=sigma)
    flattened = cv2.divide(light, np.maximum(background, 1), scale=238)

    # Blend most of the photographed paper texture back in. A fully flattened
    # luminance channel makes certificates look synthetic and exaggerates grain.
    normalized = cv2.addWeighted(light, 0.62, flattened, 0.38, 0)
    p_low, p_high = np.percentile(normalized, (0.5, 99.2))
    if p_high - p_low > 10:
        normalized = np.clip((normalized.astype(np.float32) - p_low) * 239.0 / (p_high - p_low) + 10, 0, 255).astype(np.uint8)

    if mode == "grayscale":
        result = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
    else:
        # Slightly reduce color casts while retaining stamps, signatures, and highlighting.
        a = cv2.addWeighted(a, 0.86, np.full_like(a, 128), 0.14, 0)
        b = cv2.addWeighted(b, 0.86, np.full_like(b, 128), 0.14, 0)
        result = cv2.cvtColor(cv2.merge((normalized, a, b)), cv2.COLOR_LAB2BGR)

    blurred = cv2.GaussianBlur(result, (0, 0), 0.65)
    return cv2.addWeighted(result, 1.04, blurred, -0.04, 0)


def load_image(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def save_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    a4 = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
    layout = img2pdf.get_layout_fun(pagesize=a4, fit=img2pdf.FitMode.into)
    pdf_path.write_bytes(img2pdf.convert([str(path) for path in image_paths], layout_fun=layout))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--mode", choices=("color", "grayscale"), default="color")
    parser.add_argument("--auto-crop", action="store_true")
    parser.add_argument("--trim-percent", type=float, default=0.0)
    parser.add_argument("--trim-x-percent", type=float, default=0.0)
    parser.add_argument("--trim-y-percent", type=float, default=0.0)
    parser.add_argument("--jpeg-quality", type=int, default=94)
    parser.add_argument(
        "--rotate", action="append", default=[], metavar="INDEX:DEGREES",
        help="rotate a 1-based input page clockwise by 90, 180, or 270 degrees",
    )
    return parser.parse_args()


def parse_rotations(values: list[str]) -> dict[int, int]:
    rotations: dict[int, int] = {}
    for value in values:
        try:
            index_text, degree_text = value.split(":", 1)
            index, degrees = int(index_text), int(degree_text)
        except ValueError as exc:
            raise SystemExit(f"Invalid --rotate value: {value}; expected INDEX:DEGREES") from exc
        if index < 1 or degrees not in (90, 180, 270):
            raise SystemExit(f"Invalid --rotate value: {value}; degrees must be 90, 180, or 270")
        rotations[index] = degrees
    return rotations


def main() -> int:
    args = parse_args()
    if not 80 <= args.jpeg_quality <= 100:
        raise SystemExit("--jpeg-quality must be between 80 and 100")
    for option, value in (
        ("--trim-percent", args.trim_percent),
        ("--trim-x-percent", args.trim_x_percent),
        ("--trim-y-percent", args.trim_y_percent),
    ):
        if not 0 <= value <= 5:
            raise SystemExit(f"{option} must be between 0 and 5")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rotations = parse_rotations(args.rotate)
    outputs: list[Path] = []
    report = []

    for index, input_path in enumerate(args.inputs, start=1):
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        image = load_image(input_path)
        degrees = rotations.get(index, 0)
        trim_x_percent = args.trim_x_percent or args.trim_percent
        trim_y_percent = args.trim_y_percent or args.trim_percent
        trim_x = int(round(image.shape[1] * trim_x_percent / 100.0))
        trim_y = int(round(image.shape[0] * trim_y_percent / 100.0))
        x_slice = slice(trim_x, -trim_x if trim_x else None)
        y_slice = slice(trim_y, -trim_y if trim_y else None)
        image = image[y_slice, x_slice]
        quad, confidence = find_document_quad(image) if args.auto_crop else (None, 0.0)
        cropped = warp_document(image, quad) if quad is not None else image
        cleaned = normalize_illumination(cropped, args.mode)
        # Apply the user-requested content orientation after geometry correction.
        # This avoids automatic corner ordering canceling a 180-degree correction.
        if degrees == 90:
            cleaned = cv2.rotate(cleaned, cv2.ROTATE_90_CLOCKWISE)
        elif degrees == 180:
            cleaned = cv2.rotate(cleaned, cv2.ROTATE_180)
        elif degrees == 270:
            cleaned = cv2.rotate(cleaned, cv2.ROTATE_90_COUNTERCLOCKWISE)
        output_path = args.output_dir / f"{index:02d}_{input_path.stem}_스캔.jpg"
        ok, encoded = cv2.imencode(".jpg", cleaned, [cv2.IMWRITE_JPEG_QUALITY, args.jpeg_quality])
        if not ok:
            raise OSError(f"Failed to write {output_path}")
        output_path.write_bytes(encoded.tobytes())
        outputs.append(output_path)
        report.append({
            "input": str(input_path),
            "output": str(output_path),
            "source_size": [int(image.shape[1]), int(image.shape[0])],
            "output_size": [int(cleaned.shape[1]), int(cleaned.shape[0])],
            "auto_crop": quad is not None,
            "detection_score": round(float(confidence), 4),
            "rotation_degrees": degrees,
        })

    if args.pdf:
        save_pdf(outputs, args.pdf)
    print(json.dumps({"pages": report, "pdf": str(args.pdf) if args.pdf else None}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

