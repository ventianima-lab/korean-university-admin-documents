---
name: document-scan-cleaner
description: Convert HEIC, JPEG, PNG, or TIFF document photographs into clean scan-style page images and an optional combined PDF while preserving original text, signatures, stamps, and handwriting. Use for requests mentioning vFlat-like scanning, document-photo cleanup, perspective correction, shadow or uneven-light removal, deskewing, page cropping, or combining photographed pages into a PDF.
---

# Document Scan Cleaner

Use deterministic image processing. Do not use generative image editing on text-bearing documents unless the user explicitly accepts possible content changes.

## Workflow

1. Preserve all source files unchanged.
2. Inspect page order and orientation.
3. Run `scripts/clean_document_scans.py` with explicit inputs and an output directory. Keep geometry correction disabled unless the paper boundary is unambiguous.
4. Prefer color output when pages may contain signatures, stamps, highlighting, or photographs.
5. Review every output image and render the combined PDF for visual verification.
6. If automatic page detection crops content, rerun the affected page without `--auto-crop`.
7. Report the output paths and any page that could not be confidently detected.

## Hybrid geometry mode

Use `scripts/hybrid_geometry_transfer.py` when an ImageGen edit provides excellent page geometry but changes small text, numbers, or seals. Treat every generated image strictly as a disposable geometry reference. Match reference and source features, estimate a robust homography, and render only original source pixels onto a white A4 canvas.

If the generated reference rearranges repeated text or form cells, reject geometry transfer even when the numerical inlier count is high. Fall back to the original rectangular camera frame, use the reference only to review orientation/completeness, trim desk edges conservatively, and normalize illumination. A visually plausible homography is mandatory.

```powershell
python scripts/hybrid_geometry_transfer.py --output-dir <dir> --pdf <combined.pdf> --source <original1> --reference <generated1> [--source <original2> --reference <generated2> ...]
```

- Add `--rotate INDEX:180` for a source photographed upside down.
- Reject a page when geometric matching reports fewer than 50 inliers or an inlier ratio below 0.35.
- Never copy generated text, seals, stamps, or pixels into the final image.

## Command

```powershell
python scripts/clean_document_scans.py --output-dir <dir> --pdf <combined.pdf> <input1> <input2> ...
```

Options:

- `--auto-crop`: opt in to perspective correction only when the outer paper edge is clear. It is disabled by default because printed form borders can be mistaken for paper edges.
- `--mode color`: preserve colored marks; this is the default.
- `--mode grayscale`: create neutral grayscale pages.
- `--jpeg-quality`: set JPEG quality from 80 to 100; default 94.
- `--rotate INDEX:DEGREES`: rotate one input page clockwise by 90, 180, or 270 degrees; repeat as needed.
- `--trim-percent`: remove only a small uniform camera-edge border; default 0.
- `--trim-x-percent`, `--trim-y-percent`: trim horizontal and vertical camera edges independently when content is close to only one pair of edges.

Install `scripts/requirements.txt` into the Python environment when imports are missing.

## Validation

- Confirm output count equals input count.
- Confirm page order follows the input argument order.
- Confirm no text, signatures, stamps, or page edges are clipped.
- Confirm shadows and illumination gradients are reduced without erasing pale marks.
- In hybrid mode, confirm every output is composed exclusively from source pixels plus a plain white canvas.
- Render and inspect the final PDF before delivery.

