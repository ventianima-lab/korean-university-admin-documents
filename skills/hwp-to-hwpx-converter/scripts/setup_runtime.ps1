[CmdletBinding()]
param(
    [string]$RuntimeRoot = "$env:USERPROFILE\.codex\runtimes\hwp-to-hwpx",
    [string]$PythonExe,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$packageVersion = '1.0.1'
$jreUrl = 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse'
$venvDir = Join-Path $RuntimeRoot 'venv'
$jreDir = Join-Path $RuntimeRoot 'jre'
$marker = Join-Path $RuntimeRoot 'runtime.json'

if ((Test-Path -LiteralPath $marker) -and -not $Force) {
    $state = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ((Test-Path -LiteralPath $state.converter) -and (Test-Path -LiteralPath $state.java)) {
        [pscustomobject]@{ status='ready'; runtime=$RuntimeRoot; converter=$state.converter; java=$state.java } | ConvertTo-Json -Compress
        exit 0
    }
}

if (-not $PythonExe) {
    $candidates = @(
        (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Get-Command py.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    ) | Where-Object { $_ } | Select-Object -Unique
    if (-not $candidates) { throw 'Python을 찾지 못했습니다. -PythonExe로 python.exe 절대경로를 지정하십시오.' }
    $PythonExe = $candidates[0]
}

New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
if ($Force -and (Test-Path -LiteralPath $venvDir)) { Remove-Item -LiteralPath $venvDir -Recurse -Force }

if (-not (Test-Path -LiteralPath (Join-Path $venvDir 'Scripts\python.exe'))) {
    if ([IO.Path]::GetFileName($PythonExe) -ieq 'py.exe') { & $PythonExe -3 -m venv $venvDir }
    else { & $PythonExe -m venv $venvDir }
    if ($LASTEXITCODE -ne 0) { throw "Python 가상환경 생성 실패: $LASTEXITCODE" }
}

$venvPython = Join-Path $venvDir 'Scripts\python.exe'
& $venvPython -m pip install --disable-pip-version-check --no-input "hwp2hwpx==$packageVersion"
if ($LASTEXITCODE -ne 0) { throw "hwp2hwpx 설치 실패: $LASTEXITCODE" }

$javaExe = Get-ChildItem -LiteralPath $jreDir -Filter java.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $javaExe) {
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ("hwp-to-hwpx-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    try {
        $archive = Join-Path $tempDir 'jre.zip'
        Invoke-WebRequest -Uri $jreUrl -OutFile $archive -UseBasicParsing
        if (Test-Path -LiteralPath $jreDir) { Remove-Item -LiteralPath $jreDir -Recurse -Force }
        New-Item -ItemType Directory -Path $jreDir | Out-Null
        Expand-Archive -LiteralPath $archive -DestinationPath $jreDir -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempDir) { Remove-Item -LiteralPath $tempDir -Recurse -Force }
    }
    $javaExe = Get-ChildItem -LiteralPath $jreDir -Filter java.exe -Recurse | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $javaExe) { throw '휴대용 Java 설치 후 java.exe를 찾지 못했습니다.' }
$converter = Join-Path $venvDir 'Scripts\hwp2hwpx.exe'
if (-not (Test-Path -LiteralPath $converter)) { throw 'hwp2hwpx 실행 파일을 찾지 못했습니다.' }

$state = [ordered]@{
    package = 'hwp2hwpx'
    version = $packageVersion
    converter = $converter
    java = $javaExe
    installed_at = (Get-Date).ToString('o')
}
$state | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
[pscustomobject]@{ status='installed'; runtime=$RuntimeRoot; converter=$converter; java=$javaExe } | ConvertTo-Json -Compress

