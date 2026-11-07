#!/usr/bin/env bash
# 로컬 브랜치를 api2 → api1 순서로 한 대씩 배포한다. 한 대가 health ok가 돼야 다음으로 넘어간다.
# overlay 설정(config.tar.gz)은 이미 반영된 것을 그대로 쓴다. 잠금이 비어 있을 때만 실행.
set -euo pipefail
SP=${SP:-$(mktemp -d)}   # 빌드 산출물 임시 폴더
WT=${WT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}   # 배포할 저장소 루트
ssh -o BatchMode=yes playdata 'cd ~/spacecube109 && mkdir .server-operation.lock && echo CLAUDE-DEPLOY-005 > .server-operation.lock/owner' \
  || { echo "잠금이 있어 중단"; exit 1; }
trap 'ssh -o BatchMode=yes playdata "test \"\$(cat ~/spacecube109/.server-operation.lock/owner 2>/dev/null)\" = CLAUDE-DEPLOY-005 && rm -rf ~/spacecube109/.server-operation.lock"' EXIT
(cd "$WT/frontend" && VITE_USE_MOCK=false npm run build >/dev/null)
tar --exclude='backend/.env*' --exclude='backend/logs' --exclude='backend/.venv' --exclude='*/tests' \
    --exclude='*/__pycache__' --exclude='crawler/data' -czf "$SP/payload-e2e.tar.gz" -C "$WT" \
    backend frontend/dist db/aggregate db/loaders db/seed crawler simulator
scp -q "$SP/payload-e2e.tar.gz" playdata:spacecube109/payload.tar.gz
ssh -o BatchMode=yes playdata 'bash -s' <<'REMOTE'
set -euo pipefail
K=~/.config/spacecube109
S() { ssh -o BatchMode=yes -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 "ubuntu@192.168.219.$1" "$2"; }
python3 ~/spacecube109/overlay/infra/vm/remote109/build_config.py >/dev/null
for pair in "215 api2" "214 api1"; do
  set -- $pair; ip=$1; role=$2
  echo "== $role 배포"
  scp -q -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 ~/spacecube109/payload.tar.gz ubuntu@192.168.219.$ip:claude-payload.tgz
  scp -q -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 ~/spacecube109/config.tar.gz ubuntu@192.168.219.$ip:claude-config.tgz
  S $ip "set -e; sudo install -m 644 ~/claude-payload.tgz /tmp/payload.tar.gz; sudo install -m 644 ~/claude-config.tgz /tmp/spacecube-config.tar.gz; rm -f ~/claude-payload.tgz ~/claude-config.tgz; sudo mkdir -p /tmp/lab; sudo tar -xzf /tmp/spacecube-config.tar.gz -C /tmp/lab; sudo bash /tmp/lab/install-role.sh $role > /tmp/claude-install-$role.log 2>&1; tail -1 /tmp/claude-install-$role.log"
  ok=0
  for t in $(seq 1 30); do
    if S $ip "curl -s -m 2 http://127.0.0.1:8000/health" | grep -q '"status":"ok"'; then ok=1; break; fi
    sleep 2
  done
  [ $ok = 1 ] || { echo "$role health 실패 — 중단(다음 서버는 배포하지 않음)"; exit 1; }
  S $ip "grep -nE 'pool_size|max_overflow' /opt/spacecube/backend/app/core/db.py | tr '\n' ' '; grep -o 'assets/index-[^\"]*\.js' /var/www/spacecube/index.html | head -1"
  echo "$role health ok"
  sleep 5
done
REMOTE
echo ROLLING_DONE
