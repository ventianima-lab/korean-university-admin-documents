# Survey count-and-percentage template gate

## Survey coverage and population preflight

Before transcribing or aggregating a supplied survey, build a source-to-survey coverage map independently of the candidate report. Record the source scan identity/hash and page or questionnaire-unit locations, the actual collection/completion date and its source, the instrument's target events/sessions (single or combined), and the latest scoped user instruction or other coverage authority. A printed last-session date alone does not establish that only that session was evaluated: collection timing and target coverage are separate facts. An explicit user confirmation of combined coverage governs that scope while the actual printed date remains unchanged. Preserve original scans and marked answers; do not rewrite evidence to make dates match the report's coverage.

Keep these quantities separate in the map and every authoring invocation:

- Returned questionnaire units and source pages: a multi-page scan is not automatically several questionnaires, and several copies are not automatically distinct returns. Record supported duplicate/missing-page dispositions without altering originals.
- Unique respondents: use the actual returned instruments and authorized respondent evidence or explicit user count. A combined survey remains one response set; do not multiply respondents by the number of covered sessions or create a second set of answers for an earlier session.
- Person-sessions: this is a separate attendance/exposure measure only when independently supported and requested. It is not a survey respondent denominator, and survey coverage alone does not prove attendance at every covered event.
- Per-item valid respondent counts, option counts and item-answer counts: derive them from the actual marked answers and question type. Unanswered items and multiple-choice selections can make these totals differ. A sum of item answers is not a person count, and a combined overall response cannot be split into session-specific ratings without source support.

Bind the map to the exact target report headings, row labels, event/session coverage, displayed date roles, denominators, repeated totals and authorized output-file roles/counts before writing. Pass combined scope explicitly to the authoring invocation rather than letting the printed date or an event-by-event roster loop select the report scope. Do not fabricate a missing first-session survey, duplicate a shared response set into separate session rows, or manufacture extra questionnaire/report files to match the event count. Keep an actual source-backed per-session instrument separate when one exists; combined coverage is not a universal default.

At completion, inspect the exact saved report's complete headings and rows against that map, including each row's scope label, counts, denominator, date meaning and source-answer associations. Reconcile the actual active output files and attachment lists to the authorized survey/report grouping; a renamed heading or correct aggregate percentage alone cannot clear leftover session-only labels, duplicated response sets, invented missing-survey requirements or extra output files. Check source hashes remain unchanged and preserve protected answer marks. Use the existing exact-field checks for supported saved text locations and the arithmetic gate below for count/percentage cells, then inspect the current page render for readable, consistent labels and counts. Those helpers cannot determine survey coverage, distinct respondents or source truth; a missing coverage authority, unresolved denominator, unsupported split or unchecked final report prevents a verified completion claim. Honor an explicit post-save review waiver and state the unperformed checks accurately.

## Template counts and percentages

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

When the user or authoritative instructions explicitly require displayed group totals to equal 100%, list that complete response group with `"rounding": "largest_remainder"` and the selected precision. The helper then checks the 100% total and allocation by largest fractional remainder; tied remainders may receive different last digits. Do not silently choose balanced rounding when individual rounding or another method is required. Counts and denominators remain unchanged.

The helper fails when any matching template field lacks a mapping, a count unit or percentage is absent, the count or percentage violates the selected rounding method, source evidence is missing, or listed group counts/denominators do not reconcile. It rejects unsupported count/percentage cell shapes rather than silently ignoring them. It does not establish that the selected table, survey transcription, evidence, grouping or denominator is correct, and it cannot inspect image-only fields or page layout. Confirm those independently, inspect every changed cell in the native page render for clipping or split values, and use an equivalent explicit all-field gate for other formats or cell shapes. Any unresolved field, unsupported shape, invalid count/denominator, or unverified layout blocks a completion claim.
