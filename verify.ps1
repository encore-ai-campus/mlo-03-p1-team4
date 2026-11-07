# 커밋 전 전체 검증: 파이썬(ruff · pytest) + 프론트(npm run verify)
#   powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1          # 검사만
#   powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1 -Fix     # 고칠 수 있는 건 고치고 검사
#   powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1 -E2E     # 화면 흐름(Playwright)까지
param([switch]$Fix, [switch]$E2E)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# conda를 셸에서 못 찾아도 돌도록 pro_1 환경의 python을 직접 부른다 (AGENTS.md 명령 참고)
$py = Join-Path $env:USERPROFILE 'anaconda3\envs\pro_1\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$failed = @()
function Step($name, [scriptblock]$run) {
  Write-Host "`n== $name" -ForegroundColor Cyan
  & $run
  if ($LASTEXITCODE -ne 0) { $script:failed += $name }
}

if ($Fix) {
  Step 'ruff 자동 수정' { & $py -m ruff check . --fix }
  Step 'ruff 포맷' { & $py -m ruff format . }
  Step '프론트 자동 수정' { npm --prefix frontend run fix }
  $failed = @()  # 고친 뒤 아래 검사 결과만 본다
}

Step 'ruff 린트' { & $py -m ruff check . }
Step 'ruff 포맷 확인' { & $py -m ruff format --check . }

# 백엔드·DB 테스트 파일이 생기면 pytest를 돌린다
$tests = Get-ChildItem tests, backend\tests, db\tests -Recurse -Include 'test_*.py', '*_test.py' -ErrorAction SilentlyContinue
if ($tests) { Step 'pytest' { & $py -m pytest -q } } else { Write-Host "`n== pytest: 테스트 파일 없음, 건너뜀" -ForegroundColor DarkGray }

Step '프론트 verify (린트·색 검사·단위 테스트·빌드)' { npm --prefix frontend run verify }
if ($E2E) { Step '프론트 E2E (Playwright + axe)' { npm --prefix frontend run test:e2e } }

if ($failed.Count) {
  Write-Host "`n실패: $($failed -join ', ')" -ForegroundColor Red
  exit 1
}
Write-Host "`n모두 통과" -ForegroundColor Green
