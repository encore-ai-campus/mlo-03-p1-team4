#!/usr/bin/env bash
# 2단계: PR #91 109 안내대로 api1·api2에 독립 health(8001)와 Nginx /health·/api/health만 적용한다.
# 사용: verify-step2-health.sh apply | rollback   (playdata에서 실행, health_app.py는 ~/spacecube109/claude-health_app.py)
set -euo pipefail
K=~/.config/spacecube109
S() { ssh -o BatchMode=yes -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 "ubuntu@192.168.219.$1" "$2"; }
MODE=${1:?apply|rollback}
for pair in "215 api2" "214 api1"; do
  set -- $pair; ip=$1; role=$2
  if [ "$MODE" = apply ]; then
    scp -q -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 ~/spacecube109/claude-health_app.py ubuntu@192.168.219.$ip:claude-health_app.py
    S $ip 'set -e
      sudo cp -n /etc/nginx/conf.d/spacecube.conf /etc/nginx/conf.d/spacecube.conf.bak-verify006 2>/dev/null || true
      sudo install -d -o root -g adm -m 0750 /opt/spacecube/deploy/health
      sudo install -o root -g adm -m 0640 ~/claude-health_app.py /opt/spacecube/deploy/health/health_app.py; rm -f ~/claude-health_app.py
      sudo tee /etc/systemd/system/spacecube-health.service >/dev/null <<UNIT
[Unit]
Description=Spacecube isolated health check (109)
After=network.target spacecube.service
BindsTo=spacecube.service
PartOf=spacecube.service

[Service]
Type=simple
User=spacecube
Group=adm
WorkingDirectory=/opt/spacecube/backend
EnvironmentFile=/etc/spacecube/.env
Environment=PYTHONPATH=/opt/spacecube/backend
Environment=LOG_DIR=/opt/spacecube/backend/logs
ExecStart=/opt/spacecube/venv/bin/uvicorn health_app:app --app-dir /opt/spacecube/deploy/health --host 127.0.0.1 --port 8001 --workers 1 --timeout-keep-alive 1 --no-access-log
Restart=on-failure
RestartSec=2

[Install]
WantedBy=spacecube.service
UNIT
      sudo systemctl daemon-reload; sudo systemctl enable spacecube-health.service >/dev/null 2>&1; sudo systemctl restart spacecube-health.service
      curl --retry 5 --retry-delay 1 --retry-connrefused --max-time 2 -fsS http://127.0.0.1:8001/health; echo
      sudo python3 - <<PY
from pathlib import Path
p = Path("/etc/nginx/conf.d/spacecube.conf"); s = p.read_text()
start = s.index("    location = /health {"); end = s.index("}", start) + 1
block = "    location = /health {\n        proxy_pass http://127.0.0.1:8001/health;\n    }\n    location = /api/health {\n        proxy_pass http://127.0.0.1:8001/health;\n    }"
if "location = /api/health" not in s:
    s = s[:start] + block + s[end:]
p.write_text(s)
PY
      sudo nginx -t 2>&1 | tail -1; sudo systemctl reload nginx
      for u in /health /api/health; do printf "%s " $u; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1$u; done'
  else
    S $ip 'set -e
      if [ -f /etc/nginx/conf.d/spacecube.conf.bak-verify006 ]; then sudo cp /etc/nginx/conf.d/spacecube.conf.bak-verify006 /etc/nginx/conf.d/spacecube.conf; fi
      sudo nginx -t 2>&1 | tail -1; sudo systemctl reload nginx
      sudo systemctl disable --now spacecube-health.service >/dev/null 2>&1 || true
      curl -s -o /dev/null -w "/health %{http_code}\n" http://127.0.0.1/health'
  fi
  echo "== $role $MODE 완료"
done
