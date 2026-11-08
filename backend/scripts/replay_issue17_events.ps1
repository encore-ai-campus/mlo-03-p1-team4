param(
    [Parameter(Mandatory = $true)][string]$LogFile,
    [string]$SessionId,
    [int]$Accepted = -1,
    [int]$ExpectedUnique = -1
)

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

$backendDirectory = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:USERPROFILE "miniforge3\envs\pro_1\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "프로젝트 전용 Python 환경 pro_1을 찾지 못했습니다: $pythonPath"
}

$fullLogFile = [System.IO.Path]::GetFullPath($LogFile)
$temporaryRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd("\") + "\"
if (
    -not $fullLogFile.StartsWith($temporaryRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    (Split-Path -Leaf $fullLogFile) -ne "events.log" -or
    $fullLogFile -notmatch "\\issue17-events-[a-f0-9]{32}\\events\.log$"
) {
    throw "이슈 #17 전용 임시 폴더의 events.log만 재적재할 수 있습니다."
}
if (-not (Test-Path -LiteralPath $fullLogFile -PathType Leaf)) {
    throw "재적재할 이벤트 로그 파일이 없습니다."
}
if ($SessionId -and ($Accepted -lt 0 -or $ExpectedUnique -lt 0)) {
    throw "측정하려면 -Accepted와 -ExpectedUnique에 0 이상 값을 지정해야 합니다."
}

$mongoSecure = $null
$mongoPassword = $null
$resultPath = Join-Path (Split-Path -Parent $fullLogFile) "replay-results.txt"
try {
    $mongoSecure = Read-Host ".40 MongoDB root 비밀번호 (이전에 공유된 값은 재사용하지 않음)" -AsSecureString
    $mongoPassword = ConvertFrom-SecureInput -Value $mongoSecure
    if ([string]::IsNullOrWhiteSpace($mongoPassword)) {
        throw "MongoDB 비밀번호는 비워 둘 수 없습니다."
    }

    $mongoEncoded = [Uri]::EscapeDataString($mongoPassword)
    $env:MONGO_URL = "mongodb://root:$mongoEncoded@100.100.100.40:27017/?authSource=admin"
    $env:MONGO_DB = "space_rental_analytics_test"

    Push-Location $backendDirectory
    try {
        Set-Content -LiteralPath $resultPath -Value "" -Encoding UTF8
        foreach ($pass in 1..2) {
            Write-Output "재적재 $pass/2"
            $output = & $pythonPath -m scripts.replay_events --file $fullLogFile
            if ($LASTEXITCODE -ne 0) {
                throw "MongoDB 재적재 $pass/2가 완료되지 않았습니다."
            }
            $output | Write-Output
            Add-Content -LiteralPath $resultPath -Value $output -Encoding UTF8
        }
        if ($SessionId) {
            $output = & $pythonPath -m scripts.measure_event_reliability `
                --session-id $SessionId `
                --accepted $Accepted `
                --expected-unique $ExpectedUnique `
                --file $fullLogFile
            if ($LASTEXITCODE -ne 0) {
                throw "이벤트 신뢰성 측정이 완료되지 않았습니다."
            }
            $output | Write-Output
            Add-Content -LiteralPath $resultPath -Value $output -Encoding UTF8
        }
        Write-Output "측정 결과 파일: $resultPath"
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item Env:MONGO_URL -ErrorAction SilentlyContinue
    Remove-Item Env:MONGO_DB -ErrorAction SilentlyContinue
    if ($mongoSecure) { $mongoSecure.Dispose() }
    $mongoPassword = $null
}
