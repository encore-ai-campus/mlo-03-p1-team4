"""부하 실행기의 시간 자원·응답·측정 판정. 외부 부작용이 없는 함수만 둔다."""

import math
from datetime import date, timedelta
from uuid import uuid4


def allocate_blocks(venues, start_date, days):
    result = []
    first = date.fromisoformat(start_date)
    for offset in range(days):
        for venue in venues:
            hours = venue["min_hours"]
            if not 1 <= hours <= 4:
                continue
            for start in range(venue["open_hour"], venue["close_hour"] - hours + 1, hours):
                result.append(
                    {
                        "venue_id": venue["venue_id"],
                        "date": (first + timedelta(days=offset)).isoformat(),
                        "start_hour": start,
                        "hours": hours,
                        "headcount": 1,
                        "method": "card",
                    }
                )
    return result


def check_reservation(body, receipt, price, expected_status):
    expected = {key: body[key] for key in ("venue_id", "date", "start_hour", "headcount")}
    expected.update(
        end_hour=body["start_hour"] + body["hours"],
        total_price=price * body["hours"],
        status=expected_status,
    )
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ValueError(key)
    if not isinstance(receipt.get("reservation_id"), int) or receipt["reservation_id"] <= 0:
        raise ValueError("reservation_id")
    if (
        receipt.get("payment", {}).get("status") != "paid"
        or receipt["payment"].get("method") != body["method"]
    ):
        raise ValueError("payment")


def classify_status(status, code, expected):
    if status == 0 or status >= 500:
        return "availability"
    if 200 <= status < 300:
        return "ok"
    if expected.get(status) is not None and expected[status] == code:
        return "expected"
    return "contract"


def measured_rows(rows, start, end):
    return [row for row in rows if row["started"] >= start and row["finished"] <= end]


def validate_observation(record):
    """수집 HTTP 성공과 실제 관측 가능 상태를 구분한다."""
    metrics = record["metrics"]
    for name in (
        "up",
        "cpu",
        "memory",
        "disk_free",
        "app_connections",
        "db_connections",
        "db_running",
        "db_max_connections",
        "db_replica_lag",
        "backend",
        "mysql_up",
        "app_metrics_error",
        "app_metrics_timestamp",
    ):
        if not metrics.get(name):
            raise ValueError("empty_metric_" + name)
        if any(not math.isfinite(float(row["value"][1])) for row in metrics[name]):
            raise ValueError("invalid_metric_" + name)
    for name, expected, minimum in [
        ("up", 1, 19),
        ("mysql_up", 1, 2),
        ("backend", 1, 2),
        ("app_metrics_error", 0, 2),
    ]:
        if len(metrics[name]) < minimum or any(
            float(row["value"][1]) != expected for row in metrics[name]
        ):
            raise ValueError("unhealthy_metric_" + name)
    if any(
        not -10 <= record["time"] - float(row["value"][1]) < 90
        for row in metrics["app_metrics_timestamp"]
    ):
        raise ValueError("stale_app_metrics")
    if "direct_7node_sample" in record:
        nodes = record["direct_7node_sample"]["nodes"]
        if {row["server"] for row in nodes} != {
            "gw",
            "api1",
            "api2",
            "mon",
            "db1",
            "db2",
            "mongo",
        } or any("error" in row for row in nodes):
            raise ValueError("direct_node_unavailable")


def build_event_batch(session_id, count, start_sequence):
    if not 1 <= count <= 50 or start_sequence < 1:
        raise ValueError("event_batch_bounds")
    return {
        "session_id": session_id,
        "events": [
            {
                "event_id": str(uuid4()),
                "schema_version": 1,
                "event_name": "page_view",
                "user": {
                    "anonymous_id": "synthetic-" + session_id,
                    "session_id": session_id,
                    "session_sequence": start_sequence + offset,
                },
                "site": {
                    "site_id": "main",
                    "hostname": "192.168.219.218",
                    "platform": "desktop_web",
                },
                "acquisition": {"landing_url": "http://192.168.219.218/", "referrer_url": None},
                "page": {
                    "page_view_id": str(uuid4()),
                    "page_type": "home",
                    "url": "http://192.168.219.218/",
                    "path": "/",
                },
                "navigation": {
                    "from": None,
                    "to": {"site_id": "main", "url": "http://192.168.219.218/", "path": "/"},
                    "navigation_type": "direct",
                },
            }
            for offset in range(count)
        ],
    }


def require_clean_stage(result):
    if result["spawned"] != result["users"]:
        raise ValueError("stage_spawned_mismatch")
    if any(
        result.get(name, 0)
        for name in [
            "availability_errors",
            "all_phase_failed_requests",
            "contract_errors",
            "fixture_exhausted",
            "exit_code",
        ]
    ):
        raise ValueError("stage_not_clean")
