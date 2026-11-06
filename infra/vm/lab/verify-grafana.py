"""mon VM 안에서 비밀값 출력 없이 Grafana 데이터 소스와 대시보드를 확인한다."""

import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen

values = dict(
    line.split("=", 1) for line in Path("/etc/grafana/.env").read_text().splitlines() if "=" in line
)
credentials = base64.b64encode(("admin:" + values["GF_SECURITY_ADMIN_PASSWORD"]).encode()).decode()


def get(path):
    request = Request(
        "http://127.0.0.1:3000" + path,
        headers={"Authorization": "Basic " + credentials},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 mon 내부 Grafana만 조회
        return json.load(response)


dashboards = get("/api/search?type=dash-db")
if len(dashboards) != 9:
    raise RuntimeError("Grafana 대시보드가 9개가 아닙니다.")
print(json.dumps({"dashboards": [row["title"] for row in dashboards]}, ensure_ascii=False))
for uid in ("prometheus", "loki"):
    health = get(f"/api/datasources/uid/{uid}/health")
    if health["status"] != "OK":
        raise RuntimeError(f"{uid} 데이터 소스 상태: {health['status']}")
    print(json.dumps({"datasource": uid, "health": health}, ensure_ascii=False))
