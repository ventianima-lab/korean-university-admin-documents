param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Output,
    [Parameter(Mandatory = $true)][ValidateRange(1, 10000)][int]$StartPhysicalPage,
    [Parameter(Mandatory = $true)][ValidateRange(1, 100)][int]$CopyCount
)

$ErrorActionPreference = 'Stop'
$sourceHwp = $null
$targetHwp = $null
$baselineHwpPids = @(Get-Process Hwp -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
. (Join-Path $PSScriptRoot 'hancom_com_guard.ps1')

function Compact-PageText {
    param([string]$Text, [int]$Limit = 240)
    $compact = (($Text -replace '[\r\n\t]+', ' ') -replace ' +', ' ').Trim()
    if ($compact.Length -gt $Limit) { return $compact.Substring(0, $Limit) }
    return $compact
}

if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw "Source file not found: $Source"
}
if (Test-Path -LiteralPath $Output) {
    throw "Output already exists; refusing overwrite: $Output"
}
$outputParent = Split-Path -Parent $Output
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw "Output directory not found: $outputParent"
}

try {
    $sourceHwp = New-HancomGuardedObject -Hidden -MessageBoxMode 0x111111
    $targetHwp = New-HancomGuardedObject -Hidden -MessageBoxMode 0x111111

    if (-not $sourceHwp.Open($Source, 'HWPX', 'forceopen:true')) {
        throw "Hancom failed to open source: $Source"
    }
    if (($StartPhysicalPage + $CopyCount - 1) -gt $sourceHwp.PageCount) {
        throw "Requested page range exceeds source PageCount=$($sourceHwp.PageCount)"
    }

    for ($page = $StartPhysicalPage; $page -lt ($StartPhysicalPage + $CopyCount); $page++) {
        $snippet = Compact-PageText -Text $sourceHwp.GetPageText($page - 1, 0xFFFFFFFF)
        Write-Output "SOURCE_PHYSICAL_PAGE=$page TEXT=$snippet"
    }

    [void]$sourceHwp.HAction.Run('MoveDocBegin')
    for ($move = 1; $move -lt $StartPhysicalPage; $move++) {
        if (-not $sourceHwp.HAction.Run('MovePageDown')) {
            throw "Could not move to physical page $($move + 1)"
        }
    }

    for ($offset = 0; $offset -lt $CopyCount; $offset++) {
        $page = $StartPhysicalPage + $offset
        $copy = $sourceHwp.HAction.Run('CopyPage')
        Start-Sleep -Milliseconds 400
        [void]$targetHwp.HAction.Run('MoveDocEnd')
        $paste = $targetHwp.HAction.Run('PastePage')

        if (-not $paste) {
            Start-Sleep -Milliseconds 600
            $copy = $sourceHwp.HAction.Run('CopyPage')
            Start-Sleep -Milliseconds 400
            [void]$targetHwp.HAction.Run('MoveDocEnd')
            $paste = $targetHwp.HAction.Run('PastePage')
            Write-Output "RETRY_PHYSICAL_PAGE=$page COPY=$copy PASTE=$paste"
        }

        if ($offset -eq 0) {
            [void]$targetHwp.HAction.Run('MoveDocBegin')
            if (-not $targetHwp.HAction.Run('DeletePage')) {
                throw 'Could not remove the target document initial blank page'
            }
            [void]$targetHwp.HAction.Run('MoveDocEnd')
        }

        if (-not $copy -or -not $paste) {
            throw "CopyPage/PastePage failed at physical page $page"
        }
        Write-Output "COPIED_PHYSICAL_PAGE=$page TARGET_PAGES=$($targetHwp.PageCount)"

        if ($offset -lt ($CopyCount - 1) -and -not $sourceHwp.HAction.Run('MovePageDown')) {
            throw "Could not move from physical page $page to $($page + 1)"
        }
    }

    if ($targetHwp.PageCount -ne $CopyCount) {
        throw "Unexpected target PageCount=$($targetHwp.PageCount); expected $CopyCount"
    }
    if (-not $targetHwp.SaveAs($Output, 'HWPX', '')) {
        throw "Hancom failed to save output: $Output"
    }

    for ($index = 0; $index -lt $targetHwp.PageCount; $index++) {
        $snippet = Compact-PageText -Text $targetHwp.GetPageText($index, 0xFFFFFFFF)
        Write-Output "OUTPUT_PAGE=$($index + 1) TEXT=$snippet"
    }
    $hash = Get-FileHash -LiteralPath $Output -Algorithm SHA256
    Write-Output "OUTPUT=$Output"
    Write-Output "PAGECOUNT=$($targetHwp.PageCount)"
    Write-Output "SHA256=$($hash.Hash)"
}
finally {
    if ($null -ne $sourceHwp) {
        Close-HancomGuardedObject -Hwp $sourceHwp
    }
    if ($null -ne $targetHwp) {
        Close-HancomGuardedObject -Hwp $targetHwp
    }
    Start-Sleep -Seconds 2
    $remainingNew = @(
        Get-Process Hwp -ErrorAction SilentlyContinue |
            Where-Object { $_.Id -notin $baselineHwpPids } |
            Select-Object -ExpandProperty Id
    )
    if ($remainingNew.Count) {
        Write-Warning "Hancom processes created by this run may remain: $($remainingNew -join ', ')"
    }
}
