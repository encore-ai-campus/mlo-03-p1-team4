"""정문 응답 계열과 Nginx API 개별 코드의 도넛 패널을 만든다."""

import json
from pathlib import Path

root = Path(__file__).resolve().parent
family = 'sum by(code)(increase(haproxy_frontend_http_responses_total{proxy="web"}[$__range])) > 0'
exact = 'sum by(status)(count_over_time({job="nginx",server=~"api1|api2"} | json | __error__="" | path=~"/api/.*" | path!~"/api/(health|metrics).*" [$__range]))'
for uid in ("overview", "haproxy", "nginx"):
    path = root / f"dashboard-{uid}.json"
    board = json.loads(path.read_text(encoding="utf-8-sig"))
    board["panels"] = [p for p in board["panels"] if p["id"] not in (500, 501)]
    additions = []
    choices = (
        [
            (
                "HTTP 응답 비율 · 정문 전체",
                family,
                "prometheus",
                "{{code}}",
                "선택 기간의 HAProxy 정문 응답 비율입니다. API 시간별 오류 추이는 FastAPI 대시보드에서 확인합니다.",
            )
        ]
        if uid == "overview"
        else []
    )
    for i, (title, expr, source, legend, description) in enumerate(choices):
        additions.append(
            {
                "id": 500 + i,
                "title": title,
                "description": description,
                "type": "piechart",
                "datasource": {"type": source, "uid": source},
                "targets": [
                    {
                        "refId": "A",
                        "expr": expr,
                        "legendFormat": legend,
                        "instant": True,
                        "queryType": "instant",
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "short",
                        "decimals": 0,
                        "color": {"mode": "palette-classic"},
                        "noValue": "선택 기간 수집 없음",
                    },
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": name},
                            "properties": [
                                {"id": "color", "value": {"mode": "fixed", "fixedColor": color}}
                            ],
                        }
                        for name, color in [
                            ("2xx", "green"),
                            ("200", "green"),
                            ("201", "blue"),
                            ("4xx", "orange"),
                            ("401", "orange"),
                            ("409", "yellow"),
                            ("5xx", "red"),
                            ("503", "red"),
                        ]
                    ],
                },
                "options": {
                    "pieType": "donut",
                    "displayLabels": ["name", "percent"],
                    "reduceOptions": {
                        "values": source == "loki",
                        "calcs": ["lastNotNull"],
                        "fields": "",
                    },
                    "legend": {
                        "displayMode": "table",
                        "placement": "right",
                        "values": ["value", "percent"],
                    },
                    "tooltip": {"mode": "single", "sort": "desc"},
                },
                "gridPos": {"x": i % 2 * 12, "y": 3, "w": 12, "h": 7},
            }
        )
    stats = [p for p in board["panels"] if p["type"] == "stat"]
    rest = [p for p in board["panels"] if p["type"] != "stat"]
    board["panels"] = stats + additions + rest
    board["version"] += 1
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("HTTP 상태 도넛: 전체 현황에 정문 응답 비율 1개만 생성")
