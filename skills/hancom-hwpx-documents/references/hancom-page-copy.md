# Hancom exact-page copy

The standing authorization in the parent skill covers this procedure. Do not pause for separate task, file, operation, or repeat approval. It is for exact page copying from an authoritative HWP/HWPX master; Kordoc remains the parser, patcher, validator, and renderer around the Hancom-only page-copy step.

## One-time official security module setup

Hancom publishes `보안모듈(Automation).zip` on its [HwpAutomation developer page](https://developer.hancom.com/hwpautomation). The archive contains `FilePathCheckerModuleExample.dll` and its source. The sample DLL returns `TRUE` from `IsAccessiblePath`, so install it only from the official Hancom archive and register it for the current Windows user.

1. Copy the DLL to a stable local path outside the records tree, such as `<local-tools-dir>\hancom-automation-security\FilePathCheckerModuleExample.dll`.
2. Create `HKCU\Software\HNC\HwpAutomation\Modules`.
3. Add the string value `FilePathCheckerModuleExample` whose data is the DLL's full path.
4. Call `HwpObject.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleExample")` and require `True` before opening or saving files.

`SetMessageBoxMode` does not suppress the file-path access dialog when the module is absent. It can answer ordinary message boxes during an already authorized operation. Reset it with `0xFFFFFF` in `finally`.

## Physical pages, not printed page numbers

`GetPageText(physicalIndex, 0xFFFFFFFF)` is zero-based. Inspect all pages and record the physical indexes containing the exact form title. Do not rely on the `Goto` dialog: its number may follow the document's printed page numbers.

The reliable movement sequence is:

1. `MoveDocBegin`.
2. Run `MovePageDown` `startPhysicalPage - 1` times.
3. `CopyPage` in the source object.
4. `MoveDocEnd` and `PastePage` in a separate target object.
5. After the first paste, remove only the target's automatically created blank first page with `MoveDocBegin` and `DeletePage`.

Use `scripts/copy_hancom_pages_exact.ps1` for this sequence. If a page paste fails, the helper retries once after a short clipboard delay. If a boundary still refuses pasting, copy the logical form components to separate outputs; do not re-create the page or delete XML topology to force a merge.

If format-preserving text patching leaves empty paragraphs in edited table cells and the form overflows, inspect the changed cells first. Run `scripts/clean_empty_form_paragraphs.py` only with anchors that uniquely identify those changed cells. The helper preserves the source namespace prefixes and ZIP entry properties. Always write a separate candidate, validate it, and reopen the candidate in Hancom before replacing a working file.

When an explicitly identified form requires removing a manual-only badge, remove its entire nested label table and enclosing run after copying. Preserve the first paragraph and its section/column properties. Blank text alone leaves an empty object and does not reclaim space. Apply this only to forms with a documented removal requirement; preserve all other form-number badges. Reflow, reopen, and verify the expected page count and absence of the removed label.

## Completion gates

- The source remains byte-identical.
- The output page count equals the copied physical-page count.
- Hancom reopens the exact output and `GetPageText` contains the expected title.
- `python-hwpx` and Kordoc validation pass.
- A current render shows the copied layout and all edits without overflow.
- Record the final SHA-256 and leave pre-existing user-owned Hwp windows open.
