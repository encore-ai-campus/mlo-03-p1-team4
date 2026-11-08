param(
    [string]$Gateway = 'http://192.168.0.218',
    [int]$Users = 5,
    [int]$SpawnRate = 5,
    [string]$Duration = '30s',
    [switch]$SkipBrowser,
    [switch]$SkipLoad
)

# 실행기는 이 PC에서 동작한다. 109에는 부하 생성기를 올리지 않는다.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$pythonPath = Join-Path $env:USERPROFILE 'anaconda3\envs\pro_1\python.exe'
$reportRoot = Join-Path $repoRoot ('logs\remote109-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null
$key = ssh -o BatchMode=yes playdata 'python3 /home/playdata/spacecube109/overlay/infra/vm/remote109/read_test_key.py'
if ($LASTEXITCODE -ne 0 -or -not $key) { throw '109의 합성 데이터 키를 읽지 못했습니다.' }
$env:SPACE_SYNTHETIC_KEY = $key.Trim()
$env:SPACE_GATEWAY = $Gateway
$env:SPACE_REPORT_DIR = $reportRoot
$env:SPACE_FRONTEND_DIR = Join-Path $repoRoot 'frontend'
$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $repoRoot 'backend'
try {
    if (-not $SkipBrowser) {
        & $pythonPath (Join-Path $PSScriptRoot 'run_browser.py')
        if ($LASTEXITCODE -ne 0) { throw 'Playwright 실제 API smoke 실패' }
    }
    if (-not $SkipLoad) {
        & $pythonPath -m locust -f (Join-Path $PSScriptRoot 'locustfile.py') --host $Gateway --headless --users $Users --spawn-rate $SpawnRate --run-time $Duration --only-summary --csv (Join-Path $reportRoot 'locust') --html (Join-Path $reportRoot 'locust.html')
        if ($LASTEXITCODE -ne 0) { throw 'Locust HTTP 오류 발생. 결과를 확인하세요.' }
    }
    Write-Output "결과 폴더: $reportRoot"
}
finally {
    Remove-Item Env:\SPACE_SYNTHETIC_KEY -ErrorAction SilentlyContinue
    $env:PYTHONPATH = $oldPythonPath
}
