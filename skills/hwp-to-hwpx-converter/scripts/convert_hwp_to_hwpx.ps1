[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [string]$RuntimeRoot = "$env:USERPROFILE\.codex\runtimes\hwp-to-hwpx",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Test-HwpxPackage([string]$Path) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entries = @($zip.Entries)
        if ($entries.Count -eq 0 -or $entries[0].FullName -ne 'mimetype') { throw 'HWPX의 첫 ZIP 항목이 mimetype이 아닙니다.' }
        $required = @('mimetype','Contents/header.xml','Contents/section0.xml','Contents/content.hpf')
        foreach ($name in $required) {
            if (-not ($entries.FullName -contains $name)) { throw "HWPX 필수 항목 누락: $name" }
        }
        $mimeEntry = $entries | Where-Object FullName -eq 'mimetype' | Select-Object -First 1
        $reader = New-Object IO.StreamReader($mimeEntry.Open(), [Text.Encoding]::UTF8, $true)
        try { $mime = $reader.ReadToEnd() } finally { $reader.Dispose() }
        if ($mime -ne 'application/hwp+zip') { throw "HWPX mimetype 불일치: $mime" }
        foreach ($entry in $entries | Where-Object { $_.FullName -match '\.(xml|hpf)$' }) {
            $stream = $entry.Open()
            try {
                $settings = New-Object Xml.XmlReaderSettings
                $settings.DtdProcessing = [Xml.DtdProcessing]::Prohibit
                $xml = [Xml.XmlReader]::Create($stream, $settings)
                try { while ($xml.Read()) {} } finally { $xml.Dispose() }
            } finally { $stream.Dispose() }
        }
        return $true
    } finally { $zip.Dispose() }
}

$source = (Resolve-Path -LiteralPath $InputPath).Path
$target = [IO.Path]::GetFullPath($OutputPath)
if ([IO.Path]::GetExtension($target) -ine '.hwpx') { throw 'OutputPath 확장자는 .hwpx여야 합니다.' }
if ($source -ieq $target) { throw '원본 덮어쓰기는 허용하지 않습니다. 별도 OutputPath를 지정하십시오.' }
if ((Test-Path -LiteralPath $target) -and -not $Force) { throw "출력 파일이 이미 있습니다: $target (덮어쓰려면 -Force)" }
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null

$bytes = [IO.File]::ReadAllBytes($source)
if ($bytes.Length -lt 8) { throw '입력 파일이 너무 작습니다.' }
$isOle = ($bytes[0..7] -join ',') -eq '208,207,17,224,161,177,26,225'
$isZip = $bytes[0] -eq 80 -and $bytes[1] -eq 75 -and $bytes[2] -eq 3 -and $bytes[3] -eq 4
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash

if ($isZip) {
    Test-HwpxPackage $source | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force:$Force
    $status = 'validated-copy'
}
elseif ($isOle) {
    $stateFile = Join-Path $RuntimeRoot 'runtime.json'
    if (-not (Test-Path -LiteralPath $stateFile)) { throw "런타임이 없습니다. 먼저 setup_runtime.ps1을 실행하십시오: $RuntimeRoot" }
    $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath $state.converter)) { throw "변환기 없음: $($state.converter)" }
    if (-not (Test-Path -LiteralPath $state.java)) { throw "Java 없음: $($state.java)" }
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ("hwp-to-hwpx-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    try {
        $staged = Join-Path $tempDir 'source.hwp'
        $outDir = Join-Path $tempDir 'out'
        New-Item -ItemType Directory -Path $outDir | Out-Null
        Copy-Item -LiteralPath $source -Destination $staged
        $oldPath = $env:Path
        $oldJavaHome = $env:JAVA_HOME
        try {
            $javaBin = [IO.Path]::GetDirectoryName($state.java)
            $env:JAVA_HOME = [IO.Path]::GetDirectoryName($javaBin)
            $env:Path = $javaBin + ';' + $oldPath
            & $state.converter -o $outDir $staged
            if ($LASTEXITCODE -ne 0) { throw "hwp2hwpx 변환 실패: $LASTEXITCODE" }
        } finally {
            $env:Path = $oldPath
            $env:JAVA_HOME = $oldJavaHome
        }
        $generated = Join-Path $outDir 'source.hwpx'
        if (-not (Test-Path -LiteralPath $generated)) { throw '변환 결과 source.hwpx를 찾지 못했습니다.' }
        Test-HwpxPackage $generated | Out-Null
        Copy-Item -LiteralPath $generated -Destination $target -Force:$Force
    }
    finally {
        if (Test-Path -LiteralPath $tempDir) { Remove-Item -LiteralPath $tempDir -Recurse -Force }
    }
    $status = 'converted'
}
else { throw '지원하지 않는 파일 시그니처입니다. OLE HWP 또는 ZIP HWPX가 아닙니다.' }

Test-HwpxPackage $target | Out-Null
$targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
[pscustomobject]@{
    status = $status
    source = $source
    output = $target
    source_sha256 = $sourceHash
    output_sha256 = $targetHash
    source_bytes = (Get-Item -LiteralPath $source).Length
    output_bytes = (Get-Item -LiteralPath $target).Length
} | ConvertTo-Json -Compress

