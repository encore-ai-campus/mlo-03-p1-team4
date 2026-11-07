#!/usr/bin/env bash
# 3단계: gw HAProxy에 서버별 maxconn 50, timeout queue 5s만 추가한다(PR #91 값). 나머지 109 설정은 유지.
# 사용: verify-step3-haproxy.sh apply | rollback   (playdata에서 실행)
set -euo pipefail
K=~/.config/spacecube109
S() { ssh -o BatchMode=yes -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 "ubuntu@192.168.219.218" "$1"; }
if [ "${1:?apply|rollback}" = apply ]; then
  S 'set -e
    sudo cp -n /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.bak-verify006
    sudo python3 - <<PY
from pathlib import Path
p = Path("/etc/haproxy/haproxy.cfg"); s = p.read_text()
if "timeout queue" not in s:
    s = s.replace("    timeout server 30s\n", "    timeout server 30s\n    timeout queue 5s\n", 1)
for name in ("api1 192.168.219.214:80", "api2 192.168.219.215:80"):
    old = f"    server {name} check"
    assert s.count(old) == 1, old
    s = s.replace(old, f"    server {name} maxconn 50 check")
Path("/tmp/haproxy-verify006.cfg").write_text(s)
PY
    sudo haproxy -c -f /tmp/haproxy-verify006.cfg
    sudo install -m 644 /tmp/haproxy-verify006.cfg /etc/haproxy/haproxy.cfg
    sudo systemctl reload haproxy
    grep -nE "timeout queue|maxconn" /etc/haproxy/haproxy.cfg'
else
  S 'set -e; sudo cp /etc/haproxy/haproxy.cfg.bak-verify006 /etc/haproxy/haproxy.cfg; sudo haproxy -c -f /etc/haproxy/haproxy.cfg; sudo systemctl reload haproxy; grep -c maxconn /etc/haproxy/haproxy.cfg || true'
fi
curl -s http://192.168.219.218/api/health; echo
