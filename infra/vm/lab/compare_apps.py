"""HAProxy 대시보드에 두 앱의 분산·503·동시성 경고 비교를 추가한다."""

import json
from pathlib import Path

path = Path(__file__).with_name("dashboard-haproxy.json")
board = json.loads(path.read_text(encoding="utf-8-sig"))
board["panels"] = [p for p in board["panels"] if p["id"] < 200]
y = max(p["gridPos"]["y"] + p["gridPos"]["h"] for p in board["panels"])
specs = [
    (
        "기간별 서버 분산 요청",
        'increase(haproxy_server_loadbalanced_total{proxy="apps"}[$__range])',
        "short",
        "prometheus",
    ),
    (
        "분산 비율 % · 최근 속도 기준",
        '100 * rate(haproxy_server_loadbalanced_total{proxy="apps"}[$__rate_interval]) / ignoring(server) group_left sum without(server)(rate(haproxy_server_loadbalanced_total{proxy="apps"}[$__rate_interval]))',
        "percent",
        "prometheus",
    ),
    (
        "서버별 HTTP 5xx / 초",
        'sum by(server)(rate(haproxy_server_http_responses_total{proxy="apps",code="5xx"}[$__rate_interval]))',
        "reqps",
        "prometheus",
    ),
    (
        "HAProxy→앱 활성 세션 · 워커 연결 수와 다름",
        'haproxy_server_current_sessions{proxy="apps"}',
        "short",
        "prometheus",
    ),
    (
        "헬스체크 UP/DOWN 전환 · 기간 증가량",
        'increase(haproxy_server_check_up_down_total{proxy="apps"}[$__range])',
        "short",
        "prometheus",
    ),
    (
        "서버별 평균 응답 시간 · HAProxy",
        'haproxy_server_response_time_average_seconds{proxy="apps"}',
        "s",
        "prometheus",
    ),
    (
        "동시성 제한 경고 · 서버별 분당 기록",
        'sum by(server)(count_over_time({job="journal",server=~"api1|api2"} |= "Exceeded concurrency limit" [1m]))',
        "short",
        "loki",
    ),
    (
        "헬스 실패 누계 · 기간 증가량",
        'increase(haproxy_server_check_failures_total{proxy="apps"}[$__range])',
        "short",
        "prometheus",
    ),
]
for i, (title, expr, unit, source) in enumerate(specs):
    board["panels"].append(
        {
            "id": 200 + i,
            "title": title,
            "type": "timeseries",
            "datasource": {"type": source, "uid": source},
            "targets": [
                {"refId": "A", "expr": expr, "legendFormat": "{{server}}", "queryType": "range"}
            ],
            "fieldConfig": {"defaults": {"unit": unit, "min": 0}, "overrides": []},
            "options": {
                "legend": {"displayMode": "list", "placement": "bottom"},
                "tooltip": {"mode": "multi"},
            },
            "gridPos": {"x": i % 2 * 12, "y": y + i // 2 * 8, "w": 12, "h": 8},
        }
    )
board["panels"].append(
    {
        "id": 220,
        "title": "FastAPI 동시성 제한·HAProxy 제외 근거 로그",
        "type": "logs",
        "datasource": {"type": "loki", "uid": "loki"},
        "targets": [
            {
                "refId": "A",
                "expr": '{job="journal",server=~"api1|api2|gw"} |~ "Exceeded concurrency limit|Server apps/.*(DOWN|UP)|no server available"',
            }
        ],
        "options": {
            "showTime": True,
            "showLabels": True,
            "wrapLogMessage": True,
            "sortOrder": "Descending",
        },
        "gridPos": {"x": 0, "y": y + 32, "w": 24, "h": 12},
    }
)
board["panels"].append(
    {
        "id": 221,
        "title": "지표 해석·미수집 항목",
        "type": "text",
        "options": {
            "mode": "markdown",
            "content": "요청 수·세션·경고 건수는 서로 다른 지표입니다. 경고 270:66 또는 8:0은 부하 비율이 아닙니다. 워커별 연결·실행 작업·DB 풀 대기는 아직 미수집입니다. Loki 빈 구간은 0건을 보장하지 않으며 수집 상태를 함께 보세요. 서버 제외 전후를 비교하세요.",
        },
        "gridPos": {"x": 0, "y": y + 44, "w": 24, "h": 5},
    }
)
board["description"] = (
    "두 앱의 요청 분배·응답·헬스 제외·Uvicorn 동시성 경고 비교. FastAPI 워커 내부 연결과 DB 풀 대기는 미수집."
)
board["version"] = board.get("version", 1) + 1
path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("HAProxy 비교 패널 10개 추가")
