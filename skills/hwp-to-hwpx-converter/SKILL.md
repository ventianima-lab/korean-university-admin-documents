---
name: hwp-to-hwpx-converter
description: Convert legacy binary HWP files, including HWP content mislabeled with a .hwpx extension, into validated HWPX using open-source conversion first and Hancom automation when needed. Use for HWP-to-HWPX conversion, administrative document migration, and diagnosing whether a Korean document is OLE HWP or ZIP-based HWPX.
---

# HWP to HWPX Converter

Use the bundled PowerShell scripts first. The runtime is open-source `hwp2hwpx==1.0.1` plus a portable Eclipse Temurin JRE, installed under the user's Codex runtime directory. The parent skill grants standing authorization for task-related Hancom automation. If conversion or final openability verification fails, use Hancom Office or HWP COM automation without requesting separate task, file, operation, or repeat approval; reserve computer-use for an unavoidable prompt.

## Workflow

1. For a follow-up conversion or edit, re-enumerate the active task folder and select the current working final as the input baseline. Do not use an older source, intermediate, backup, candidate, validation copy, or prior run output when a newer final exists.
2. Before replacing any working final, record its path, modification time, SHA-256, page or section count, and representative completed-content markers. Block replacement if the converted candidate drops content outside the requested change.
3. Run `scripts/setup_runtime.ps1` once. It installs or reuses the pinned runtime without a GUI.
4. Run `scripts/convert_hwp_to_hwpx.ps1 -InputPath <source> -OutputPath <target>`.
5. Preserve the source and use a distinct `.hwpx` output path.
6. Treat success only as the script's exit code 0 plus its `status: converted` or `status: validated-copy` result.
7. For important records, record source/output SHA-256 values in the task manifest.

## Behavior

- OLE signature `D0 CF 11 E0 A1 B1 1A E1`: convert as legacy HWP, regardless of filename extension.
- ZIP signature `50 4B 03 04`: validate as HWPX; copy only when source and output differ.
- Other signatures: stop with a concrete error.
- If a supplied or requested `.hwpx` file actually contains OLE HWP bytes, keep the original bytes separately and create a real HWPX at a clearly identified output path when HWPX is the user's desired format. Renaming the only accessible file to `.hwp` is not completion of an HWPX request. Verify the exact output's signature, content and page count against the source, and check native openability and a current rendering when layout matters.
- HWPX validation checks the first `mimetype` entry, exact mimetype value, required package parts, and XML well-formedness.
- Existing output is not overwritten unless `-Force` is explicitly supplied.

## Commands

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/convert_hwp_to_hwpx.ps1 -InputPath "C:\docs\source.hwp" -OutputPath "C:\docs\source.hwpx"
```

If setup cannot discover Python, pass `-PythonExe <absolute-python.exe>`. Network is needed only for first-time runtime installation.
