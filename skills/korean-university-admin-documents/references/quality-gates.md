# Quality gates

## All formats

- Correct current template and source evidence
- Protected-value comparison passed
- Required labels and fields present
- No unsupported facts inserted
- Source preserved and output path distinct unless overwrite was requested
- Exact final-byte SHA-256 recorded for important deliverables

## Visual gate

Render every final page at readable resolution. Check clipping, overlap, missing glyphs, broken tables, unexpected blank pages, page-break drift, header/footer placement, signature space and print area. Re-render after every layout-sensitive change.

## Application gate

When native application compatibility materially affects delivery, reopen the exact final path in the target application and verify the title/path, page count and key text. Report success only for the exact bytes that passed.

## Delivery status

Report structural, textual, visual and application-openability checks separately. Do not turn a partial pass into a full success claim.
