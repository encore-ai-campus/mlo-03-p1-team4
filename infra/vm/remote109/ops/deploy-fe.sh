#!/usr/bin/env bash
# 프론트 빌드만 api1·api2의 /var/www/spacecube에 교체한다(서비스 재시작 없음). 잠금이 비어 있을 때만.
set -euo pipefail
SP=${SP:-$(mktemp -d)}   # 빌드 산출물 임시 폴더
WT=${WT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}   # 배포할 저장소 루트
ssh -o BatchMode=yes playdata 'cd ~/spacecube109 && mkdir .server-operation.lock && echo CLAUDE-FE-004 > .server-operation.lock/owner' \
  || { echo "잠금이 있어 중단"; exit 1; }
trap 'ssh -o BatchMode=yes playdata "test \"\$(cat ~/spacecube109/.server-operation.lock/owner 2>/dev/null)\" = CLAUDE-FE-004 && rm -rf ~/spacecube109/.server-operation.lock"' EXIT
(cd "$WT/frontend" && VITE_USE_MOCK=false npm run build >/dev/null)
tar -czf "$SP/fe-dist.tgz" -C "$WT/frontend/dist" .
scp -q "$SP/fe-dist.tgz" playdata:/tmp/fe-dist.tgz
ssh -o BatchMode=yes playdata 'bash -s' <<'REMOTE'
set -euo pipefail
K=~/.config/spacecube109
for ip in 214 215; do
  scp -q -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 /tmp/fe-dist.tgz ubuntu@192.168.219.$ip:/tmp/fe-dist.tgz
  ssh -o BatchMode=yes -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 ubuntu@192.168.219.$ip \
    'set -e; d=/tmp/fe-new; rm -rf $d; mkdir $d; tar -xzf /tmp/fe-dist.tgz -C $d; sudo cp -a $d/. /var/www/spacecube/; rm -rf $d /tmp/fe-dist.tgz; grep -o "assets/index-[^\"]*\.js" /var/www/spacecube/index.html | head -1'
done
rm -f /tmp/fe-dist.tgz
REMOTE
echo FE_DEPLOYED
