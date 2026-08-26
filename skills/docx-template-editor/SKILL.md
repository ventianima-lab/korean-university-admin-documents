---
name: docx-template-editor
description: Fill, revise, compare, and verify DOCX or Microsoft Word templates while preserving styles, sections, headers, footers, tables, numbering, fields, comments, tracked changes, content controls, and page layout. Use for Word forms and university administrative documents.
---

# DOCX template editor

Treat a supplied DOCX as the design authority. Preserve the source and edit a copy unless overwrite is explicitly requested.

## Workflow

1. Inspect the package, document text, sections, styles, numbering, relationships, headers, footers, tables, images, fields, comments, tracked changes and content controls.
2. Snapshot protected facts and template structure.
3. Make minimal local edits. Prefer run-level replacement that preserves surrounding formatting; do not rewrite whole paragraphs for a small correction.
4. Preserve real Word styles, numbering definitions, section breaks, table grid widths, cell widths, repeated header rows and merge structure.
5. For forms, preserve content controls and make response areas usable. Do not replace a supplied form with a generic table.
6. For review work, anchor comments at the relevant text and retain tracked-change structure. Do not flatten review markup unless requested.
7. Run `scripts/validate_docx.py` on the exact output.
8. Render the exact output with `scripts/render_docx.py`, inspect every page image, fix defects and repeat.
9. Reopen in Microsoft Word when exact Word compatibility materially affects delivery and Word is available.

## Verification

- No missing package relationships or malformed XML
- Expected text and fields present
- Page count and orientation as expected
- No clipping, overlap, broken tables, missing fonts or unexpected blank pages
- Headers, footers, page numbers, captions and cross-references remain correct
- Comments, tracked changes, metadata, restrictions and content controls match the requested delivery state

Read [references/word-forms-and-review.md](references/word-forms-and-review.md) for forms, tracked changes and privacy.
