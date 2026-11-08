$ErrorActionPreference = "Stop"

function ConvertFrom-SecureInput {
    param([Parameter(Mandatory = $true)][System.Security.SecureString]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function New-TemporaryToken {
    $bytes = New-Object byte[] 48
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    ([BitConverter]::ToString($bytes)).Replace("-", "")
}

$backendDirectory = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:USERPROFILE "miniforge3\envs\pro_1\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "프로젝트 전용 Python 환경 pro_1을 찾지 못했습니다: $pythonPath"
}

$mysqlSecure = $null
$mongoSecure = $null
$mysqlPassword = $null
$mongoPassword = $null
$temporaryVariables = @(
    "DB_WRITE_URL",
    "DB_READ_URL",
    "MONGO_URL",
    "MONGO_DB",
    "JWT_SECRET",
    "INTERNAL_API_KEY",
    "SYNTHETIC_API_KEY",
    "LOG_DIR",
    "SERVER_NAME",
    "BOOKING_PAST_DAYS",
    "BOOKING_FUTURE_DAYS",
    "TODAY_OVERRIDE"
)

try {
    $mysqlSecure = Read-Host "MariaDB issue17_runner 비밀번호 (화면에 표시되지 않음)" -AsSecureString
    $mongoSecure = Read-Host ".40 MongoDB root 비밀번호 (이전에 공유된 값은 재사용하지 말고 새 값 입력)" -AsSecureString
    $mysqlPassword = ConvertFrom-SecureInput -Value $mysqlSecure
    $mongoPassword = ConvertFrom-SecureInput -Value $mongoSecure

    if ([string]::IsNullOrWhiteSpace($mysqlPassword) -or [string]::IsNullOrWhiteSpace($mongoPassword)) {
        throw "DB 비밀번호는 비워 둘 수 없습니다."
    }

    $mysqlEncoded = [Uri]::EscapeDataString($mysqlPassword)
    $mongoEncoded = [Uri]::EscapeDataString($mongoPassword)
    $env:DB_WRITE_URL = "mysql+pymysql://issue17_runner:$mysqlEncoded@100.100.100.31:3306/spacecube_test?charset=utf8mb4"
    $env:DB_READ_URL = $env:DB_WRITE_URL
    $env:MONGO_URL = "mongodb://root:$mongoEncoded@100.100.100.40:27017/?authSource=admin"
    $env:MONGO_DB = "space_rental_analytics_test"
    $env:JWT_SECRET = New-TemporaryToken
    $env:INTERNAL_API_KEY = New-TemporaryToken
    $env:SYNTHETIC_API_KEY = New-TemporaryToken
    $env:SERVER_NAME = "issue17-test"
    $env:BOOKING_PAST_DAYS = "365"
    $env:BOOKING_FUTURE_DAYS = "365"
    $env:TODAY_OVERRIDE = ""

    $logDirectory = Join-Path $env:TEMP ("issue17-events-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $logDirectory | Out-Null
    $env:LOG_DIR = $logDirectory

    $stdoutPath = Join-Path $logDirectory "api.stdout.log"
    $stderrPath = Join-Path $logDirectory "api.stderr.log"
    $apiProcess = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002") `
        -WorkingDirectory $backendDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    $health = $null
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if ($apiProcess.HasExited) {
            throw "시험 API가 시작 과정에서 종료됐습니다. 임시 로그 폴더의 서버 로그를 확인하세요."
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -TimeoutSec 2
            break
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $health) {
        Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue
        throw "시험 API가 20초 안에 준비되지 않았습니다. 임시 로그 폴더의 서버 로그를 확인하세요."
    }

    Write-Output "시험 API 프로세스를 시작했습니다."
    Write-Output "주소: http://127.0.0.1:8002 (이 PC에서만 접근 가능)"
    Write-Output "PID: $($apiProcess.Id)"
    Write-Output "저장소 상태: $($health | ConvertTo-Json -Compress)"
    Write-Output "임시 로그 폴더: $logDirectory"
    Write-Output "합성 공간 등록용 X-Internal-Key: $env:INTERNAL_API_KEY"
    Write-Output "합성 데이터용 X-Synthetic-Key: $env:SYNTHETIC_API_KEY"
    Write-Output "시험이 끝나면 Stop-Process -Id $($apiProcess.Id)로 API를 종료하세요."
}
finally {
    foreach ($name in $temporaryVariables) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    }
    if ($mysqlSecure) { $mysqlSecure.Dispose() }
    if ($mongoSecure) { $mongoSecure.Dispose() }
    $mysqlPassword = $null
    $mongoPassword = $null
}
