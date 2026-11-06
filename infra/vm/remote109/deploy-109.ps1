param(
    [ValidateSet('Plan', 'Create', 'Configure', 'Status', 'On', 'Off')]
    [string]$Action = 'Plan',
    [string]$SourcePath = ''
)

# vmrest 자격증명은 기존 109 실습의 보호된 설정으로만 읽힌다. 이 실행기는 값을 받지 않는다.
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
if (-not $SourcePath) { $SourcePath = $repoRoot }
$bundle = Join-Path $env:TEMP 'spacecube109-automation.tar.gz'
& tar '--exclude=*/.terraform' '--exclude=*/terraform.tfstate*' '--exclude=*.tfplan' '--exclude=*/.env*' '--exclude=*/__pycache__' '--exclude=*/reports' -czf $bundle -C $repoRoot infra/vm/remote109 infra/vm/lab
if ($LASTEXITCODE -ne 0) { throw '공개 자동화 묶음 생성 실패' }
& ssh -o BatchMode=yes playdata 'mkdir -p ~/spacecube109/overlay'
& scp $bundle playdata:spacecube109/automation.tar.gz
& ssh -o BatchMode=yes playdata 'tar -xzf ~/spacecube109/automation.tar.gz -C ~/spacecube109/overlay; python3 ~/spacecube109/overlay/infra/vm/remote109/build_config.py'
if ($LASTEXITCODE -ne 0) { throw '109 자동화 파일 준비 실패' }
if ($Action -eq 'Configure') {
    $oldMock = $env:VITE_USE_MOCK
    try {
        $env:VITE_USE_MOCK = 'false'
        & npm --prefix (Join-Path $SourcePath 'frontend') run build
        if ($LASTEXITCODE -ne 0) { throw '실제 API 모드 프론트 빌드 실패' }
    }
    finally { $env:VITE_USE_MOCK = $oldMock }
    $payload = Join-Path $env:TEMP 'spacecube109-payload.tar.gz'
    & tar '--exclude=backend/.env*' '--exclude=backend/logs' '--exclude=backend/.venv' '--exclude=backend/tests' '--exclude=*/__pycache__' -czf $payload -C $SourcePath backend frontend/dist
    if ($LASTEXITCODE -ne 0) { throw '배포 묶음 생성 실패' }
    & scp $payload playdata:spacecube109/payload.tar.gz
    & ssh -o BatchMode=yes playdata 'test -s ~/.config/spacecube109/app/.env && cd ~/spacecube109/overlay/infra/vm/remote109 && ANSIBLE_TIMEOUT=60 ansible-playbook -i inventory.yml site.yml'
}
else {
    $operation = $Action.ToLowerInvariant()
    & ssh -o BatchMode=yes playdata "cd ~/spacecube109/overlay/infra/vm/remote109 && bash terraform.sh $operation"
}
if ($LASTEXITCODE -ne 0) { throw "109 $Action 실패" }
