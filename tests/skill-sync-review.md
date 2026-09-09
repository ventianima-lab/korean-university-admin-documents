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
