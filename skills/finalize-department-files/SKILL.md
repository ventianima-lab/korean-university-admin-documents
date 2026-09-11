---
name: finalize-department-files
description: Finalize completed university department-file work by identifying authoritative records, classifying each file from its content and business packet, applying a March-to-February academic-year boundary, standardizing evidence-backed filenames and destinations, preserving originals and unresolved items, verifying SHA-256, recording manifests, refreshing the local index, and confirming no task residue remains. Use for requests to archive, close out, organize, or permanently file completed department records.
---

# Finalize Department Files

Treat archiving as verified records closeout, not a simple move.

## 1. Establish the archive policy

1. Read the workspace's records root, control/index root, taxonomy, latest index report, and relevant earlier manifests.
2. Use one versioned record-series policy as the source of truth for the skill, target validator, audit, and index checks.
3. Do not treat the current folder or filename as proof that a record is correctly classified.

## 2. Build a classification dossier before moving

Create one row per file containing:

- current absolute path, size, SHA-256, extension, and detected container;
- document title and exact evidence location;
- actual department and business function;
- explicit academic year, semester, operating period, and their evidence locations;
- issue/event dates separated from quoted, revision, birth, cohort, scan, download, and filesystem dates;
- record series and business-packet relationship;
- proposed filename, proposed destination, reason, extraction status/error, confidence, and policy version.

Inspect document structures as well as visible text. For spreadsheets, include relevant sheets, hidden sheets, formulas, and populated-record signals. For packaged Korean documents, prefer deterministic parsing and structural inspection; render when layout affects the decision.

## 3. Determine the academic year

Use this priority order:

1. explicit target academic year in the document;
2. explicit semester or operating period;
3. authoritative issue or event date;
4. filesystem dates only as a last resort.

An academic year runs from March 1 through the last day of February in the following calendar year. January and February therefore belong to the previous academic year. A document explicitly prepared for a future academic year belongs to that stated academic year even when drafted earlier.

Do not confuse reference years, regulation revision years, quoted prior records, student cohorts, or dates on supporting attachments with the packet's target academic year.

## 4. Preserve business packets and record series

- Classify by actual content first, business-packet relationship second, established adjacent-year record series third, folder context fourth, and filename fifth.
- Keep supporting attachments with the business packet when they are needed to understand or audit it, even when an attachment has an older reference date or a different document form.
- Treat a public letter as a form, not automatically as a business function.
- Do not split scans from the packet they evidence.
- For recurring records such as instructor parking rosters, use the workspace's versioned record-series destination and block any path that disagrees with it.

## 5. Standardize filenames from verified content

Prefer readable patterns such as:

```text
YYYY학년도_학기_학과명_업무명_문서성격_버전.ext
YYYY년_M월_학과명_업무명_문서성격.ext
```

- Reflect the verified title, department, year/semester, business, document character, and meaningful version.
- Remove accidental copy markers, duplicated words, typos, and obsolete work traces only after the file's role is established.
- Keep `양식` only for a genuinely blank reusable form. A populated form is a record, not a blank template.
- Use `제출본` only when submission is confirmed.
- Never silently overwrite an existing target. Compare content and hashes first.

## 6. Resolve uncertainty without misclassification

Continue with full text, tables, hidden sheets, adjacent-year examples, packet context, hashes, and metadata before declaring a file unresolved. For a whole-corpus request, do not return routine candidate rows to the user for manual sorting.

If evidence still cannot support a safe move, preserve the original in place and record one of:

```text
PRESERVE_NO_MOVE
UNRESOLVED_CONFLICT
DUPLICATE_RETAINED
ACTIVE_WORKING_RETAINED
NO_RENAME_EVIDENCE
```

Do not guess encrypted, damaged, or unreadable contents. Do not re-save them merely to inspect them.

## 7. Gate and execute moves

Before every move:

1. resolve explicit absolute source, target, and target parent paths;
2. confirm the source has not drifted from the dossier's size and SHA-256;
3. run the deterministic target-policy validator;
4. confirm the target does not exist;
5. ensure the classification row and evidence are complete.

Use literal-path moves in one operating-system-native flow. After each move require target presence, source absence, size equality, and SHA-256 equality. Stop on source drift, collision, hash mismatch, policy rejection, or index failure.

Exact duplicates are not permission to delete. Retain the authoritative business copy and move deletion candidates to an approval area only when the workspace policy allows it.

## 8. Record and verify closeout

Produce at least:

```text
scope_census.csv
classification_manifest.csv
move_manifest.csv
verification_report.md
index_reconciliation.md
```

The move manifest records source, target, size, SHA-256 before/after, status, reason, evidence, and policy version. Refresh the operational index, verify every final path, rerun record-series audits, check task residue and empty task-created folders, and confirm changed files have no taxonomy-mismatch flags.

Report authoritative final paths, counts, hash results, index timestamp, preserved unresolved items, and deletion candidates. Never make the user reconstruct the outcome from raw manifests.
