param()

$ErrorActionPreference = 'Stop'
$hwp = $null
. (Join-Path $PSScriptRoot 'hancom_com_guard.ps1')

try {
    $hwp = New-HancomGuardedObject -Hidden
    Write-Output 'REGISTERED=True'
}
finally {
    if ($null -ne $hwp) {
        Close-HancomGuardedObject -Hwp $hwp
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
