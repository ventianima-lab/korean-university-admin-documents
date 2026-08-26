#!/usr/bin/env python3
"""Render DOCX to PDF and page PNGs with LibreOffice plus Poppler or PyMuPDF."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_program(explicit: str | None, candidates: list[str]) -> str | None:
    if explicit:
        return explicit
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def render_pdf(pdf: Path, output_dir: Path, dpi: int, pdftoppm: str | None) -> list[Path]:
    if pdftoppm:
        prefix = output_dir / "page"
        subprocess.run([pdftoppm, "-png", "-r", str(dpi), str(pdf), str(prefix)], check=True)
        return sorted(output_dir.glob("page-*.png"))
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install Poppler (pdftoppm) or PyMuPDF to render page images") from exc
    scale = dpi / 72
    document = fitz.open(pdf)
    images = []
    for index, page in enumerate(document, 1):
        destination = output_dir / f"page-{index:03d}.png"
        page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(destination)
        images.append(destination)
    return images


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--libreoffice")
    parser.add_argument("--pdftoppm")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    document = args.document.resolve()
    output_dir = args.output_dir.resolve()
    if not document.is_file():
        parser.error(f"document not found: {document}")
    if args.dpi < 72 or args.dpi > 600:
        parser.error("--dpi must be between 72 and 600")
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        parser.error(f"output directory is not empty: {output_dir}; pass --force")
    output_dir.mkdir(parents=True, exist_ok=True)

    soffice = find_program(args.libreoffice, ["soffice", "libreoffice"])
    if not soffice:
        raise RuntimeError("LibreOffice executable not found; pass --libreoffice")
    pdftoppm = find_program(args.pdftoppm, ["pdftoppm"])

    with tempfile.TemporaryDirectory(prefix="docx-render-") as temporary:
        temp_dir = Path(temporary)
        subprocess.run([
            soffice, "--headless", "--convert-to", "pdf", "--outdir", str(temp_dir), str(document)
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        generated_pdf = temp_dir / f"{document.stem}.pdf"
        if not generated_pdf.is_file():
            raise RuntimeError("LibreOffice did not produce the expected PDF")
        final_pdf = output_dir / f"{document.stem}.pdf"
        shutil.copy2(generated_pdf, final_pdf)
        images = render_pdf(final_pdf, output_dir, args.dpi, pdftoppm)

    if not images:
        raise RuntimeError("no page images were produced")
    print(f"PDF={final_pdf}")
    print(f"PAGES={len(images)}")
    for image in images:
        print(f"PAGE_IMAGE={image}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
