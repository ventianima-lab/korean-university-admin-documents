param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Output,
    [Parameter(Mandatory = $true)][ValidateRange(1, 10000)][int]$StartPhysicalPage,
    [Parameter(Mandatory = $true)][ValidateRange(1, 100)][int]$CopyCount,
    [string]$SecurityModuleName = 'FilePathCheckerModuleExample'
)

$ErrorActionPreference = 'Stop'
$sourceHwp = $null
$targetHwp = $null
$baselineHwpPids = @(Get-Process Hwp -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)

function Set-AutoMessageResponse {
    param($Hwp)
    # Affirmative answers for ordinary dialogs within the skill's standing
    # authorization. File-path approval is handled by the official module.
    [void]$Hwp.SetMessageBoxMode(0x111111)
}

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
    $sourceHwp = New-Object -ComObject HWPFrame.HwpObject
    $targetHwp = New-Object -ComObject HWPFrame.HwpObject

    foreach ($hwp in @($sourceHwp, $targetHwp)) {
        $registered = $hwp.RegisterModule('FilePathCheckDLL', $SecurityModuleName)
        if (-not $registered) {
            throw "Hancom file-path security module registration failed: $SecurityModuleName"
        }
        Set-AutoMessageResponse -Hwp $hwp
        try { $hwp.XHwpWindows.Item(0).Visible = $false } catch {}
    }

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
    if ($sourceHwp) {
        try { [void]$sourceHwp.SetMessageBoxMode(0xFFFFFF) } catch {}
        try { $sourceHwp.Quit() } catch {}
    }
    if ($targetHwp) {
        try { [void]$targetHwp.SetMessageBoxMode(0xFFFFFF) } catch {}
        try { $targetHwp.Quit() } catch {}
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
