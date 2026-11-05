param()

$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot

if (-not $env:CHECK_DB_URL) {
    $localConfigFiles = @()
    if ($env:LOCALAPPDATA) {
        $activePointer = Join-Path $env:LOCALAPPDATA 'SpacecubeTestMariaDBActive.txt'
        if (Test-Path -LiteralPath $activePointer) {
            $activeDirectory = (Get-Content -LiteralPath $activePointer -Raw).Trim()
            if (Test-Path -LiteralPath $activeDirectory -PathType Container) {
                $localConfigFiles += Join-Path $activeDirectory '.env'
            }
        }
        $localConfigFiles += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'SpacecubeTestMariaDB*') `
            -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName '.env' }
        $localConfigFiles = $localConfigFiles | Select-Object -Unique
    }

    foreach ($configFile in $localConfigFiles) {
        $entry = Get-Content -LiteralPath $configFile -ErrorAction SilentlyContinue |
            Where-Object { $_ -match '^\s*CHECK_DB_URL\s*=' } |
            Select-Object -First 1
        if ($entry) {
            $env:CHECK_DB_URL = ($entry -replace '^\s*CHECK_DB_URL\s*=\s*', '').Trim().Trim('"', "'")
            break
        }
    }
}

if (-not $env:CHECK_DB_URL) {
    throw 'CHECK_DB_URL을 찾지 못했습니다. 테스트 전용 로컬 spacecube_test 설정을 확인하세요.'
}

$pythonCandidates = @(
    (Join-Path $env:USERPROFILE 'miniforge3\envs\pro_1\python.exe'),
    (Join-Path $env:USERPROFILE 'Miniforge3\envs\pro_1\python.exe'),
    (Join-Path $env:USERPROFILE 'anaconda3\envs\pro_1\python.exe'),
    (Join-Path $env:USERPROFILE 'miniconda3\envs\pro_1\python.exe')
) | Select-Object -Unique
$pythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

Push-Location $backendRoot
try {
    $testTempRoot = Join-Path $env:TEMP "spacecube-pytest-$PID"
    New-Item -ItemType Directory -Path $testTempRoot -ErrorAction Stop | Out-Null
    $pytestArgs = @(
        '-m', 'pytest',
        '--basetemp', $testTempRoot,
        'tests\test_core_contracts.py',
        'tests\test_core_events.py',
        'tests\test_auth.py'
    )
    if ($pythonExe) {
        & $pythonExe @pytestArgs
    } elseif (Get-Command conda -ErrorAction SilentlyContinue) {
        conda run -n pro_1 --no-capture-output python @pytestArgs
    } else {
        throw 'pro_1 Python을 찾지 못했습니다. conda 환경 pro_1을 설치하거나 활성화하세요.'
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
