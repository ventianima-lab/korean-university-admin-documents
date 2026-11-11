# Native automation ownership and lock release

Before native document access, record the pre-existing application processes and documents without changing them. Track each COM object created by this run, its opened files and, when verifiably bound to that object/window, its process ID and start time. A newly observed PID alone is not proof of ownership when other workers or the user may start instances concurrently.

Before any document `Open` on a newly created COM object, record the pre-existing process baseline and exact planned file paths, then bind that same object through its window handle to the owning PID and process start time and record the association. The object must already have passed the existing security-module gate; obtaining window/PID metadata does not authorize changing visibility or accessing a document. If the object-to-window-to-process association cannot be verified and recorded before opening, do not open a document with that object; continue with format-level methods when sufficient and report native verification as unresolved. A recently appeared PID, creation timing, automation flag, or embedding flag cannot substitute for the association. A match is not permission to quit a shared application or alter unrelated documents.

On a sharing violation or apparent file lock, diagnose the exact path read-only before asking the user to close an application. Distinguish file attributes, an actual sharing violation and other access failures. Use an available read-only lock-owner enumeration, such as Windows Restart Manager, and record owner PID, process start time, automation/embedding flags and the independently tracked object association. Flags describe a process's mode, not who owns it; neither those flags nor a closed visible window establish that the instance belongs to this task or that the user still has the document open. Do not repeat a close request without new owner evidence. If ownership cannot be established, state that specific uncertainty and preserve the file and process.

Use `finally` cleanup for task-opened documents and verified task-owned objects. Close/release only those resources; verify that a whole-object quit will not close pre-existing user documents. Never terminate all application processes, attach to an arbitrary active object to quit it, or infer authority to close an older automation instance from its command-line flags. Preserve other workers' instances and pre-existing user objects. A cleanup call returning, or an exception being swallowed, does not prove release; it also does not by itself establish a defect in the shared security guard.

After the last native reopen/render/verification, complete cleanup and re-enumerate owners of every exact file opened by this run. Compare process identity using PID plus start time and the tracked object association, not a recycled PID. Require evidence that this run left no attributable new file lock; legitimate pre-existing locks need not disappear. Preserve the exact verified file bytes and final hash. If a task-attributable lock remains or the ownership/release check cannot be completed, report that precise unresolved cleanup status rather than claiming release or asking the user to close the same document again. This gate does not authorize modifying the source or closing any unowned object.

## Strict-mode caller preflight

A caller that dot-sources the guard inherits strict mode. An empty process baseline has no `.Id` property: materialize IDs by pipeline before COM creation, rather than using `$baseline.Id`. Serialize with `ConvertTo-Json -InputObject @($baseline)`, since piping an empty baseline can produce no JSON instead of `[]`. In the existing caller path, use this baseline block before creating its guarded object:

<!-- ownership-baseline-start -->
```powershell
$baselineIds = @($baseline | ForEach-Object { [int]$_.Id })
$baselineJson = ConvertTo-Json -InputObject @($baseline) -Depth 4
$owned = $false
$ownerId = 0
$ownerStart = $null
```
<!-- ownership-baseline-end -->

After security registration and the same object's window-to-PID binding have succeeded, supply `$boundProcessId`, the independently read `$ownerProcess` and that object's `$initialDocumentCount`. Perform this binding block before log serialization, file hashing/opening, visibility changes or other unrelated throwing work:

<!-- ownership-binding-start -->
```powershell
if ($boundProcessId -le 0 -or $ownerProcess.Id -ne $boundProcessId -or
    $ownerProcess.ProcessName -ne 'Hwp' -or $boundProcessId -in $baselineIds) {
    throw 'Unbound or pre-existing process; no file access or quit authorized.'
}
if ($initialDocumentCount -ne 1) {
    throw 'Initial document scope is not exclusive; preserve the unowned object.'
}
$ownerId = [int]$boundProcessId
$ownerStart = $ownerProcess.StartTime
$owned = $true
```
<!-- ownership-binding-end -->

Keep creation and binding inside the same `try/finally`. Only after this block may the caller write its ownership evidence and proceed; if evidence writing fails, `finally` still has the bound identity for scoped cleanup. Recheck that identity and document scope before a whole-object quit. Unbound/shared objects remain unresolved and must not be quit speculatively. A run-local mutex serializes only callers using that exact mutex; do not describe it as a global canonical lock unless a verified shared implementation exists. Run `scripts/test_hancom_owner_preflight.ps1` for zero/one-baseline ID extraction, JSON array round-trips and post-binding-failure regressions without launching Hancom. This test proves the caller pattern, not native application opening or process exit.
