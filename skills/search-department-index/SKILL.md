---
name: search-department-index
description: Search configured operational and document-content indexes for university department records, verify live sources, and expand to off-index local folders when recurring records are missing.
---

# Search Department Index

Find likely records from the current operational index and historical content/OCR indexes, then verify the live path before answering.

## Workspace configuration

Use the configured records root and control/index root from the workspace policy. The public helper defaults to the current directory; pass `--control-root` explicitly when it differs. It reads `01_색인결과/운영색인/current/current_inventory.csv` and optional document-content indexes. Configure local paths and department taxonomies in workspace instructions, not in this public skill.

## Workflow

0. Establish department scope from the actual task folder and workspace taxonomy. An explicit user scope overrides that inference. A reusable form from another department does not authorize mixing its people or companies into the task. Clarify only when the folder and available context do not resolve scope.

1. Read the workspace README, operating rules and latest index report before a broad search.
2. Convert the request into 2–5 distinctive keywords. Remove filler such as `자료`, `파일`, `찾아줘`, and `관련` unless it is meaningful.
3. Run:

```powershell
python "<skill-dir>/scripts/search_index.py" --control-root "<control-root>" --query "검색어1 검색어2" --limit 20 --json
```

4. Add filters when known: `--department`, `--year`, `--work-type`, or `--extension`. Use `--match any` only when synonyms or alternative names should be OR-matched.
5. Rank exact filename/path matches above inferred classifications and content previews. Treat `content_match` as supporting evidence, not proof that the historical path is current; the script resolves a matching SHA256 to the current operational path when possible.
6. Confirm that each returned `full_path` exists, but do not treat existence or an empty `review_flags` value as proof that the business folder is correct. For a recurring record series, compare the same document type across adjacent academic years and inspect whether an established dedicated folder exists.
7. For recurring record series, verify the expected business folder against the workspace taxonomy; report apparent mismatches instead of treating the current location as authoritative.
8. For an important candidate, inspect the current file with an open-source parser before asserting document contents. Use Hancom Office, Hwp.exe, HWPFrame.HwpObject, or Hancom COM when conversion, repair, rendering, or final openability verification is required; handle task-scoped prompts with computer-use.
9. If no useful result appears, retry once with fewer or broader keywords and `--match any`, then search current filenames directly with `rg`/PowerShell. State when the index is insufficient instead of guessing.

## Recurring records and searches beyond the index

An index covers its configured records root, not the whole computer. When a recurring record is not found, especially after the user says it exists locally, inspect handover instructions and adjacent-year packets for its actual filename, author and storage clues. Inventory available local data volumes and current or former user-profile Desktop, Downloads and Documents folders before directing the user to an external office. A former profile on another volume can contain the only editable source. Keep cloud-only, inaccessible and unsearched roots explicit; do not silently count them as searched.

For student-authored diaries or reports, verify the actual writing fields and course/credit identity. Attendance registers, diary request forms, timetables and instructions mentioning a diary are leads, not the requested diary. Discover candidates across formats, including images and archive members, before applying editable-document filters; a misleading filename is not content evidence. Read complete candidate bodies and later pages rather than relying on truncated previews or ranked top-N hits. Follow a handover's named-file clue into off-index folders instead of repeating the same index query.

Close the search with an existing verified source path and precise fields, or a scoped account of checked roots, formats and actual access/parser limits. Do not infer nonexistence from one index. Stop broad scans once a matching source has been independently verified; do not move, recreate or copy the user's records during a read-only search.

## Program identity and awarded budgets

When the request identifies a program by the responsible person and activity but omits its official title or award amount, check the owning office's current selection or registration notice and attached roster or allocation table before asking the user. Search the notice system by academic year, program category and owning office. Search the department budget ledger in parallel when available. A generic manual, earlier filled packet or department-wide budget total does not establish the identity, award, or current balance of a particular project. Verify the department, responsible person and project on the same source row. Cite the notice ID and attachment sheet/row or page, and distinguish the amount awarded from actual spending and available balance. If still unresolved, say which source or access is missing.

## Roster completeness and affiliation searches

For a requested list of people and their organizations, establish the department and semester scope from the user's wording and named examples. A timetable or parking register supplies candidates for that scope; one department's register cannot establish a workspace-wide exhaustive list. If a named person falls outside the initial filter, reopen that filter and inspect the relevant department's current register before asking the user for information already in records.

Separate roster membership from organization and legal-representative evidence. Cross-check the current roster against original appointment records, business registrations, and cooperation-agreement reports. Read all relevant sections: previews and ranked top-N results can omit people in later tables. Record each scoped person as organization verified, evidence conflicting, or unresolved after identified searches. Do not treat a short preview or a missing result as proof that a person or organization is absent.

Before handing off a list or generating one document per organization, reconcile every current roster name and every name supplied by the user with the evidence list. Deduplicate organizations separately from people, and keep the organization's representative distinct from its instructor/contact. A newly supplied counterexample must trigger this reconciliation again, including any affected document fields.

A parking-application list or one year's classroom schedule is a partial operational list, not a complete personnel register. Check its inclusion rule before using it to exclude a lecturer. An explicit user correction of department or people overrides an inferred scope; replace that scope rather than unioning departments. Once the user confirms a person list, use it as an allowlist and check both missing and additional people in the answer and generated artifacts. Preserve excluded drafts outside the active deliverable folder and leave original records unchanged.

### Contact fields for external participants

When an appointment list identifies an external participant but omits contact fields, follow the owning department and activity into the appointment request, meeting or payment packet, partner records, and the previous edition of the same event where accessible. Inspect pertinent original attachment rows and later sheets beyond index previews; an index miss, bare appointment list, or name-only match does not close the contact search.

Before filling a form, reconcile each mobile number and email with the requested name, organization and role. A previous application may provide contacts for a same-name person at another organization. Reuse those details only when current records or explicit user confirmation establish that the records refer to the same person. Record the precise source location for each verified field, check the saved values against that mapping, and identify the owning record or office and remaining unverified fields when evidence is insufficient.

## Evidence-role searches

For vendor/travel evidence availability, apply the composite-evidence role map in [procurement-forms.md](../hancom-hwpx-documents/references/procurement-forms.md) before declaring a role absent. Use the limits below as an invocation gate: inspect the complete live candidate, including later pages and embedded scans, and cite each role's file/page/field. Match company, vehicle and effective period; distinguish passenger insurance, vehicle mutual-aid coverage and company bonds. Related date fields do not prove a separate certificate exists. Keep historical availability independent from current-trip suitability. For a read-only request, return the map in chat and leave source records, checklists and prepared packets unchanged; do not create a new inventory file.

## Content limits

- The current operational index follows the workspace refresh schedule and contains metadata, hashes, and path-derived classifications; it does not contain document body text.
- Historical document indexes contain truncated previews, not complete documents. Typical limits are about 1,200–1,500 characters.
- PDF text extraction checks up to three pages. OCR is a fallback only when embedded PDF text is empty and checks at most the first two pages.
- Spreadsheet extraction checks up to three sheets and 30 rows per sheet; DOCX checks up to 80 paragraphs; PPTX checks up to 20 slides.
- HWP/HWPX uses open-source extraction. Image files and scanned images embedded in Office/HWP documents are not generally OCR-indexed.
- Always report `operational_index_updated_at`, `content_index_updated_at`, and `content_index_stale` when content evidence materially affects the answer.

## Output style

Return the strongest few matches with clickable absolute paths, why each matched, and freshness caveats. Distinguish filename/path evidence from extracted-content evidence.
