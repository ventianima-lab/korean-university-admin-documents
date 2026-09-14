param()

$ErrorActionPreference = 'Stop'
$guardName = 'hancom_com_guard.ps1'
$selfName = 'test_hancom_guard_contract.ps1'
$violations = [System.Collections.Generic.List[string]]::new()

foreach ($file in Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' -File) {
    if ($file.Name -eq $selfName) {
        continue
    }

    $text = Get-Content -LiteralPath $file.FullName -Raw
    if ($file.Name -ne $guardName -and $text -match 'New-Object\s+-ComObject\s+HWPFrame\.HwpObject') {
        $violations.Add("$($file.Name): direct HWPFrame.HwpObject construction")
    }
    if ($file.Name -ne $guardName -and $text -match '\.RegisterModule\s*\(') {
        $violations.Add("$($file.Name): direct RegisterModule call")
    }
    if ($text -match 'FilePathCheckerModule(?!Example)') {
        $violations.Add("$($file.Name): shortened security-module name")
    }

    $usesFileAccess = $text -match '\.(?:Open|Save|SaveAs)\s*\('
    if ($usesFileAccess -and (
        $text -notmatch 'hancom_com_guard\.ps1' -or
        $text -notmatch 'New-HancomGuardedObject'
    )) {
        $violations.Add("$($file.Name): file access without the shared guard")
    }
}

if ($violations.Count) {
    throw "Hancom automation guard contract failed:`n$($violations -join "`n")"
}

Write-Output "GUARD_CONTRACT=PASS FILES=$((Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' -File).Count)"
