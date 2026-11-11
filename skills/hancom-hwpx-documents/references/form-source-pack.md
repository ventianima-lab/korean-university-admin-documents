# Pre-write official form-source pack

## Invocation boundary

This gate applies to every institutional form or packet, including non-event HWP/HWPX, DOCX and XLSX work. Use a separate source-form subfolder inside each actual business folder and retain all applicable blank forms and guidance before writing. The existing CLI field `event_id` is a stable business-packet identifier for non-event work too; keep the version-1 schema unchanged.

The failed path counted external technical/TEMP master copies and authored outputs as source retention, and selected only the main form instead of the complete applicable form set. Run this gate **before authoring or filling**, not just during final packet review. Blank source copying/extraction is preparation for this gate, not permission to fill forms early. The existing final-packet checker remains a separate later check.

1. Inspect the established current business folder and latest working set first. Create the business-specific folder only when absent and authorized; preserve existing grouping. On follow-ups inspect and reuse a valid pack before editing; never reconstruct or replace the user's latest finals from blanks.
2. Independently inventory all applicable form roles from current instructions, event/expense conditions, selected official bundle and phase. Record source/checklist coordinates and the reason for required, inapplicable, later or unresolved status. A generic example is not a requirement, and a broad manual does not make every form or later-phase form mandatory. Unknown applicability blocks a complete-pack claim. Respect curated office-selected forms and explicit exclusions. If the user specifically requests several phases, inventory and check each selected phase separately; do not declare later-phase coverage from an advance-only pass.
3. Before filling any form, retain the selected official originals byte-identically **inside that business packet's active folder**, in a separate clearly named source-form subfolder. Verify original and copy SHA-256. External TEMP/QA backups cannot satisfy this default boundary. When the user expressly directs a different source location or prohibits copying, that instruction prevails: do not fabricate a default-gate PASS; report the directed exception and independently check its coverage. Never overwrite a different existing file.
4. For each applicable embedded form, retain the entire unchanged manual **and** an unfilled source-bound derivative for that form, with exact physical pages/section/table coordinates and an independent extraction/layout review. A whole-manual copy cannot stand in for its selected embedded forms. Derivatives are not byte-identical originals; hash and label them separately. A multi-form derivative is possible only when independently reviewed to contain every mapped form; shared bytes alone prove no role coverage. Preserve source originals and existing working finals. No generated final or filled form substitutes for the blank pack.
5. Run the command below separately for each business folder, including when a common form set is copied to multiple business folders. Require exit 0 and `FORM_SOURCE_PACK` / `PASSED` before dispatching authoring. Give the worker the inventory, pack mappings and successful preflight result. Any later change to applicability, sources or blanks invalidates that result; rerun before the next write. The helper is read-only. It does not grant authority to edit signer-controlled or user-reserved fields, including footer roles.

For HWPX blank packs, also require the [annotated-original guidance and structure gate](form-guidance-gate.md). Run this helper with `--guidance-check` and set each mapped HWPX form's `guidance_spec` to its private absolute guidance-spec path. Independently inspect all raw memo/comment/control channels and inline guidance against the original official source; preserve all guidance in blank masters and original table/merged-cell/label/style authority. A latest live filled predecessor is content authority only. The result records `guidance_checked` and each checked spec's hash; a coverage-only PASS cannot establish annotation fidelity.

## CLI and JSON contract (v1)

```text
python <skill-dir>/scripts/verify_form_source_pack.py --inventory <private-inventory.json> --pack <private-pack.json> --active-dir <absolute-event-folder>
```

Both manifests are UTF-8 JSON (BOM accepted). Keep them and stdout containing private paths outside public fixtures and unrequested deliverables. All file paths in JSON and `--active-dir` must be absolute. Resolve the actual event folder from business evidence, not from wherever the candidate files happen to be. Do not use a broad parent directory or TEMP as the event root to evade the active-copy test.

The JSON result binds the check to `event_id`, `phase`, resolved `active_dir`, exact input-manifest SHA-256 values and `checked_at_utc`. Preserve that result in the existing private run evidence when available; do not reuse another event's or an earlier manifest's PASS. This does not itself prove authoring had not already started.

Inventory schema:

```json
{
  "schema_version": 1,
  "event_id": "synthetic-event",
  "phase": "advance",
  "mode": "followup",
  "existing_finals": ["<absolute-user-working-final>"],
  "sources": [
    {"id": "manual", "path": "<absolute-official-original>", "sha256": "<64hex>", "authority": "current official manual and applicability"}
  ],
  "requirements": [
    {
      "id": "receipt-form",
      "role": "physical receipt attachment form",
      "phase": "advance",
      "status": "required",
      "basis": {"source_id": "manual", "location": "expense checklist row / current instruction", "reason": "this event's expense condition requires preparation now"},
      "form": {"source_id": "manual", "location": "physical page 12, exact form title", "kind": "embedded"}
    }
  ]
}
```

`mode` is `create` or `followup`; explicitly list existing finals even for a newly prepared pack when working outputs already exist. A follow-up requires a nonempty `existing_finals`. These paths are protected against template/source aliasing; the helper never reads or hashes their contents. A current user edit does not require freezing or reviewing that final. Source files must not themselves be working finals. File alias checks inspect filesystem identity only.

Every considered role needs a unique `id`, nonempty `role` and `phase`, and a `basis` linked to a real hash-bound source. `status` is `required`, `not_applicable`, `later` or `unresolved`; every decision needs its exact source location and specific reason. `required` must match the checked phase; `later` must differ. Each required form needs `form.source_id`, `form.location` and `form.kind` (`standalone` or `embedded`). Non-form actions such as ERP approvals remain separately inventoried in the phase/owner workflow; do not fabricate a paper template for them. Multiple phases require separate runs/manifests. A phase with no applicable forms is not a form-pack PASS; report that scoped disposition separately.

Pack schema:

```json
{
  "schema_version": 1,
  "event_id": "synthetic-event",
  "phase": "advance",
  "sources": [{"source_id": "manual", "path": "<absolute-active-folder-source-copy>"}],
  "forms": [
    {
      "requirement_id": "receipt-form",
      "path": "<absolute-active-folder-unfilled-derivative>",
      "sha256": "<64hex>",
      "source_location": "physical page 12, exact form title",
      "extraction_review": "independently inspected exact source region, title and preserved form layout"
    }
  ]
}
```

Map every current required role exactly once. Originals used as form sources each need an active-folder copy; one original/manual can support several independently mapped forms. A standalone blank must match its original bytes; its blank path can be the retained source-copy path. An embedded derivative needs its own current hash, matching source coordinates and nonempty `extraction_review`; it cannot be the whole manual. Later or inapplicable roles need no current form mapping. Extra mapped forms, missing mappings, unknown/duplicate IDs, unresolved applicability, source/hash/coordinate mismatches, external copies and protected-final aliases fail. Symlink/junction escapes are resolved; hardlinks to external originals fail as dependent copies.

## Meaningful completion and limits

Independently compare the complete checklist and requested phases with the inventory first; never manufacture the requirement list from the pack's existing files. Then require the helper's full declared role coverage, real official-source and copy hashes, correct event boundary and preserved blank-form mappings. A copied manual, an external QA master, successful final-file checks or a correct count cannot clear this gate. An earlier missing preflight cannot be retroactively described as performed before authoring; repair the pack without rewriting existing finals, report the actual sequence, and pass the gate before any further authorized edits.

The helper cannot authenticate official status, determine whether the source checklist inventory is exhaustive, decide event/expense applicability, inspect extraction semantics/layout or prove that a declared blank is unfilled. Independent source and derivative inspection remain mandatory. It verifies only declared pre-write source-pack coverage, not substantive completion, approval, submission or payment. Post-edit review waivers remain in force; this pre-write gate does not authorize post-save QA of actual documents or edits to user-owned fields.

The result also binds the running source-pack `checker_sha256`; each `guidance_checks` entry records the guidance checker hash. Reuse requires matching the current checker(s), not just identical input-manifest hashes. Older unbound results must be rerun rather than silently treated as current acceptance or failure.

## Format-specific routes

- HWP/HWPX: load `hancom-hwpx-documents`; for HWPX require `--guidance-check` and [form-guidance-gate.md](form-guidance-gate.md). A binary HWP needs an inspectable source-faithful conversion and reconciled authority or a precisely reported equivalent review.
- DOCX: load the available Word/template preservation skill (the public pack provides `docx-template-editor`). Inspect actual comment text and range anchors, text boxes, content controls, hidden text and inline directions through their linked OOXML parts; author/date metadata is insufficient. Compare source and exact output tables/grids/merges, fixed labels, styles/fonts, fields, section layout and latest retained content, then render every output page.
- XLSX: load `spreadsheet-form-preservation` and the applicable spreadsheet authoring skill. Inspect comments/notes and their cell anchors, hidden sheets/rows/columns, text boxes and inline examples; map each applicable instruction to its cell/region. Compare exact output formulas, merges, fixed labels, styles/fonts, row/column geometry, deliberate blanks, validations, print settings and retained user content, then inspect current printed layout.

The source-pack helper checks coverage and hashes across formats; its HWPX-only guidance flag is not a DOCX/XLSX annotation, structure or rendering check. Use equivalent source-bound checks for those formats and report any actual unsupported channel or failed verification. No helper PASS replaces independent applicability, complete attachment reconciliation or final page inspection.
