---
name: spreadsheet-form-preservation
description: Fill, repair, compare, and verify XLSX spreadsheet forms while preserving formulas, merged cells, styles, row heights, column widths, hidden sheets, named ranges, validations, print areas, page settings, printer parts, charts, images, and workbook relationships.
---

# Spreadsheet form preservation

Treat the supplied workbook as the structural and visual authority. Work on a copy unless overwrite is explicitly requested.

## Attachment access and compatibility

- For an encrypted attachment, inspect its notice and filename for password guidance first. If an explicitly supplied Korean password fails, confirm that the input reached the reader as valid Unicode. A Korean/English keyboard-state mismatch may be checked once by converting those exact Hangul keystrokes to their two-set Korean keyboard Latin equivalents. This is a bounded input correction, not permission to guess unrelated passwords. Verify successful decryption and exact-file application opening before declaring recovery. Keep password values out of scripts, command history, logs, reports, and previews; preserve required output encryption and verify it by reopening.
- A spreadsheet written by Hancom HCell can contain `mc:AlternateContent` wrappers around fonts or cell formats. An out-of-range style error does not prove the source styles are missing. On a compatibility copy, select explicit `mc:Fallback` children in place without changing their order or style indices, then compare headers, values, merges, and styles. Do not replace unavailable styles with defaults. Keep the original intact and verify the finished file in the target application.
- When submitting one department from a multi-institution form, retain the current official fields, supplied identifiers, row order, and not-applicable markers. Remove unrelated records from the submission copy, including unused shared-string data. Obtain each person's applicable periods from the current roster rather than applying one student's periods to everyone.

## Workflow

1. Compare target cells with the reference and identify the smallest required edit set.
   Record the intended row identities and any explicit exclusions before filling. Identify records by stable identifiers plus section or another necessary discriminator, rather than by count alone. A request to exclude a record removes its row; do not retain it with blank dates or restore it from a roster on regeneration. Verify that the final included identity set exactly matches the requested set and that excluded identities are absent, including after a user correction.
   When a partially filled contact roster has a name resembling a person in another record, do not silently treat the names as the same person. Confirm the identity correction with the user before transferring that person's employer, role, or phone. After confirmation, verify the complete name-to-employer-to-role-to-phone association and remove the superseded spelling from the delivered workbook, including unused shared strings when they contain only that corrected identity. A business landline is not evidence for a mobile-phone field; leave the field blank and identify the missing value separately when no mobile number is supported. Keep unnamed spare rows outside the fill scope unless the user requests new people.
2. Snapshot formulas, styles, merges, row heights, column widths, sheet order and visibility, defined names, validations, print areas, page setup, printer settings, charts and relationships.
   Before replacing a working output, recheck its live path and hash. If it moved or changed after verification, inspect the current saved workbook and preserve later user edits; never regenerate it from the earlier snapshot merely to pass a stale comparison.
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
