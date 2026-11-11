param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$text = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../references/hancom-lock-ownership.md') -Raw
function Get-Pattern([string]$Name) {
    $pattern = '(?s)<!-- ownership-' + $Name + '-start -->\s*```powershell\s*(.*?)\s*```\s*<!-- ownership-' + $Name + '-end -->'
    $match = [regex]::Match($text, $pattern)
    if (-not $match.Success) { throw "Missing executable reference pattern: $Name" }
    [scriptblock]::Create($match.Groups[1].Value)
}
$baselineBlock = Get-Pattern 'baseline'
$bindingBlock = Get-Pattern 'binding'
$cases = @(
    @{ Name='zero_baseline'; Existing=@(); Bound=202; Count=1; Expected=$true },
    @{ Name='one_baseline_new'; Existing=@([pscustomobject]@{Id=101}); Bound=202; Count=1; Expected=$true },
    @{ Name='one_baseline_shared'; Existing=@([pscustomobject]@{Id=101}); Bound=101; Count=1; Expected=$false },
    @{ Name='unbound'; Existing=@(); Bound=0; Count=1; Expected=$false },
    @{ Name='shared_documents'; Existing=@(); Bound=202; Count=2; Expected=$false }
)
foreach ($case in $cases) {
    $baseline = @($case.Existing)
    . $baselineBlock
    if ($baselineIds.Count -ne $baseline.Count) { throw 'Baseline identity loss' }
    if (-not $baselineJson.Trim().StartsWith('[') -or -not $baselineJson.Trim().EndsWith(']')) { throw 'Baseline must serialize as a JSON array, including zero/one records' }
    $roundTrip = @(foreach ($record in (ConvertFrom-Json -InputObject $baselineJson)) { $record })
    $roundTripIds = @($roundTrip | ForEach-Object { [int]$_.Id })
    if ($roundTrip.Count -ne $baseline.Count -or ($roundTripIds -join ',') -ne ($baselineIds -join ',')) { throw 'Baseline JSON round-trip lost process identities' }
    $boundProcessId = $case.Bound
    $ownerProcess = [pscustomobject]@{Id=$case.Bound; ProcessName='Hwp'; StartTime=[datetime]'2020-01-01Z'}
    $initialDocumentCount = $case.Count
    $cleanupIdentity = $null
    try {
        . $bindingBlock
        # Simulate a failure in log/hash work immediately after ownership binding.
        throw 'SIMULATED_EVIDENCE_WRITE_FAILURE'
    } catch {
        if ($case.Expected -and $_.Exception.Message -ne 'SIMULATED_EVIDENCE_WRITE_FAILURE') { throw }
    } finally {
        if ($owned) { $cleanupIdentity = @($ownerId, $ownerStart) }
    }
    if ($owned -ne $case.Expected) { throw "Incorrect ownership: $($case.Name)" }
    if ($case.Expected -and ($null -eq $cleanupIdentity -or $cleanupIdentity[0] -ne $boundProcessId -or $cleanupIdentity[1] -ne $ownerProcess.StartTime)) { throw 'Bound cleanup identity was lost' }
    if (-not $case.Expected -and $null -ne $cleanupIdentity) { throw 'Unowned cleanup was authorized' }
}
Write-Output "OWNER_PREFLIGHT=PASS CASES=$($cases.Count) NATIVE_APPLICATION_LAUNCHED=False"
