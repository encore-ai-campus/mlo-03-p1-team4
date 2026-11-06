param(
 [ValidateSet('Student','Worker','Gathering','Explorer')][string]$Profile='Explorer',
 [ValidateSet('ReadOnly','Write')][string]$Mode='ReadOnly',
 [Parameter(Mandatory=$true)][string]$Dates,
 [int]$Users=0,[string]$Duration='2m',[string]$Gateway='http://192.168.0.218'
)
# 일일 페르소나 실행기. 스케줄 등록·계정 생성·DB 정리는 하지 않는다.
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$limits=@{Student=20;Worker=15;Gathering=10;Explorer=5}
if($Users -eq 0){$Users=$limits[$Profile]}
if($Users -lt 1 -or $Users -gt $limits[$Profile]){throw '일일 인원 상한을 넘었습니다. 한계 시험과 분리해 주세요.'}
if(-not $env:SYNTHETIC_API_KEY){throw 'SYNTHETIC_API_KEY가 필요합니다.'}
if($Mode -eq 'Write' -and $Profile -ne 'Explorer' -and (-not $env:LOCUST_ACCOUNTS_FILE -or -not (Test-Path -LiteralPath $env:LOCUST_ACCOUNTS_FILE))){throw '쓰기 모드는 보호된 LOCUST_ACCOUNTS_FILE이 필요합니다.'}
$uri=[uri]$Gateway
if(-not $uri.IsAbsoluteUri -or $uri.Scheme -notin @('http','https') -or $uri.UserInfo){throw '인증정보 없는 HTTP(S) 정문 주소를 지정하세요.'}
$pythonPath=Join-Path $env:USERPROFILE 'anaconda3/envs/pro_1/python.exe'
if(-not (Test-Path -LiteralPath $pythonPath)){throw 'pro_1 Python 경로를 확인하세요.'}
$reportRoot=Join-Path $repoRoot ('logs/persona-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+$Profile+'-'+$Mode+'-'+([guid]::NewGuid().ToString('N').Substring(0,8)))
New-Item -ItemType Directory -Path $reportRoot -Force|Out-Null
$old=@{}
foreach($name in @('LOCUST_ALLOW_WRITES','LOCUST_DATES','LOCUST_RUN_LOG','PYTHONPATH','PYTHONIOENCODING')){$old[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try{
 $env:LOCUST_ALLOW_WRITES=if($Mode -eq 'Write'){'1'}else{'0'}
 $env:LOCUST_DATES=$Dates
 $env:LOCUST_RUN_LOG=Join-Path $reportRoot 'daily-runs.jsonl'
 $env:PYTHONPATH=(Join-Path $repoRoot 'backend')+$(if($old.PYTHONPATH){[IO.Path]::PathSeparator+$old.PYTHONPATH})
 $env:PYTHONIOENCODING='utf-8'
 & $pythonPath -m locust -f (Join-Path $PSScriptRoot 'daily_locustfile.py') --headless --host $Gateway --users $Users --spawn-rate ([math]::Min(4,$Users)) --run-time $Duration --only-summary --csv (Join-Path $reportRoot 'locust') --html (Join-Path $reportRoot 'locust.html') $Profile
 $runExit=$LASTEXITCODE
 Write-Output "REPORT=$reportRoot"
}finally{foreach($name in $old.Keys){[Environment]::SetEnvironmentVariable($name,$old[$name],'Process')}}
exit $runExit
