param()

$ErrorActionPreference = 'Stop'
$hwp = $null

try {
    $hwp = New-Object -ComObject HWPFrame.HwpObject
    $registered = $hwp.RegisterModule(
        'FilePathCheckDLL',
        'FilePathCheckerModuleExample'
    )
    if (-not $registered) {
        throw 'Hancom file-path security module registration failed: FilePathCheckerModuleExample'
    }
    Write-Output 'REGISTERED=True'
}
finally {
    if ($null -ne $hwp) {
        try { $hwp.Quit() } catch {}
        try {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($hwp)
        }
        catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
