"""109 제어 노드에서 서비스·지표·로그를 읽기 전용으로 확인한다."""

import json
import shlex
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

PRIVATE = Path.home() / ".config/spacecube109"


def ssh_mon(command):
    result = subprocess.run(  # noqa: S603 고정 mon 주소와 고정 SSH 실행 파일만 사용
        [
            "/usr/bin/ssh",
            "-i",
            str(PRIVATE / "id_ed25519"),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"UserKnownHostsFile={PRIVATE / 'known_hosts'}",
            "ubuntu@192.168.0.217",
            command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def mon_json(path, port=9090):
    return json.loads(ssh_mon("curl -fsS " + shlex.quote(f"http://127.0.0.1:{port}{path}")))


def get(path):
    with urlopen("http://192.168.0.218" + path, timeout=10) as response:
        return json.load(response)


health = get("/api/health")
if health.get("replica") == "down":
    raise RuntimeError("replica가 primary로 대체된 상태입니다.")
rotations = Counter()
for _ in range(12):
    with urlopen("http://192.168.0.218/", timeout=10) as response:
        rotations[response.headers["x-spacecube-node"]] += 1
if len(rotations) != 2:
    raise RuntimeError(f"두 앱에 분산되지 않습니다: {rotations}")
for _ in range(15):
    targets = mon_json("/api/v1/targets")["data"]["activeTargets"]
    if len(targets) == 15 and all(row["health"] == "up" for row in targets):
        break
    time.sleep(2)
if len(targets) != 15 or any(row["health"] != "up" for row in targets):
    raise RuntimeError([(row["labels"], row["lastError"]) for row in targets])
nginx = mon_json("/api/v1/query?" + urlencode({"query": "nginx_up"}))["data"]["result"]
if len(nginx) != 2 or any(row["value"][1] != "1" for row in nginx):
    raise RuntimeError("Nginx 실제 수집 실패")
servers = mon_json("/loki/api/v1/label/server/values", port=3100)["data"]
if set(servers) != {"gw", "api1", "api2", "mon"}:
    raise RuntimeError(f"Loki 서버 라벨 누락: {servers}")
venues = get("/api/venues?page=1&size=1")
result = {
    "health": health,
    "round_robin": rotations,
    "prometheus_targets_up": len(targets),
    "nginx_up": "2/2",
    "loki_servers": servers,
    "venues_total": venues["total"],
    "terraform_host": "109",
    "mongo": "excluded",
}
report = Path.home() / "spacecube109/reports/services.json"
report.parent.mkdir(exist_ok=True)
report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(report.read_text())
