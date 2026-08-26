---
name: spreadsheet-form-preservation
description: Fill, repair, compare, and verify XLSX spreadsheet forms while preserving formulas, merged cells, styles, row heights, column widths, hidden sheets, named ranges, validations, print areas, page settings, printer parts, charts, images, and workbook relationships.
---

# Spreadsheet form preservation

Treat the supplied workbook as the structural and visual authority. Work on a copy unless overwrite is explicitly requested.

## Workflow

1. Compare target cells with the reference and identify the smallest required edit set.
2. Snapshot formulas, styles, merges, row heights, column widths, sheet order and visibility, defined names, validations, print areas, page setup, printer settings, charts and relationships.
3. Change only approved cells, formulas or labels. Do not rebuild the workbook from a generic export when the source structure matters.
4. Preserve formulas as formulas and distinguish blank, zero, empty string and not-applicable values.
5. Run `scripts/inspect_xlsx_package.py` on the source and result, then compare structural fingerprints.
6. Recalculate in a compatible spreadsheet application when formulas or cached results changed.
7. Render or print every relevant sheet and inspect pagination, clipping, repeated titles and print area.

## Hard failures

- Hidden-sheet state or sheet order changed unexpectedly
- Formula or named-range references changed outside the approved edit set
- Merges, widths, heights, print area, page setup or printer parts drifted
- A filled form was renamed or treated as a blank template
- A structurally sensitive workbook was round-tripped through a lossy exporter
