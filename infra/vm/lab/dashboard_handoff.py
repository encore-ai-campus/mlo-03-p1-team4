"""DASH-003을 기존 Codex 원본에 중복 없이 반영한다."""

import argparse
import copy
import json
from pathlib import Path

TABS = [
    ("전체 현황", "overview"),
    ("서버", "servers"),
    ("HAProxy", "haproxy"),
    ("Nginx", "nginx"),
    ("FastAPI", "api"),
    ("MariaDB", "mariadb"),
    ("DB 연결·대기", "db-connections"),
    ("이벤트·저장소", "storage"),
    ("로그 탐색", "logs"),
    ("Alloy", "alloy"),
    ("Loki", "loki"),
]
PROM = {"type": "prometheus", "uid": "prometheus"}
NOTE = """**구성과 관측 범위**
- 219망 VM 7대: 정문 .218 · API .214/.215 · mon .217 · MariaDB .212/.213 · MongoDB .216.
- node exporter는 6대입니다. MongoDB는 전용 exporter 없이 API health 및 실험 SSH 표본으로 확인합니다. 수집 대상 정상 비율은 19개 scrape 대상의 응답 비율입니다.
- api1 타이머: 이용 완료 매시 :05 · event_daily 매시 :20 · 크롤러 월요일 04:00.

**지표를 읽는 법**
- 총 요청·RPS는 두 Nginx 합계로 정적 파일·health·상태 요청을 포함합니다. 실험 요청 수와는 다릅니다.
- 예약 생성·충돌·API 지연은 현재 수집 워커 통계입니다. 워커 합산이 미구성돼 기간 증가량이 과소/과대 집계될 수 있습니다. 실제 업무 건수는 DB/실험 기록으로 확인합니다.
- API p95의 300ms는 조회 가이드입니다. 모의 결제 예약 생성의 500ms 기준은 Locust 기록에서 따로 확인합니다.
- 생성기 파일럿 과거 이벤트 10,368건은 실시간 API 요청 카운터가 아닌 원천 events/event_daily에 있습니다."""
STORAGE_NOTE = """**저장·집계 범위**
MariaDB 10.11.14 primary·replica exporter는 정상 수집 중입니다. MongoDB 8.0.34는 온라인이며 전용 exporter는 미설치입니다.

이벤트 API 202는 batch 접수 수로, 이벤트 수나 MongoDB 저장 완료 건수가 아닙니다. 예약·취소의 서버 이벤트는 /events 요청 없이도 생성됩니다.

원천 space_rental_analytics.events는 api1이 매시 :20에 event_daily로 집계합니다. 생성기 파일럿(100명·30일, 10-08~11-06)의 10,368건과 이후 부하 시험 이벤트를 구분합니다. Mongo user.user_id는 문자열입니다. 업무별 정확한 건수는 실험 SQL/Mongo 집계 문서를 따릅니다."""


def stat(pid, title, expr, x, y, unit="short", steps=None, desc="", decimals=0):
    return {
        "id": pid,
        "title": title,
        "type": "stat",
        "description": desc,
        "datasource": copy.deepcopy(PROM),
        "gridPos": {"x": x, "y": y, "w": 6, "h": 3},
        "targets": [{"refId": "A", "expr": expr, "instant": True}],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": decimals,
                "min": 0,
                "noValue": "수집 없음",
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": steps or [{"color": "blue", "value": None}],
                },
            },
            "overrides": [],
        },
        "options": {
            "textMode": "value",
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "center",
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "values": False},
            "text": {"titleSize": 11, "valueSize": 24},
        },
    }


def patch_dashboard(original):
    d = copy.deepcopy(original)
    d["links"] = [
        {
            "title": title,
            "type": "link",
            "url": "/d/spacecube-" + uid,
            "keepTime": True,
            "includeVars": True,
            "targetBlank": False,
        }
        for title, uid in TABS
    ]
    d["timezone"] = "Asia/Seoul"
    d["refresh"] = "15s"
    d["time"] = {"from": "now-30m", "to": "now"}
    if d["uid"] == "spacecube-db-connections":
        d["title"] = "Spacecube / DB 연결·대기"
    if d["uid"] == "spacecube-storage":
        for panel in d["panels"]:
            if panel.get("type") == "text":
                panel.update(
                    title="저장·집계 범위", options={"mode": "markdown", "content": STORAGE_NOTE}
                )
                panel["gridPos"]["h"] = 8
    if d["uid"] != "spacecube-overview":
        return d
    legacy = {1, 2, 3, 4, 11, 12, 13, 14, 21, 22, *range(7001, 7009)}
    remaining = [p for p in d["panels"] if not (p["id"] in legacy and p.get("type") == "stat")]
    sample = "수집 워커 기준이며 다중 프로세스 합산이 미구성돼 과소/과대 집계될 수 있습니다. DB 실제 건수와 구분합니다."
    panels = [
        stat(
            7001,
            "기간 총 요청 · 정적 포함",
            "sum(increase(nginx_http_requests_total[$__range]))",
            0,
            0,
            desc="두 Nginx 전체 요청 증가 추정값. 정적·health·상태 요청 포함.",
        ),
        stat(
            7002,
            "전체 RPS · 정적 포함",
            "sum(rate(nginx_http_requests_total[$__rate_interval]))",
            6,
            0,
            "reqps",
            decimals=1,
        ),
        stat(
            7003,
            "앱 정상 (2대 중)",
            'sum(haproxy_server_status{proxy="apps",state="UP"})',
            12,
            0,
            steps=[
                {"color": "red", "value": None},
                {"color": "orange", "value": 1},
                {"color": "green", "value": 2},
            ],
            desc="HAProxy health 기준 정상 앱 서버 수",
        ),
        stat(
            7004,
            "수집 대상 정상 비율",
            "100*sum(up)/count(up)",
            18,
            0,
            "percent",
            steps=[
                {"color": "red", "value": None},
                {"color": "orange", "value": 90},
                {"color": "green", "value": 100},
            ],
            desc="전체 19개 scrape 대상 응답 비율. DB 연결 성공률과는 다릅니다.",
        ),
        stat(
            7005,
            "replica 복제 지연",
            'max(mysql_slave_status_seconds_behind_master{job="mariadb"})',
            0,
            3,
            "s",
            steps=[
                {"color": "green", "value": None},
                {"color": "orange", "value": 5},
                {"color": "red", "value": 30},
            ],
        ),
        stat(
            7006,
            "예약 생성 · 워커 표본",
            'sum(increase(reservation_total{job="api",result="ok"}[$__range]))',
            6,
            3,
            desc=sample,
        ),
        stat(
            7007,
            "예약 충돌 · 워커 표본",
            'sum(increase(reservation_total{job="api",result="conflict"}[$__range]))',
            12,
            3,
            desc="동일 칸 경합의 정상 409 차단. " + sample,
        ),
        stat(
            7008,
            "API 응답 p95",
            'histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])))',
            18,
            3,
            "s",
            steps=[
                {"color": "green", "value": None},
                {"color": "orange", "value": 0.3},
                {"color": "red", "value": 1},
            ],
            decimals=2,
            desc="현재 수집 워커의 전체 API 지연. 조회 300ms 가이드이며 업무별 실험 p95와 구분합니다.",
        ),
    ]
    indexed = {p["id"]: p for p in remaining}
    used = set()
    positions = {
        5: (0, 6, 12, 7),
        6: (12, 6, 12, 7),
        600: (0, 13, 24, 6),
        7: (0, 19, 12, 7),
        8: (12, 19, 12, 7),
        9: (0, 26, 12, 7),
        10: (12, 26, 12, 7),
    }
    for pid, pos in positions.items():
        if pid in indexed:
            p = indexed[pid]
            p["gridPos"] = dict(zip(["x", "y", "w", "h"], pos, strict=True))
            panels.append(p)
            used.add(pid)
            if pid in {5, 6, 7, 8}:
                p["description"] = (
                    "node exporter 6대 지표입니다. MongoDB는 실험 SSH 표본에서 확인합니다."
                )
    pies = [p for p in remaining if p.get("type") == "piechart"]
    for i, p in enumerate(pies):
        p["gridPos"] = {"x": (i % 2) * 12, "y": 33 + (i // 2) * 7, "w": 12, "h": 7}
        panels.append(p)
        used.add(p["id"])
    cursor = 33 + ((len(pies) + 1) // 2) * 7
    for i, pid in enumerate([20, 23]):
        if pid in indexed:
            p = indexed[pid]
            p["gridPos"] = {"x": i * 12, "y": cursor, "w": 12, "h": 2}
            panels.append(p)
            used.add(pid)
    cursor += 2
    for p in remaining:
        if p["id"] in used:
            continue
        if p.get("type") == "text":
            p.update(title="구성과 읽는 법", options={"mode": "markdown", "content": NOTE})
            height = 8
        else:
            height = 7
        p["gridPos"] = {"x": 0, "y": cursor, "w": 24, "h": height}
        cursor += height
        panels.append(p)
    d["panels"] = panels
    d["description"] = "219망 VM 7대: 앱·수집 상태, 트래픽, 예약 워커 표본, 복제 지연과 OS 자원."
    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path, default=Path(__file__).parent)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    out = args.output or args.source
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.source.glob("dashboard-*.json")):
        d = patch_dashboard(json.loads(path.read_text(encoding="utf-8-sig")))
        (out / path.name).write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print("DASH-003 applied")


if __name__ == "__main__":
    main()
