---
name: korean-university-admin-documents
description: Create, fill, revise, compare, and verify Korean university administrative documents from supplied HWP/HWPX, DOCX, XLSX, PDF, and scan templates. Use for official letters, plans, result reports, purchasing and budget forms, rosters, notices, and other department-office documents where source evidence and template fidelity matter.
---

# Korean university administrative documents

Use the supplied official template and current evidence as the authority. Preserve the source and produce a separate result unless the user explicitly requests an overwrite.

## Standing Hancom authorization

The user grants standing authorization through this skill for Hancom document automation. Hancom Office, `Hwp.exe`, `HWPFrame.HwpObject`, Hancom COM automation, and automated Hancom GUI control may be used whenever they materially help complete or verify the current requested HWP/HWPX task. Do not ask for separate per-task, per-file, per-operation, or repeat authorization. Limit automation to files and operations reasonably required by the current request, preserve pre-existing user windows, and handle routine task-related prompts automatically.

## Core workflow

1. Identify the requested deliverable, authoritative template, current instructions, source evidence, deadline, and required fields.
2. Read reference or master documents without modifying them. Choose the exact current official form before any prior-year or similar form. For official letters, establish the applicable manual or actual precedent before drafting; preserve its labels, citation syntax, routing, and attachment conventions, not just its appearance. If local evidence is insufficient, search institutional notices and administrative manuals. Follow the official-letter rules in [references/document-types.md](references/document-types.md).
3. Snapshot protected values and structures before editing. Read [references/evidence-and-protected-fields.md](references/evidence-and-protected-fields.md).
4. Select the format workflow in [references/format-routing.md](references/format-routing.md).
5. Fill only supported values. Leave unsupported approval, contact, vendor, amount, quantity, document-number, and issue-date fields blank or explicitly unresolved. Treat every date field inside a 결재란, approval block, signature block, or signer row as signer-controlled: leave it blank even when another document date is known, and fill that exact field only when the user explicitly directs it.
6. Preserve the authoritative template's layout and change only the requested content. Do not redesign a supplied form. Leave unsupported values blank in the artifact and report unresolved facts separately; do not insert unsolicited remarks or workflow explanations. For purchase packets, verify item, specification, package/unit quantity, price, and totals across every related document using `style-guide`.
7. Apply the Korean writing route in `korean-admin-writing` only to unprotected prose.
8. Validate protected values, structure, text, formulas where applicable, page images, and application openability. Read [references/quality-gates.md](references/quality-gates.md).
9. Deliver the requested final artifact and a concise verification status. Do not expose internal QA intermediates unless requested.

## Document types

Read [references/document-types.md](references/document-types.md) when drafting an official letter, plan, result report, budget or purchase packet, meeting document, roster, or notice.

## Hard failures

- `VERIFICATION_FAILED`: a protected fact, value, association, table order, or required label changed.
- `TEMPLATE_MISMATCH`: the output is based on the wrong form or an unapproved reconstruction.
- `LAYOUT_FAILED`: clipping, overlap, missing glyphs, broken tables, or unexpected pagination remains.
- `OPENABILITY_UNVERIFIED`: exact application reopen could not be completed.
- `EVIDENCE_REQUIRED`: a required fact is missing and must not be invented.
