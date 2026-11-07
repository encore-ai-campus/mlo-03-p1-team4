"""관측 중인 지표를 사용해 서비스별 Grafana 대시보드와 전환 링크를 생성한다."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINKS = [
    ("servers", "서버"),
    ("nginx", "Nginx"),
    ("api", "FastAPI"),
    ("haproxy", "HAProxy"),
    ("alloy", "Alloy"),
    ("loki", "Loki"),
    ("logs", "로그"),
]
SPECS = {
    "nginx": (
        "Nginx",
        [
            ("Nginx 수집 상태", "nginx_up", "stat", "short", "{{instance}}"),
            ("활성 연결", "nginx_connections_active", "timeseries", "short", "{{instance}}"),
            (
                "초당 요청",
                "rate(nginx_http_requests_total[2m])",
                "timeseries",
                "reqps",
                "{{instance}}",
            ),
            ("처리 중 연결", "nginx_connections_writing", "timeseries", "short", "{{instance}}"),
            ("대기 연결", "nginx_connections_waiting", "timeseries", "short", "{{instance}}"),
            (
                "수락한 연결 / 초",
                "rate(nginx_connections_accepted[2m])",
                "timeseries",
                "cps",
                "{{instance}}",
            ),
        ],
        '{job="nginx"}',
    ),
    "api": (
        "FastAPI",
        [
            (
                "FastAPI 프로세스 수집 상태 (DB 상태와 별개)",
                'up{job="api"}',
                "stat",
                "short",
                "{{server}}",
            ),
            (
                "초당 요청",
                'sum by(server)(rate(http_requests_total{job="api"}[2m]))',
                "timeseries",
                "reqps",
                "{{server}}",
            ),
            (
                "응답 상태별 요청",
                'sum by(server,status)(rate(http_requests_total{job="api"}[2m]))',
                "timeseries",
                "reqps",
                "{{server}} · {{status}}",
            ),
            (
                "응답 p95",
                'histogram_quantile(0.95,sum by(le,server)(rate(http_request_duration_seconds_bucket{job="api"}[2m])))',
                "timeseries",
                "s",
                "{{server}}",
            ),
            (
                "워커 프로세스 메모리 (수집된 워커)",
                'process_resident_memory_bytes{job="api"}',
                "timeseries",
                "bytes",
                "{{server}}",
            ),
            (
                "MongoDB 전달 실패 (현재 미연결)",
                "mongo_event_write_failures_total",
                "timeseries",
                "short",
                "{{server}}",
            ),
        ],
        '{job="api"}',
    ),
    "haproxy": (
        "HAProxy",
        [
            (
                "앱 서버 UP",
                'haproxy_server_status{proxy="apps",state="UP"}',
                "stat",
                "short",
                "{{server}}",
            ),
            (
                "서버별 분산 요청 / 초",
                'rate(haproxy_server_loadbalanced_total{proxy="apps"}[2m])',
                "timeseries",
                "reqps",
                "{{server}}",
            ),
            (
                "서버별 누적 분산 요청",
                'haproxy_server_loadbalanced_total{proxy="apps"}',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "서버별 활성 세션",
                'haproxy_server_current_sessions{proxy="apps"}',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "헬스체크 실패 누계",
                'haproxy_server_check_failures_total{proxy="apps"}',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "서버별 평균 응답 시간",
                'haproxy_server_response_time_average_seconds{proxy="apps"}',
                "timeseries",
                "s",
                "{{server}}",
            ),
        ],
        '{server="gw",job="journal"}',
    ),
    "alloy": (
        "Alloy · 로그 수집·전송",
        [
            ("Alloy 수집 상태", 'up{job="alloy"}', "stat", "short", "{{server}}"),
            (
                "설정 로드 성공",
                'alloy_config_last_load_successful{job="alloy"}',
                "stat",
                "short",
                "{{server}}",
            ),
            (
                "Loki 전달 로그 / 초",
                'sum by(server)(rate(loki_write_sent_entries_total{job="alloy"}[2m]))',
                "timeseries",
                "ops",
                "{{server}}",
            ),
            (
                "전송 재시도 누계",
                'sum by(server)(loki_write_batch_retries_total{job="alloy"})',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "전송 유실 누계",
                'sum by(server)(loki_write_dropped_entries_total{job="alloy"})',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "활성 파일 수 (gw·mon은 journal만 수집)",
                'loki_source_file_files_active_total{job="alloy"}',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "journal 수집 누계",
                'loki_source_journal_target_lines_total{job="alloy"}',
                "timeseries",
                "short",
                "{{server}}",
            ),
            (
                "Alloy 메모리",
                'process_resident_memory_bytes{job="alloy"}',
                "timeseries",
                "bytes",
                "{{server}}",
            ),
        ],
        '{job="journal"} |= "alloy"',
    ),
    "loki": (
        "Loki · 로그 저장·조회",
        [
            ("Loki 수집 상태", 'up{job="loki"}', "stat", "short", "{{instance}}"),
            (
                "수신 로그 / 초",
                "sum(rate(loki_distributor_lines_received_total[2m]))",
                "timeseries",
                "ops",
                "수신 로그",
            ),
            (
                "수신 바이트 / 초",
                "sum(rate(loki_distributor_bytes_received_total[2m]))",
                "timeseries",
                "Bps",
                "수신량",
            ),
            (
                "메모리 내 스트림",
                "sum(loki_ingester_memory_streams)",
                "timeseries",
                "short",
                "스트림",
            ),
            (
                "Loki 메모리",
                'process_resident_memory_bytes{job="loki"}',
                "timeseries",
                "bytes",
                "Loki",
            ),
            (
                "조회·수신 요청 / 초",
                "sum by(route,status_code)(rate(loki_request_duration_seconds_count[2m]))",
                "timeseries",
                "reqps",
                "{{route}} · {{status_code}}",
            ),
        ],
        '{server=~"gw|api1|api2|mon"}',
    ),
}

for uid, (title, specs, log_query) in SPECS.items():
    panels = []
    for index, (name, expr, kind, unit, legend) in enumerate(specs):
        defaults = {"unit": unit, "min": 0}
        if kind == "stat":
            defaults.update(
                {
                    "mappings": [
                        {
                            "type": "value",
                            "options": {
                                "0": {"text": "DOWN", "color": "red"},
                                "1": {"text": "UP", "color": "green"},
                            },
                        }
                    ],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}],
                    },
                }
            )
        panels.append(
            {
                "id": index + 1,
                "title": name,
                "type": kind,
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [{"refId": "A", "expr": expr, "legendFormat": legend}],
                "fieldConfig": {"defaults": defaults, "overrides": []},
                "options": {
                    "legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"},
                }
                if kind == "timeseries"
                else {
                    "colorMode": "background",
                    "reduceOptions": {"calcs": ["lastNotNull"], "values": False},
                },
                "gridPos": {"x": index % 2 * 12, "y": index // 2 * 8, "w": 12, "h": 8},
            }
        )
    panels.append(
        {
            "id": 100,
            "title": "관련 로그 · Loki",
            "type": "logs",
            "datasource": {"type": "loki", "uid": "loki"},
            "targets": [{"refId": "A", "expr": log_query}],
            "options": {
                "showTime": True,
                "showLabels": True,
                "wrapLogMessage": True,
                "sortOrder": "Descending",
            },
            "gridPos": {"x": 0, "y": ((len(specs) + 1) // 2) * 8, "w": 24, "h": 12},
        }
    )
    board = {
        "uid": f"spacecube-{uid}",
        "title": f"Spacecube / {title}",
        "schemaVersion": 39,
        "version": 2,
        "refresh": "15s",
        "panels": panels,
        "time": {"from": "now-30m", "to": "now"},
        "tags": ["spacecube", "lab"],
        "description": "DB·MongoDB 미연결 시험. FastAPI /health=503은 예상 상태. API 워커별 메트릭은 현재 스크랩한 프로세스 기준이며 전체 워커 합산이 아니다.",
    }
    (HERE / f"dashboard-{uid}.json").write_text(
        json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

for path in HERE.glob("dashboard-*.json"):
    board = json.loads(path.read_text(encoding="utf-8"))
    board["links"] = [
        {
            "type": "link",
            "title": label,
            "url": f"/d/spacecube-{uid}",
            "targetBlank": False,
            "keepTime": True,
            "includeVars": True,
        }
        for uid, label in LINKS
    ]
    if board["uid"] == "spacecube-servers":
        for panel in board["panels"]:
            if panel["title"] == "HAProxy 백엔드 상태":
                panel["targets"][0]["expr"] = 'haproxy_server_status{proxy="apps",state="UP"}'
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("서비스 대시보드 8개·공통 전환 링크 생성 완료")
