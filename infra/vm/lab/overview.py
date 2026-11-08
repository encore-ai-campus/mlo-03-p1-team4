"""전체 현황 대시보드를 기존 수집 지표로 생성한다."""

import json
from pathlib import Path

p = Path("infra/vm/lab")
base = json.loads((p / "dashboard-servers.json").read_text(encoding="utf-8"))
specs = [
    (
        "기간 총 요청 · 정적 파일 포함",
        "sum(increase(nginx_http_requests_total[$__range]))",
        "short",
        "stat",
    ),
    (
        "전체 RPS · 정적 파일 포함",
        "sum(rate(nginx_http_requests_total[$__rate_interval]))",
        "reqps",
        "stat",
    ),
    ("앱 정상 대수", 'sum(haproxy_server_status{proxy="apps",state="UP"})', "short", "stat"),
    ("수집 정상 대상", "sum(up)", "short", "stat"),
    (
        "서버별 CPU 사용률",
        '100 * (1 - avg by(server)(rate(node_cpu_seconds_total{job="nodes",mode="idle"[$__rate_interval])))',
        "percent",
        "timeseries",
    ),
    (
        "서버별 메모리 사용률",
        '100 * (1 - node_memory_MemAvailable_bytes{job="nodes"}/node_memory_MemTotal_bytes{job="nodes"})',
        "percent",
        "timeseries",
    ),
    ("서버별 가용 메모리", 'node_memory_MemAvailable_bytes{job="nodes"}', "bytes", "timeseries"),
    (
        "루트 디스크 사용률",
        '100 * (1-node_filesystem_avail_bytes{job="nodes",mountpoint="/",fstype!="rootfs"}/node_filesystem_size_bytes{job="nodes",mountpoint="/",fstype!="rootfs"})',
        "percent",
        "timeseries",
    ),
    (
        "서버별 분산 RPS",
        'rate(haproxy_server_loadbalanced_total{proxy="apps"}[$__rate_interval])',
        "reqps",
        "timeseries",
    ),
    (
        "Alloy 로그 전송 / 초",
        'sum by(server)(rate(loki_write_sent_entries_total{job="alloy"}[$__rate_interval]))',
        "ops",
        "timeseries",
    ),
]
panels = []
for i, (title, expr, unit, kind) in enumerate(specs):
    panels.append(
        {
            "id": i + 1,
            "title": title,
            "type": kind,
            "datasource": {"type": "prometheus", "uid": "prometheus"},
            "targets": [
                {
                    "refId": "A",
                    "expr": expr,
                    "legendFormat": "{{server}}",
                    "instant": kind == "stat",
                }
            ],
            "fieldConfig": {"defaults": {"unit": unit, "min": 0}, "overrides": []},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"], "values": False},
                "legend": {"displayMode": "list", "placement": "bottom"},
            },
            "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 7, "w": 12, "h": 7},
        }
    )
panels.append(
    {
        "id": 90,
        "type": "text",
        "title": "DB 수집 현황 · 지표 해석",
        "options": {
            "mode": "markdown",
            "content": "DB .212/.213: node exporter·mysqld exporter 정상 수집. MongoDB .216 온라인. 요청은 두 Nginx 합계이며 정적 파일·헬스 요청을 포함합니다. FastAPI 2워커 카운터는 아직 전체 합산이 아니므로 업무 누계로 사용하지 않습니다.",
        },
        "gridPos": {"x": 0, "y": 35, "w": 24, "h": 4},
    }
)
base.update(
    uid="spacecube-overview",
    title="Spacecube / 전체 현황",
    panels=panels,
    tags=["spacecube"],
    description="109 배포 전체 현황. DB exporter 2대·19 targets 수집.",
    version=1,
)
(p / "dashboard-overview.json").write_text(
    json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
for f in p.glob("dashboard-*.json"):
    b = json.loads(f.read_text(encoding="utf-8"))
    b["links"] = [
        {"type": "link", "title": "전체 현황", "url": "/d/spacecube-overview", "keepTime": True}
    ] + [x for x in b.get("links", []) if x.get("url") != "/d/spacecube-overview"]
    f.write_text(json.dumps(b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("전체 현황 11패널과 공통 링크 생성")
