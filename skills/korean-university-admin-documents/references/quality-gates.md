# Quality gates

## All formats

- Correct current template and source evidence
- Protected-value comparison passed
- Required labels and fields present
- No unsupported facts inserted
- Source preserved and output path distinct unless overwrite was requested
- Exact final-byte SHA-256 recorded for important deliverables
- Every target field checked against the user's requested state after saving; correct totals or parsing do not excuse inconsistent rows, wrong checkbox glyphs, unreadable identifiers, unsolicited annotations, or wrong photo/date associations
- Editable deliverables retained and extra PDFs limited to requested or confirmed printing/submission needs; verification-only PDFs stay outside active records

## Visual gate

Render every final page at readable resolution. Check clipping, overlap, missing glyphs, broken tables, unexpected blank pages, page-break drift, header/footer placement, signature space and print area. Re-render after every layout-sensitive change.

## Images intended for printing

Images intended for printing must be at least 300dpi at their final physical print size; honor any higher requested resolution. A4 at 300dpi is approximately 2480 x 3508 pixels, subject only to normal whole-pixel rounding. Verify both axes from the saved pixel dimensions and print size, and check saved DPI metadata. A prompt requesting 300dpi or changing metadata alone does not pass this gate. For images embedded in documents or PDFs, calculate resolution at the actual placed dimensions. Preserve the accepted original design when the user requests only a DPI increase; disclose resampling separately from native detail recovery. Do not report actual printer quality as tested without a physical output check.

## Application gate

When native application compatibility materially affects delivery, reopen the exact final path in the target application and verify the title/path, page count and key text. Report success only for the exact bytes that passed.

## Delivery status

Report structural, textual, visual and application-openability checks separately. Do not turn a partial pass into a full success claim.
