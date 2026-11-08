"""실제 109 수집 지표를 사용해 Grafana 5개 대시보드 영역을 정리한다."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}


def target(expr, ref="A", legend=None, *, instant=False, fmt=None):
    item = {"refId": ref, "expr": expr}
    if legend is not None:
        item["legendFormat"] = legend
    if instant:
        item["instant"] = True
    if fmt is not None:
        item["format"] = fmt
    return item


def make_panel(
    panel_id, title, kind, targets, *, datasource=PROM, unit="short", description="", instant=False
):
    defaults = {"unit": unit, "min": 0, "decimals": 1, "noValue": "수집 없음"}
    options = {}
    if kind == "stat":
        options = {
            "colorMode": "value",
            "graphMode": "none",
            "textMode": "value_and_name",
            "justifyMode": "auto",
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "values": False},
        }
    elif kind == "timeseries":
        defaults["custom"] = {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
        }
        options = {
            "legend": {"displayMode": "list", "placement": "bottom", "calcs": []},
            "tooltip": {"mode": "multi", "sort": "desc"},
        }
    elif kind == "state-timeline":
        defaults["mappings"] = [
            {
                "type": "value",
                "options": {
                    "0": {"text": "DOWN / STOPPED", "color": "red"},
                    "1": {"text": "UP / RUNNING", "color": "green"},
                },
            }
        ]
        options = {
            "showValue": "auto",
            "mergeValues": True,
            "rowHeight": 0.8,
            "tooltip": {"mode": "single"},
        }
    elif kind == "barchart":
        options = {
            "orientation": "horizontal",
            "showValue": "auto",
            "groupWidth": 0.7,
            "barWidth": 0.9,
            "stacking": {"mode": "none", "group": "A"},
            "legend": {"show": False},
            "tooltip": {"mode": "single", "sort": "desc"},
        }
    elif kind == "table":
        options = {"showHeader": True, "cellHeight": "sm", "sortBy": []}
    elif kind == "logs":
        options = {
            "showTime": True,
            "showLabels": False,
            "wrapLogMessage": False,
            "sortOrder": "Descending",
            "enableLogDetails": True,
        }
    return {
        "id": panel_id,
        "title": title,
        "description": description,
        "type": kind,
        "datasource": datasource,
        "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": options,
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 7},
    }


def upsert(panels, new_panel):
    panel_id = new_panel["id"]
    return [p for p in panels if p.get("id") != panel_id] + [new_panel]


def get_panel(panels, panel_id):
    return next((p for p in panels if p.get("id") == panel_id), None)


def set_panel_query(panels, panel_id, title, expr, unit, description=""):
    panel = get_panel(panels, panel_id)
    if not panel:
        return
    panel["title"] = title
    panel["description"] = description
    panel["targets"] = [target(expr, instant=panel.get("type") == "stat")]
    panel.setdefault("fieldConfig", {}).setdefault("defaults", {}).update(
        unit=unit, min=0, noValue="수집 없음"
    )


def layout(board):
    panels = board.get("panels", [])
    stats = [p for p in panels if p.get("type") == "stat"]
    graphs = [p for p in panels if p.get("type") not in ("stat", "text", "logs")]
    notes = [p for p in panels if p.get("type") == "text"]
    logs = [p for p in panels if p.get("type") == "logs"]
    columns = min(4, max(1, len(stats)))
    width = 24 // columns
    for i, panel in enumerate(stats):
        panel["gridPos"] = {"x": (i % columns) * width, "y": (i // columns) * 3, "w": width, "h": 3}
        panel.setdefault("options", {}).update(
            colorMode="value",
            graphMode="none",
            textMode="value_and_name",
            justifyMode="auto",
            orientation="horizontal",
            reduceOptions={"calcs": ["lastNotNull"], "values": False},
        )
        panel.setdefault("options", {}).setdefault("text", {}).update(valueSize=16, titleSize=11)
        for item in panel.get("targets", []):
            item["instant"] = True
    y = ((len(stats) + columns - 1) // columns) * 3
    col = 0
    full_width = {"state-timeline", "heatmap"}
    for panel in graphs:
        if panel.get("type") in full_width:
            if col:
                y += 7
                col = 0
            height = 8
            panel["gridPos"] = {"x": 0, "y": y, "w": 24, "h": height}
            y += height
        else:
            panel["gridPos"] = {"x": col * 12, "y": y, "w": 12, "h": 7}
            if col:
                col = 0
                y += 7
            else:
                col = 1
    if col:
        y += 7
    for panel in notes:
        panel["gridPos"] = {"x": 0, "y": y, "w": 24, "h": 4}
        y += 4
    for panel in logs:
        height = 16 if len(panels) == 1 else 9
        panel["gridPos"] = {"x": 0, "y": y, "w": 24, "h": height}
        y += height
    board["panels"] = stats + graphs + notes + logs


def update_overview(board):
    panels = board["panels"]
    set_panel_query(
        panels,
        1,
        "API 총 요청 · 선택 기간",
        'sum(increase(http_requests_total{job="api",handler!~"/health|/metrics"}[$__range]))',
        "short",
        "FastAPI 요청 수. 정적 파일과 헬스·메트릭 요청은 제외합니다.",
    )
    set_panel_query(
        panels,
        2,
        "API 요청률",
        'sum(rate(http_requests_total{job="api",handler!~"/health|/metrics"}[$__rate_interval]))',
        "reqps",
    )
    set_panel_query(
        panels,
        3,
        "앱 백엔드 정상 대수",
        'sum(haproxy_server_status{proxy="apps",state="UP"})',
        "short",
    )
    set_panel_query(panels, 4, "정상 수집 대상", "sum(up)", "short")
    panels[:] = [p for p in panels if p.get("id") != 501]
    pie = get_panel(panels, 500)
    if pie:
        pie["title"] = "HTTP 응답 비율 · HAProxy 정문"
        pie["description"] = (
            "선택 기간의 정문 전체 응답 비율입니다. 시간별 오류 추이는 FastAPI 대시보드에서 확인하세요."
        )
    panels[:] = upsert(
        panels,
        make_panel(
            20,
            "API 5xx 비율",
            "stat",
            [
                target(
                    '100 * sum(rate(http_requests_total{job="api",status=~"5.."}[$__rate_interval])) / clamp_min(sum(rate(http_requests_total{job="api"}[$__rate_interval])), 0.001)'
                )
            ],
            unit="percent",
            description="FastAPI 전체 응답 중 5xx 비율입니다.",
        ),
    )
    panels[:] = upsert(
        panels,
        make_panel(
            21,
            "API 응답 p95",
            "stat",
            [
                target(
                    '1000 * histogram_quantile(0.95, sum by(le)(rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])))'
                )
            ],
            unit="ms",
            description="FastAPI 요청 지연의 95백분위입니다.",
        ),
    )
    panels[:] = upsert(
        panels,
        make_panel(
            22,
            "MariaDB 복제 지연",
            "stat",
            [target('mysql_slave_status_seconds_behind_master{job="mariadb"}')],
            unit="s",
        ),
    )
    panels[:] = upsert(
        panels,
        make_panel(
            23,
            "이벤트 API 수락 · 선택 기간",
            "stat",
            [
                target(
                    'sum(increase(http_requests_total{job="api",handler="/events",status="202"}[$__range]))'
                )
            ],
            unit="short",
            description="HTTP 202로 수락된 요청 수이며 MongoDB 저장 건수는 아닙니다.",
        ),
    )
    panels[:] = upsert(
        panels,
        make_panel(
            600,
            "서비스·백엔드 상태 이력",
            "state-timeline",
            [
                target(
                    'max by(server,job)(up{job=~"alloy|api|haproxy|loki|mariadb|nginx|nodes|prometheus"})',
                    "A",
                    "{{server}} · {{job}}",
                ),
                target(
                    'haproxy_server_status{proxy="apps",state="UP"}',
                    "B",
                    "{{server}} · HAProxy backend",
                ),
            ],
            description="1=정상, 0=비정상. Prometheus 수집 상태와 HAProxy의 앱 서버 헬스체크를 함께 봅니다.",
        ),
    )
    note = get_panel(panels, 90)
    if note:
        note["title"] = "지표 해석"
        note["options"] = {
            "mode": "markdown",
            "content": "MariaDB primary·replica exporter가 연결되어 있습니다. DB 용량은 `spacecube`의 테이블 데이터·인덱스 합계이며 OS 디스크 사용량과 구분됩니다. MongoDB는 온라인이지만 이벤트 API 202는 수락 건수이지 MongoDB 저장 건수가 아닙니다.",
        }
    board["panels"] = sorted(
        panels,
        key=lambda p: (
            0
            if p.get("type") == "stat"
            else 1
            if p.get("id") == 600
            else 2
            if p.get("type") not in ("text", "logs")
            else 3
            if p.get("type") == "text"
            else 4,
            p.get("id", 0),
        ),
    )
    board["description"] = (
        "서비스 요청 품질(요청률·오류·지연)과 인프라 상태를 먼저 보고, 아래 상태 이력·자원 그래프에서 장애 구간을 추적합니다."
    )


def update_api(board):
    panels = board["panels"]
    set_panel_query(
        panels,
        2,
        "초당 API 요청",
        'sum by(server)(rate(http_requests_total{job="api"}[$__rate_interval]))',
        "reqps",
    )
    set_panel_query(
        panels,
        3,
        "HTTP 상태코드별 API 요청률",
        'sum by(server,status)(rate(http_requests_total{job="api"}[$__rate_interval]))',
        "reqps",
    )
    latency = get_panel(panels, 4)
    if latency:
        latency.update(
            title="API 응답 지연 p50 / p95 / p99",
            description="FastAPI 히스토그램 버킷에서 계산한 서버별 백분위입니다. 단위는 ms.",
            type="timeseries",
        )
        latency["datasource"] = PROM
        latency["targets"] = [
            target(
                '1000 * histogram_quantile(0.50, sum by(le,server)(rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])))',
                "A",
                "{{server}} · p50",
            ),
            target(
                '1000 * histogram_quantile(0.95, sum by(le,server)(rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])))',
                "B",
                "{{server}} · p95",
            ),
            target(
                '1000 * histogram_quantile(0.99, sum by(le,server)(rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])))',
                "C",
                "{{server}} · p99",
            ),
        ]
        latency.setdefault("fieldConfig", {}).setdefault("defaults", {}).update(
            unit="ms", min=0, noValue="수집 없음"
        )
    mongo = get_panel(panels, 6)
    if mongo:
        mongo["title"] = "MongoDB 이벤트 전달 실패"
        mongo["description"] = (
            "MongoDB는 현재 온라인입니다. 응답 뒤 저장 실패 누계이며 문서 수나 저장 완료 건수가 아닙니다."
        )
    panels[:] = upsert(
        panels,
        make_panel(
            7,
            "API 5xx 요청률 · 상태코드별",
            "timeseries",
            [
                target(
                    'sum by(server,status)(rate(http_requests_total{job="api",status=~"5.."}[$__rate_interval]))',
                    legend="{{server}} · {{status}}",
                )
            ],
            unit="reqps",
            description="503 등 서버 오류를 발생 서버와 상태코드별로 비교합니다.",
        ),
    )
    panels[:] = upsert(
        panels,
        make_panel(
            8,
            "API 응답 지연 분포 · 시간별",
            "heatmap",
            [
                target(
                    'sum by(le)(rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval]))',
                    legend="{{le}}",
                    fmt="heatmap",
                )
            ],
            unit="s",
            description="각 시점의 요청 지연시간 분포입니다. 밝은 구간은 요청이 몰린 지연 버킷입니다.",
        ),
    )
    panels[:] = upsert(
        panels,
        make_panel(
            9,
            "5xx 발생 경로 · 선택 기간 상위 10개",
            "table",
            [
                target(
                    'topk(10,sum by(handler,status)(increase(http_requests_total{job="api",status=~"5.."}[$__range])))',
                    instant=True,
                    fmt="table",
                )
            ],
            description="선택 기간에 5xx가 많이 발생한 API 경로와 코드입니다.",
        ),
    )
    board["description"] = (
        "API RED 상세: 요청률·상태코드·지연 백분위와 히스토그램, 5xx 경로를 살펴봅니다."
    )


def update_storage(board):
    board["title"] = "Spacecube / 이벤트·저장소 요약"
    board["description"] = (
        "이벤트 API 수락, replica 읽기 대체, 로그 전달과 DB 용량 요약을 봅니다. DB 세부 패널은 MariaDB 대시보드에서 확인합니다."
    )
    board["panels"] = [
        make_panel(
            10,
            "MariaDB exporter 정상 대수",
            "stat",
            [target('sum(mysql_up{job="mariadb"})')],
            unit="short",
        ),
        make_panel(
            11,
            "spacecube 데이터 + 인덱스",
            "stat",
            [
                target(
                    'sum by(server,role)(mysql_info_schema_table_size{job="mariadb",schema="spacecube",component=~"data_length|index_length"})',
                    "A",
                    "{{server}}",
                )
            ],
            unit="bytes",
            description="테이블 데이터·인덱스 크기 합계입니다. DB 서버 루트 디스크 사용량과 다릅니다.",
        ),
        make_panel(
            12,
            "Replica 복제 지연",
            "stat",
            [target('mysql_slave_status_seconds_behind_master{job="mariadb"}', "A", "{{server}}")],
            unit="s",
        ),
        make_panel(
            14,
            "이벤트 API 수락 수 · 선택 기간",
            "stat",
            [
                target(
                    'sum(increase(http_requests_total{job="api",handler="/events",status="202"}[$__range]))'
                )
            ],
            unit="short",
            description="HTTP 202 응답 수이며 MongoDB 저장 건수는 아닙니다.",
        ),
        make_panel(
            15,
            "읽기 대체 횟수 · 선택 기간",
            "stat",
            [target('sum(increase(db_read_fallback_total{job="api"}[$__range]))')],
            unit="short",
        ),
        make_panel(
            20,
            "이벤트 API 수락률 · HTTP 202",
            "timeseries",
            [
                target(
                    'sum by(server)(rate(http_requests_total{job="api",handler="/events",status="202"}[$__rate_interval]))',
                    legend="{{server}}",
                )
            ],
            unit="reqps",
        ),
        make_panel(
            21,
            "Replica 읽기 대체 증가율",
            "timeseries",
            [
                target(
                    'sum by(server)(rate(db_read_fallback_total{job="api"}[$__rate_interval]))',
                    legend="{{server}}",
                )
            ],
            unit="ops",
        ),
        make_panel(
            22,
            "MongoDB 전달 실패 누계",
            "timeseries",
            [
                target(
                    'sum by(server)(mongo_event_write_failures_total{job="api"})',
                    legend="{{server}}",
                )
            ],
            unit="short",
            description="MongoDB는 온라인입니다. 이벤트 API 수락과 MongoDB 저장은 별도입니다.",
        ),
        make_panel(
            23,
            "Alloy → Loki 전송률",
            "timeseries",
            [
                target(
                    'sum by(server)(rate(loki_write_sent_entries_total{job="alloy"}[$__rate_interval]))',
                    legend="{{server}}",
                )
            ],
            unit="ops",
        ),
        make_panel(
            24,
            "Loki 로그 수신률",
            "timeseries",
            [target("sum(rate(loki_distributor_lines_received_total[$__rate_interval]))")],
            unit="ops",
        ),
        make_panel(900, "저장 범위", "text", [], unit="short"),
    ]
    board["panels"][-1]["options"] = {
        "mode": "markdown",
        "content": "상세 DB 연결·쿼리·복제 스레드·테이블별 용량은 **MariaDB primary · replica** 대시보드에 있습니다. MongoDB는 온라인이며 원천은 space_rental_analytics.events입니다. 이벤트 API 202 응답은 Mongo 문서 수가 아닙니다.",
    }


def update_logs(board):
    board["description"] = (
        "같은 시간 범위에서 API 오류, Nginx 5xx, 시스템·수집기 로그를 확인합니다."
    )
    board["panels"] = [
        make_panel(
            1, "전체 로그", "logs", [target('{server=~"gw|api1|api2|mon"}')], datasource=LOKI
        ),
        make_panel(
            2,
            "FastAPI 오류·503·동시성 제한",
            "logs",
            [
                target(
                    '{job="api",server=~"api1|api2"} |~ "(?i)(ERROR|Exception|Traceback|503|Exceeded concurrency limit)"'
                )
            ],
            datasource=LOKI,
        ),
        make_panel(
            3,
            "Nginx API 5xx 접근 로그",
            "logs",
            [
                target(
                    '{job="nginx",server=~"api1|api2"} | json | __error__="" | path=~"/api/.*" | path!~"/api/(health|metrics).*" | status=~"5.."'
                )
            ],
            datasource=LOKI,
        ),
        make_panel(
            4,
            "서버·수집기 오류 로그",
            "logs",
            [
                target(
                    '{job="journal",server=~"gw|api1|api2|mon"} |~ "(?i)(error|failed|down|retry|drop)"'
                )
            ],
            datasource=LOKI,
        ),
    ]


def main():
    for path in sorted(ROOT.glob("dashboard-*.json")):
        original = json.loads(path.read_text(encoding="utf-8-sig"))
        board = copy.deepcopy(original)
        uid = board.get("uid", "")
        if uid == "spacecube-overview":
            update_overview(board)
        elif uid == "spacecube-api":
            update_api(board)
        elif uid == "spacecube-storage":
            update_storage(board)
        elif uid == "spacecube-logs":
            update_logs(board)
        elif uid in ("spacecube-nginx", "spacecube-haproxy"):
            board["panels"] = [p for p in board.get("panels", []) if p.get("id") not in (500, 501)]
        board["refresh"] = "15s"
        board["timepicker"] = {"refresh_intervals": ["15s", "30s", "1m", "5m"]}
        board["links"] = [
            {
                "type": "link",
                "title": title,
                "url": "/d/spacecube-" + uid,
                "keepTime": True,
                "includeVars": True,
                "targetBlank": False,
            }
            for uid, title in [
                ("overview", "전체 현황"),
                ("servers", "서버"),
                ("api", "FastAPI"),
                ("haproxy", "HAProxy"),
                ("mariadb", "MariaDB"),
                ("storage", "이벤트·저장소"),
                ("nginx", "Nginx"),
                ("alloy", "Alloy"),
                ("loki", "Loki"),
                ("logs", "로그"),
            ]
        ]
        board["tags"] = [tag for tag in board.get("tags", []) if tag != "db-disconnected"]
        layout(board)
        original_without_version = {k: v for k, v in original.items() if k != "version"}
        current_without_version = {k: v for k, v in board.items() if k != "version"}
        if current_without_version != original_without_version:
            board["version"] = max(int(original.get("version", 0)) + 1, 100)
        else:
            board["version"] = int(original.get("version", 1))
        path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: {len(board.get('panels', []))} panels, version {board['version']}")


if __name__ == "__main__":
    main()
