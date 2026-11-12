param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'test_hancom_security_module.ps1')

# All native boundaries are replaced; this file never creates a COM application.
function New-HancomGuardedObject {
    param([switch]$Hidden)
    if ($Hidden) { throw 'Preflight must not change visibility before binding.' }
    if ($script:case.RegisterFail) { throw 'Synthetic registration failure' }
    [pscustomobject]@{ Synthetic = $true }
}
function Get-HancomPreflightProcesses {
    if ($script:closed -and $script:case.Remains) {
        [pscustomobject]@{Id=202; StartTime=$script:start}
    } elseif (-not $script:closed) {
        foreach ($id in $script:case.Baseline) { [pscustomobject]@{Id=$id; StartTime=$script:start} }
    }
}
function Get-HancomPreflightIdentity([int]$ProcessId) {
    $script:identityCalls++
    $time = $script:start
    if ($script:identityCalls -gt 1 -and $script:case.Recycled) { $time = $time.AddSeconds(1) }
    [pscustomobject]@{Id=$ProcessId; ProcessName='Hwp'; StartTime=$time}
}
function Get-HancomPreflightWindows($Hwp) {
    $script:windowCalls++
    if ($script:case.Unbound) { throw 'Synthetic missing HWND' }
    $handle = 77
    if ($script:windowCalls -gt 1 -and $script:case.WindowChanged) { $handle = 88 }
    [pscustomobject]@{Handle=$handle; ProcessId=$script:case.Bound}
    if ($script:case.MultiProcess) { [pscustomobject]@{Handle=99; ProcessId=303} }
}
function Get-HancomPreflightDocumentCount($Hwp) {
    $script:documentCalls++
    if ($script:documentCalls -gt 1 -and $script:case.NewDocument) { return 2 }
    $script:case.Documents
}
function Close-HancomGuardedObject($Hwp) { $script:quits++; $script:closed=$true }
function Release-HancomPreflightReference($Hwp) { $script:releases++ }

$cases = @(
    @{Name='zero_baseline'; Quit=1; Pass=$true},
    @{Name='preexisting_other_preserved'; Baseline=@(101); Quit=1; Pass=$true},
    @{Name='preexisting_same_object'; Baseline=@(202); Quit=0},
    @{Name='unbound'; Unbound=$true; Quit=0},
    @{Name='multiple_owner_processes'; MultiProcess=$true; Quit=0},
    @{Name='initial_shared_documents'; Documents=2; Quit=0},
    @{Name='no_initial_document'; Documents=0; Quit=0},
    @{Name='recycled_pid'; Recycled=$true; Quit=0},
    @{Name='changed_window'; WindowChanged=$true; Quit=0},
    @{Name='new_document_before_quit'; NewDocument=$true; Quit=0},
    @{Name='quit_does_not_prove_exit'; Remains=$true; Quit=1},
    @{Name='registration_failure'; RegisterFail=$true; Quit=0}
)
foreach ($inputCase in $cases) {
    $script:case = @{Baseline=@(); Bound=202; Documents=1; RegisterFail=$false; Unbound=$false;
        MultiProcess=$false; Recycled=$false; WindowChanged=$false; NewDocument=$false;
        Remains=$false; Pass=$false}
    foreach ($key in $inputCase.Keys) { $script:case[$key]=$inputCase[$key] }
    $script:start=[datetime]'2030-01-01Z'
    $script:closed=$false
    $script:quits=0; $script:releases=0; $script:identityCalls=0
    $script:windowCalls=0; $script:documentCalls=0
    $output=@(); $failure=$null
    try { $output=@(Invoke-HancomSecurityPreflight) } catch { $failure=$_.Exception.Message }
    if ($script:quits -ne $script:case.Quit) { throw "Unsafe/missing Quit: $($script:case.Name)" }
    if (($null -eq $failure) -ne $script:case.Pass) { throw "Wrong result: $($script:case.Name): $failure" }
    if ($script:case.Pass -and 'CLEANUP=VERIFIED' -notin $output) { throw 'Missing verified cleanup' }
    if (-not $script:case.Pass -and -not $script:case.RegisterFail -and $failure -notmatch 'CLEANUP=UNRESOLVED') {
        throw "Missing cleanup warning: $($script:case.Name)"
    }
    if ($script:case.Quit -eq 0 -and -not $script:case.RegisterFail -and $script:releases -ne 1) {
        throw 'Unowned caller reference was not released exactly once'
    }
}

# Exercise the real guard's registration-failure branch with a synthetic object.
. (Join-Path $PSScriptRoot 'hancom_com_guard.ps1')
$script:failedObject=[pscustomobject]@{QuitCalled=$false}
$script:failedObject | Add-Member ScriptMethod RegisterModule { param($kind,$name) return $false }
$script:failedObject | Add-Member ScriptMethod Quit { $this.QuitCalled=$true }
function New-Object { param([string]$ComObject) $script:failedObject }
$guardFailed=$false
try { $null=New-HancomGuardedObject -WarningAction SilentlyContinue } catch { $guardFailed=$true }
if (-not $guardFailed -or $script:failedObject.QuitCalled) { throw 'Registration failure quit an unbound object' }
Write-Output "SECURITY_PREFLIGHT_CONTRACT=PASS CASES=$($cases.Count + 1) NATIVE_APPLICATION_LAUNCHED=False"
