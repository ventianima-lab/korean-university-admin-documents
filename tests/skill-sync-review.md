# Document skill synchronization review — 2026-09-08

Reviewed complete folders for all seven existing installed counterparts, including scripts, references, examples, and invocation metadata. Reviewed the four public-only adapters without replacing them with proprietary product plugins. Added the installed comparison-quote skill, bringing the pack to twelve skills.

| Skill | Result |
|---|---|
| document-scan-cleaner | No substantive delta; newline-only differences retained. |
| fluent-korean | Added prohibition on unsolicited administrative annotations. |
| grammar-checker | No substantive delta; newline-only differences retained. |
| hancom-hwpx-documents | Added full template search gate, annotations/quantity routing, conditional manual-badge removal, and generalized attendance-master guidance. |
| humanize-korean | No substantive delta; newline-only differences retained. |
| hwp-to-hwpx-converter | Retained newer public standing-authorization wording; helpers have no substantive delta. |
| style-guide | Added package/unit/specification totals and cross-document purchase consistency rules. |
| hwpx-internet-comparison-quotes | Added complete skill, UI metadata, checklist, and verifier; tested synthetic pass/fail cases. |
| korean-admin-writing | Public adapter updated to route annotations and quantity checks. |
| korean-university-admin-documents | Public adapter updated for blank fields, separate uncertainty reporting, and cross-document consistency. |
| docx-template-editor | Public adapter retained; no same-name installed counterpart. |
| spreadsheet-form-preservation | Public adapter retained; no same-name installed counterpart. |

Intentional differences: personal filesystem locations are generalized; institution-specific master identity is omitted; form-badge removal is conditional on a verified requirement rather than imposed on other institutions. Existing public standing Hancom authorization remains authoritative over stale installed references. Third-party licenses and automatic invocation metadata remain unchanged. Unrelated browser, system, archive, and administrative-system skills are outside this document-authoring pack. Proprietary bundled document/spreadsheet product skills are not copied into the public repository.

Validation: public release scan, all twelve skill manifests, and five synthetic quote-verifier tests. No real records, screenshots, credentials, or personal paths are included.

## 2026-09-09 follow-up

Updated the complete spreadsheet-form-preservation adapter with bounded Korean/English keyboard-state recovery, explicit HCell markup fallback handling, and roster-specific period preservation. Installed the maintained adapter locally with its existing scripts and metadata. The working tree was clean before this update; no pending public changes were omitted. No proprietary spreadsheet-plugin material was copied. Validated the release scan and all skill manifests; these changes add instructions only and do not change executable helpers.

## 2026-09-14 follow-up

Reviewed the complete installed and public `hancom-hwpx-documents` folders after a user-visible file-access prompt exposed an enforcement gap. The rule already named `FilePathCheckerModuleExample`, but it was buried in the exact-page-copy procedure and there was no shared constructor for ordinary open, page-count, or PDF-export automation. Added a fail-closed COM guard with a fixed module name, routed both PowerShell COM helpers through it, removed the caller-controlled module-name parameter, and added a static guard-contract test. The installed preflight and exact-page copy passed live checks without an access prompt; PowerShell parsing, all public skill validations, and the public release scan passed.

Intentional differences remain unchanged: public files retain portable tool paths and generalized institutional examples, while private local paths and institution-specific record facts are not published. No proprietary Hancom security-module binary or real document was added.

## 2026-09-15 follow-up

Added the complete `korean-student-group-chat-notice` skill and invocation metadata after a student event-notice workflow demonstrated a reusable audience-filtering pattern, bringing the pack to fourteen skills. The skill requires source-first extraction, separates student actions from staff-only material, protects dates, times, locations, links, and exceptions, and verifies Korean text in phone-readable portrait images. The public copy contains no real notice, institution name, private path, contact detail, or proprietary asset. The maintained clone was clean before this addition, so no related pending public changes were omitted.

## 2026-10-06 procurement correction follow-up

Compared all fourteen public skill folders with their available installed counterparts, including references, scripts, examples, licenses, and invocation metadata. Added the user's preparation-permission rule, a complete-column specification/quantity gate, and an explicit procurement reference covering requested checkbox/card fields, quotation dates and issuers, editable Word quotations, receipt-reference handling, consistent date-based goods/process/results layouts, and annotation rejection. Entry-point routing now requires that reference before filling and field-level comparisons after saving; existing no-annotation and consistency rules alone had not prevented mixed rows and unnecessary permission questions.

Preserved the public-only administrative and Word adapters and their independent implementation. The related quote-grouping, current-file, and minimal-PDF updates from another task were already published in the preceding commit and remain intact. Scripts and invocation policy have no substantive changes, so no executable-helper behavior changed. Blank-line differences are retained rather than creating sync noise.

Intentional local/public differences remain: private tool and record paths, the institution's attendance master, and its form-badge convention are generalized in public; the newer portable archive and standing-conversion authorization wording is preserved. No private documents, stamp images, card identifiers, credentials, or proprietary plugin instructions are published. The added decision checks use synthetic values.

Validation: the public release scan, all fourteen public skill manifests, and the three updated installed manifests passed. Seven procurement-reference routes resolve to existing files. The nine synthetic decision cases were reviewed against the entrypoints and saved-field gates. No executable helpers or invocation policy changed; generated Python caches are excluded from source synchronization.

### Named-item coverage and quotation grouping

The follow-up exposed a gap: identical row patterns still omitted the quantities of other explicitly named materials. The gate now compares both adjacent columns and requires every named item to have source-backed specifications and quantities. It permits consistent omission of repeated names, handles mixed specifications without collapsing their quantities, and rejects unreadable single-line squeezing. Planning rows use the requested quotation grouping and planned vendor rather than inheriting actual receipt-merchant grouping; merged amounts are independently summed while actual merchant evidence remains separate. Added two synthetic decision cases. The installed style and procurement-reference folders were compared in full with the public pack; unrelated scripts, invocation metadata, private-path generalizations, and newer public corrections remain intact.

The public release scan and fourteen public plus two relevant installed skill validations passed. All eleven synthetic decision cases were reviewed; no executable helper or invocation policy changed.

### Official-letter and operating-plan grouping

The next correction exposed a table-coverage failure: the attached operating plan followed the quotation groups while the official-letter cover table retained receipt-based rows. The procurement route now inventories every planned-purchase table before editing and compares each saved row count, order, and amount vector against the quotations and the other planned tables. Matching totals alone cannot pass this gate. Actual receipt-merchant associations remain separate. Added a synthetic mismatched-cover case.

Compared all fourteen public folders with the complete available installed counterparts, including references, scripts, and invocation metadata. Preserved public-only adapters, intentional private-path generalizations, and newer public corrections; no related pending source updates were omitted. The public release scan, all fourteen public manifests, and the updated installed manifest passed. All twelve decision cases were reviewed against the saved-field gates. No executable helpers or invocation policy changed; no private records or proprietary plugin material were published.

### Date separation, kind-count summaries, and file containment

The next corrections distinguished three independent constraints: a one-page usage plan still needs each class date separately; a requested representative-plus-other-kinds label needs source-based distinct-kind counting; and one date per evidence page does not justify creating one editable file per date. The procurement route now maps file count, page count, date groups, and transaction groups independently. Saved-file gates compare each date's use, representative-excluding counts, editable consolidated page content, and active-folder file count. Verified technical backups preserve superseded individual files without introducing an archival step or duplicate active deliverables.

Compared the complete installed/public folders again, retaining the public-only adapters, seven intentional portable/private differences, newer corrections, scripts, and invocation metadata. The release scan and fourteen public plus one installed manifest validations passed. All fifteen synthetic decision cases were reviewed; no published executable helper or invocation policy changed. Temporary consolidation work was verified by exact native reopens and page comparisons, without publishing real records or unverified fallback methods.
