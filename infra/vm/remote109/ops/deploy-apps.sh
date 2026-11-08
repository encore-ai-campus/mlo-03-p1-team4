#!/usr/bin/env bash
# CLAUDE-CFG-002: 로컬 브랜치 local/server-e2e-1107을 109 api1·api2에만 배포한다.
# overlay의 대시보드·mon·gw 파일은 건드리지 않는다. 서버 operation 잠금이 비어 있을 때만 실행한다.
set -euo pipefail
SP=${SP:-$(mktemp -d)}   # 빌드 산출물 임시 폴더
WT=${WT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}   # 배포할 저장소 루트
UP=$(cd "$(dirname "$0")" && pwd)

# 0) 잠금 선점 (다른 작업이 잡고 있으면 중단)
ssh -o BatchMode=yes playdata 'cd ~/spacecube109 && mkdir .server-operation.lock && echo CLAUDE-CFG-002 > .server-operation.lock/owner' \
  || { echo "서버 operation 잠금이 이미 있어 중단"; exit 1; }

# 1) 실제 API 모드 프론트 빌드
(cd "$WT/frontend" && VITE_USE_MOCK=false npm run build >/dev/null)

# 2) 배포 묶음: 앱 + 집계 + 크롤러 + 생성기 (비밀값·테스트 제외)
tar --exclude='backend/.env*' --exclude='backend/logs' --exclude='backend/.venv' --exclude='*/tests' \
    --exclude='*/__pycache__' --exclude='crawler/data' -czf "$SP/payload-e2e.tar.gz" -C "$WT" \
    backend frontend/dist db/aggregate db/loaders db/seed crawler simulator
scp -q "$SP/payload-e2e.tar.gz" playdata:spacecube109/payload.tar.gz
scp -q "$UP/nginx.conf" playdata:spacecube109/claude-nginx.conf
scp -q "$UP/timers.snippet.sh" playdata:spacecube109/claude-timers.snippet.sh

# 3) overlay 앱 설정만 교체(백업) → config 묶음 재생성 → apps만 ansible
ssh -o BatchMode=yes playdata 'bash -s' <<'REMOTE'
set -euo pipefail
cd ~/spacecube109/overlay/infra/vm/lab
stamp=$(date +%Y%m%d-%H%M)
cp nginx.conf nginx.conf.bak-$stamp
cp install-role.sh install-role.sh.bak-$stamp
install -m 644 ~/spacecube109/claude-nginx.conf nginx.conf
if ! grep -q spacecube-complete.timer install-role.sh; then
  python3 - <<'PY'
from pathlib import Path
p = Path("install-role.sh"); s = p.read_text(encoding="utf-8").replace("\r\n", "\n")
snippet = Path.home().joinpath("spacecube109/claude-timers.snippet.sh").read_text(encoding="utf-8")
anchor = "  systemctl restart spacecube nginx prometheus-nginx-exporter\n"
assert s.count(anchor) == 1
p.write_text(s.replace(anchor, anchor + snippet), encoding="utf-8")
PY
fi
bash -n install-role.sh
python3 ../remote109/build_config.py
cd ../remote109
ANSIBLE_TIMEOUT=60 ansible-playbook -i inventory.yml site.yml --limit apps
REMOTE
echo "배포 완료. 확인 뒤 잠금 해제: ssh playdata 'rm -rf ~/spacecube109/.server-operation.lock'"
