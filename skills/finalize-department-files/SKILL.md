---
name: finalize-department-files
description: Finalize completed university department-file work and archive incoming department scans by identifying business packets, preserving active work and unresolved evidence, standardizing names, verifying moves and hashes, recording manifests, and refreshing the local index. Use for completed task cleanup or incoming scans for ongoing or archived department work. Also use when the user asks to gather component originals under an active packet while exposing named canonical bundles.
---

# Finalize Department Files

Treat completed-work archiving as verified records closeout. Handle incoming scans for ongoing work using the scoped path below.

Do not broaden the cleanup to unrelated files merely because they share the same work folder.

## Originals inside an active working packet

When the user requests an original-storage folder while keeping named integrated bundles visible, treat that as working-folder organization, not business completion or permanent closeout. Use the requested original-storage folder inside the actual packet; this explicit layout overrides the generic prohibition on new archive wrappers for completed records. Keep the named canonical bundles at the requested working-folder level, preserve phase and claim boundaries inside original storage, and do not resave documents merely to move them.

Inventory the current components and recoverable originals already moved to technical backup using the existing move maps. Bring those originals into durable original storage rather than leaving the user's only component copies in TEMP. Preserve relative business/stage paths, raw media, signatures, scans and source forms; do not flatten colliding names or merge unrelated activities. An entire folder may be relocated intact only within the user's authorized layout scope.

Before moving linked sources, inventory their current reference consumers. After byte-preserving moves, update authorized calendar/index references through their current versioned interfaces and verify the saved paths while preserving unrelated fields; do not keep scattered active copies solely to avoid repairing links. Record collisions or failed reference updates precisely. Require the requested visible canonical-file set, preserved original inventory and move-integrity results. Keep technical manifests outside the active deliverable view. A content-review waiver does not invite document resaving or rendering during this organization step; perform only the authorized move-integrity and reference checks.

## Incoming scans for an existing business packet

Use this scoped path when asked to archive incoming scans, even if the underlying work is ongoing. Establish the packet and its current status from current evidence. Put the authoritative scan in the existing business folder inside `00_작업중` when the work is ongoing; if the work is already archived, put it directly in the existing permanent business packet. Scan arrival alone does not complete the work or authorize moving editable sources, closing the task, or clearing its working folder. Apply closeout-only residue and completion checks only to an actual authorized closeout.

Before any scan move, inventory incoming scanned PDFs and images together with existing scanned PDFs and images throughout the actual destination business packet, including differently named files. Scope the inventory to that packet, not unrelated records. Compare incoming scans with one another and with destination scans: inspect every page, page order, signatures, stamps, handwriting, approvals, and attachments. A matching title, filename collision, or different compression or hash does not establish equivalence. Preserve materially distinct evidence and non-scan editable files in their existing grouping.

Establish complete equivalence and which scan is newest using reliable scan metadata, supported filename timestamps, or actual record revisions; a copied file's modification time alone is insufficient. If equivalence, completeness, or recency is uncertain, preserve the candidates in place, record the uncertainty, and do not claim that group was reconciled.

For each verified-equivalent group, retain the proven newest complete scan as the single canonical scan in the existing business packet. Where the current instruction and workspace policy authorize deletion-review moves, move every superseded scan, including older scans already in the destination, to the designated review area using meaningful, normalized, collision-free filenames. If the destination scan is newest, retain it and move older incoming equivalents to review. Without that authorization, preserve candidates in place and report the incomplete reconciliation. A review move is not deletion authorization: permanently delete only when separately and explicitly authorized by the latest instruction.

Use a verified version-replacement manifest, never a blind OS overwrite or force operation: record each candidate's original and resulting paths, role and disposition, identity/completeness and recency evidence, size and before/after SHA-256, and links to the retained scan's original path, canonical path, and hash. Recheck source hashes immediately before each move, move the superseded destination scan to an unoccupied review path and verify it before installing a newer incoming scan at an unoccupied canonical path; stop on drift, collision, or hash mismatch and preserve all surviving files.

Completion gate for each reconciled group: re-inventory the packet and require exactly one canonical scan, proven newest and complete; verify every superseded destination source has been moved from its old path (if the canonical scan reuses that path, verify its current identity against the manifest), every superseded scan exists in review under a meaningful normalized filename, and the manifest links all original and resulting paths and matching hashes to the retained scan. Verify the retained scan exists and matches its recorded hash and that active editable sources and unrelated grouping remain unchanged. Refresh the applicable index after authorized moves. Report any unresolved identity, recency, placement, or failed check rather than claiming completion.

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

For XLSX classification, run `scripts/inspect_archive_workbook.py` and read the populated cells of every sheet, including hidden sheets. A first-sheet roster, shared-string sample, filename containing `양식`, or an earlier copy's hash cannot establish that the exact current workbook is blank or university-wide. Locate the filled department form and its actual record rows before proposing a destination or asking the user to choose one. Preserve a combined roster/form workbook intact and use the populated form's department and target academic year; retain conflicting reference-year values as evidence without editing them. Record sheet/cell evidence for the department, title/year, populated record, and completion markers, then rerun those exact checks with `--expect-cell SHEET CELL VALUE` on the archived file. Missing sheet coverage or failed expected-cell checks block classification/handoff. Byte-identical archiving needs no spreadsheet resave or automatic PDF.

### Verify the initiating notice

For records prepared in response to a notice, official request, or amended announcement, locate and read that specific notice's full body and decision-relevant attachments before choosing a year, business folder, packet membership, or filename. Search the local notice ledger and saved evidence first, then refresh the exact authenticated notice when available. A ledger status, title, filename, or download date alone cannot pass this check. Distinguish the latest amended notice from an earlier version and similar requests from another programme.

Record the notice title, identifier, URL or exact local evidence path, issuing office, amendment/version, retrieval time, and precise body/attachment locations. Cross-check the document's department, record title/year, appointment or operating period, recipient, and required attachment relationship. Separate the record's own operating year from a future curriculum or programme year discussed in its purpose; do not automatically replace the former with the latter. Keep a signed supporting resume with its committee packet rather than routing it to general personnel records. A populated application with an embedded blank companion form is not wholly a blank template: preserve the complete submitted package without splitting or resaving it merely for archiving.

Include `notice_verification_status`, `notice_reference`, `notice_checked_at`, and `notice_evidence_locations` in the classification row. Use `CURRENT_NOTICE_VERIFIED`, `SAVED_NOTICE_VERIFIED`, `NOT_APPLICABLE`, or `NOTICE_UNVERIFIED`; cached evidence retains its original capture date and must never be reported as a live check. If the notice is unavailable or conflicts materially with the files, preserve affected files in place, record the concrete missing/conflicting evidence, and continue evidence gathering. A notice's submission requirement does not prove actual submission; use the user's confirmation or explicit receipt evidence.

Completion requires a verified notice reference for each notice-driven move and an explanation for differing record/target-programme years. Reconcile the final filename, destination year, business function, and companion files with the recorded evidence locations. `NOTICE_UNVERIFIED` blocks a notice-driven move.

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

### Diagnose blocked Windows moves or deletions

- Capture the exact failed operation and error text, then compare the current user SID, owner SID, inherited and explicit access rules, attributes, path shape, and relevant destination or recycle-bin access. A permission dialog alone does not identify the cause.
- Keep permission inspection, opening a handle with DELETE access, and completing a move or deletion as separate findings. A successful access probe does not prove the complete operation will succeed or that no process retains directory handles. State the coverage and any inaccessible processes.
- If needed, compare an isolated disposable copy under the same parent with the original, using the same operation path. Verify its content hashes, restrict cleanup to the resolved scratch path, and confirm the original hashes are unchanged. Success on the copy rules out neither original-specific state nor application-specific blocking.
- Identify processes holding the exact source or descendant paths before proposing process cleanup. An open handle is evidence of use, not proof that it blocks deletion. Do not forcibly close handles, terminate a shared application, reset ownership, or broaden access merely because a handle exists or an access check passes.
- Keep report-only diagnosis non-mutating for the source. Perform repairs, moves, or deletions only within the user's authorized scope. Call the problem resolved only after the originally failing operation succeeds in that scope; otherwise report verified findings, the unconfirmed cause, and the remaining discriminating check.


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
