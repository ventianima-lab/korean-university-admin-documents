# Survey count-and-percentage template gate

When an official or user-selected survey results template shows a count and percentage together, preserve both in every corresponding field, including respondent demographics, totals, each response option and zero-count cells. A count-only entry is incomplete even when the arithmetic is correct or the document opens successfully. The template's placeholder numbers are examples, not evidence of actual responses.

Before editing, map all template count/percentage cells to the current working final and independently recorded counts and denominators. Use the survey responses or other authorized current evidence; for a narrow follow-up formatting correction, preserve existing user-approved counts and independently check available evidence. Distinguish survey totals, per-question valid response counts, subgroup totals, and total columns; do not assume all denominators are equal. Leave unsupported values unresolved instead of inventing them. Follow a specified rounding rule; otherwise use a consistent, documented precision. Independently rounded percentages need not sum to exactly 100%. Preserve user-edited content, blanks, dates, and structural areas outside the requested change.

For HWPX with one `N명(N%)`-shaped value per cell, run `scripts/verify_template_count_percent.py TEMPLATE OUTPUT EXPECTATIONS.json`. The independently prepared JSON lists every such source-template cell and its corresponding output cell, independent count, denominator, evidence, rounding precision, and all applicable mutually exclusive exhaustive groups. Its table indexes are zero-based among `hp:tbl` elements in the named section; cell coordinates are `rowAddr` and `colAddr`:

```json
{
  "template": {"section": "Contents/section0.xml", "table": 0},
  "output": {"section": "Contents/section0.xml", "table": 0},
  "rounding_decimals": 1,
  "fields": [
    {"template": [3, 1], "output": [3, 1], "count": 2, "denominator": 3, "source": "independent response evidence, question 1"},
    {"template": [3, 2], "output": [3, 2], "count": 1, "denominator": 3, "source": "independent response evidence, question 1"}
  ],
  "groups": [{"name": "question 1", "output_cells": [[3, 1], [3, 2]], "denominator": 3}]
}
```

The helper fails when any matching template field lacks a mapping, a count unit or percentage is absent, the count or rounded percentage is wrong, source evidence is missing, or listed group counts/denominators do not reconcile. It rejects unsupported count/percentage cell shapes rather than silently ignoring them. It does not establish that the selected table, survey transcription, evidence, grouping or denominator is correct, and it cannot inspect image-only fields or page layout. Confirm those independently, inspect every changed cell in the native page render for clipping or split values, and use an equivalent explicit all-field gate for other formats or cell shapes. Any unresolved field, unsupported shape, invalid count/denominator, or unverified layout blocks a completion claim.
