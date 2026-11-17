param(
    [switch]$Run,
    [switch]$Headed,
    [ValidateSet('read','write')][string]$Mode = 'read',
    [ValidateSet('all','study','work','photo','workshop','gathering','browse')][string]$Persona = 'all',
    [string]$Gateway = 'http://192.168.0.218',
    # 사용자마다 화면 영상(videos/<페르소나>-<모드>.webm)을 남긴다. 기본 동작 간격 400ms(-SlowMo로 변경).
    [switch]$Record,
    # 6명을 동시에 실행한다(창 6개). 없으면 1명씩 차례로.
    [switch]$Parallel,
    [int]$SlowMo = -1
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$cli = Join-Path $PSScriptRoot 'node_modules/@playwright/test/cli.js'
if (-not (Test-Path -LiteralPath $cli)) { throw '먼저 frontend에서 npm ci를 실행하세요.' }
$values = @{
    PERSONA_RUN = $(if ($Run) { '1' } else { '0' })
    PERSONA_MODE = $Mode
    PERSONA_FILTER = $Persona
    E2E_BASE_URL = $Gateway
    PERSONA_RECORD = $(if ($Record) { '1' } else { '0' })
    PERSONA_PARALLEL = $(if ($Parallel) { '1' } else { '0' })
    PERSONA_SLOWMO = $(if ($SlowMo -ge 0) { [string]$SlowMo } else { '' })
    PERSONA_REPORT_DIR = (Join-Path $root ('logs/playwright-personas/' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)))
}
$saved = @{}
foreach ($key in $values.Keys) { $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
try {
    foreach ($key in $values.Keys) { [Environment]::SetEnvironmentVariable($key, $values[$key], 'Process') }
    $arguments = @($cli, 'test', '--config', (Join-Path $PSScriptRoot 'playwright.persona.config.js'))
    if (-not $Run) { $arguments += '--list' }
    if ($Headed) { $arguments += '--headed' }
    & node @arguments
    $runExit = $LASTEXITCODE
    Write-Output "REPORT=$($values.PERSONA_REPORT_DIR)"
} finally {
    foreach ($key in $saved.Keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
}
exit $runExit
