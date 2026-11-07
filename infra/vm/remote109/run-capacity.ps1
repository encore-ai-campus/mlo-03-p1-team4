param([ValidateRange(1,800)][int[]]$Stages = @(50,100,200,400,800), [ValidateRange(10,600)][int]$Seconds = 60)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$report = Join-Path $root ('logs/locust-capacity-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $report -Force | Out-Null
$rows = @()
foreach ($users in $Stages) {
    $start = [DateTimeOffset]::Now
    ssh -o BatchMode=yes playdata 'python3 /home/playdata/spacecube109/overlay/infra/vm/remote109/verify_services.py' | Set-Content -Encoding UTF8 (Join-Path $report "before-$users.json")
    if ($LASTEXITCODE -ne 0) { throw 'SSH 사전 서비스 검사 실패' }
    $runner = Join-Path $PSScriptRoot 'run-experiments.ps1'
    $argsList = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$runner,'-SkipBrowser','-Users',$users,'-SpawnRate',([math]::Max(5,[math]::Ceiling($users/10))),'-Duration',($Seconds.ToString()+'s'))
    $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $argsList -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $report "locust-$users.log") -RedirectStandardError (Join-Path $report "locust-$users.stderr.log")
    $code = $proc.ExitCode
    $latest = Get-ChildItem (Join-Path $root 'logs/remote109-*') -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $csv = Import-Csv (Join-Path $latest.FullName 'locust_stats.csv') | Where-Object Name -eq 'Aggregated'
    $peak = (Import-Csv (Join-Path $latest.FullName 'locust_stats_history.csv') | Measure-Object -Property 'User Count' -Maximum).Maximum
    $failRate = [double]$csv.'Failure Count' / [math]::Max(1,[double]$csv.'Request Count')
    $row = [pscustomobject]@{users=$users;actual_peak_users=$peak;seconds=$Seconds;requests=$csv.'Request Count';failures=$csv.'Failure Count';rps=$csv.'Requests/s';p95_ms=$csv.'95%';p99_ms=$csv.'99%';average_ms=$csv.'Average Response Time';passed=($peak -ge $users -and $code -eq 0 -and $failRate -le 0.01 -and [double]$csv.'95%' -le 500);report=$latest.FullName;started=$start.ToString('o');ended=[DateTimeOffset]::Now.ToString('o')}
    $rows += $row
    $rows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $report 'summary.csv')
    $queries = @{cpu='100*(1-avg by(server)(rate(node_cpu_seconds_total{job="nodes",mode="idle"}[1m])))';memory='100*(1-node_memory_MemAvailable_bytes{job="nodes"}/node_memory_MemTotal_bytes{job="nodes"})'}
    foreach($name in $queries.Keys) {
        $uri='http://192.168.0.217:9090/api/v1/query_range?query='+[uri]::EscapeDataString($queries[$name])+'&start='+$start.ToUnixTimeSeconds()+'&end='+[DateTimeOffset]::Now.ToUnixTimeSeconds()+'&step=15'
        Invoke-RestMethod -Uri $uri -TimeoutSec 10 | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 (Join-Path $report "$name-$users.json")
    }
    if (-not $row.passed) { Write-Output '오류율 1% 또는 p95 500ms 기준 초과로 상승 중지'; break }
}
ssh -o BatchMode=yes playdata 'python3 /home/playdata/spacecube109/overlay/infra/vm/remote109/verify_services.py' 2> (Join-Path $report 'after.stderr.log') | Set-Content -Encoding UTF8 (Join-Path $report 'after.json')
$postCheckExit = $LASTEXITCODE
$overallPassed = ($rows.Count -gt 0 -and @($rows | Where-Object { -not $_.passed }).Count -eq 0 -and $postCheckExit -eq 0)
@{passed=$overallPassed;post_check_exit=$postCheckExit;criteria='error <=1%; p95 <=500ms; target users reached';scope='GET only, preliminary';stages=$Stages;seconds=$Seconds} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $report 'verdict.json')
$rows | Format-Table users,requests,failures,rps,p95_ms,passed
Write-Output "REPORT=$report"





& (Join-Path $env:USERPROFILE 'anaconda3/envs/pro_1/python.exe') (Join-Path $PSScriptRoot 'summarize_capacity.py') $report
if (-not $overallPassed) { exit 1 }
