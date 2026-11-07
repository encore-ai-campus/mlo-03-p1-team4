import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("load_logic", Path(__file__).parents[1] / "logic.py")
logic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logic)


def test_blocks_respect_minimum_and_do_not_overlap():
    venues = [
        {"venue_id": 7, "open_hour": 9, "close_hour": 20, "min_hours": 3, "price_per_hour": 100}
    ]
    blocks = logic.allocate_blocks(venues, "2026-11-08", 2)
    assert len(blocks) == 6
    occupied = [
        (b["date"], h) for b in blocks for h in range(b["start_hour"], b["start_hour"] + b["hours"])
    ]
    assert len(occupied) == len(set(occupied))
    assert all(b["hours"] == 3 and b["start_hour"] + b["hours"] <= 20 for b in blocks)


def test_reservation_must_match_amount_and_confirmed_state():
    body = {
        "venue_id": 7,
        "date": "2026-11-08",
        "start_hour": 9,
        "hours": 3,
        "headcount": 1,
        "method": "card",
    }
    receipt = {
        "reservation_id": 1,
        "venue_id": 7,
        "date": "2026-11-08",
        "start_hour": 9,
        "end_hour": 12,
        "headcount": 1,
        "total_price": 300,
        "status": "confirmed",
        "payment": {"status": "paid", "method": "card"},
    }
    logic.check_reservation(body, receipt, 100, "confirmed")
    with pytest.raises(ValueError, match="total_price"):
        logic.check_reservation(body, {**receipt, "total_price": 1}, 100, "confirmed")


def test_only_matching_expected_domain_error_is_allowed():
    assert logic.classify_status(409, "SLOT_TAKEN", {409: "SLOT_TAKEN"}) == "expected"
    assert logic.classify_status(409, "ALREADY_CANCELLED", {409: "SLOT_TAKEN"}) == "contract"
    assert logic.classify_status(409, "SLOT_TAKEN", {}) == "contract"
    assert logic.classify_status(503, None, {}) == "availability"
    assert logic.classify_status(0, None, {}) == "availability"


def test_measurement_excludes_warmup_and_crossing_requests():
    rows = [
        {"started": 5, "finished": 11},
        {"started": 10, "finished": 12},
        {"started": 19, "finished": 21},
    ]
    assert logic.measured_rows(rows, 10, 20) == [rows[1]]


def test_event_batch_includes_v1_user_context_and_unique_event_ids():
    session = "9414c39c-6f35-46d1-aeaf-e1334ec137bd"
    batch = logic.build_event_batch(session, 10, 7)
    assert batch["session_id"] == session
    assert len(batch["events"]) == 10
    assert all(
        e["schema_version"] == 1 and e["user"]["session_id"] == session for e in batch["events"]
    )
    assert [e["user"]["session_sequence"] for e in batch["events"]] == list(range(7, 17))
    assert len({e["event_id"] for e in batch["events"]}) == 10
    assert all(
        e["page"]["url"] == e["acquisition"]["landing_url"] == e["navigation"]["to"]["url"]
        for e in batch["events"]
    )


def test_observation_rejects_empty_down_stale_and_failed_node_samples():
    import copy

    names = [
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
    ]
    record = {"time": 1000, "metrics": {name: [{"value": [1000, "1"]}] for name in names}}
    for name, count, value in [
        ("up", 19, "1"),
        ("backend", 2, "1"),
        ("mysql_up", 2, "1"),
        ("app_metrics_error", 2, "0"),
        ("app_metrics_timestamp", 2, "995"),
    ]:
        record["metrics"][name] = [{"value": [1000, value]} for _ in range(count)]
    logic.validate_observation(record)
    for name, replacement in [
        ("cpu", []),
        ("up", [{"value": [1000, "0"]}]),
        ("app_metrics_timestamp", [{"value": [1000, "800"]}]),
        ("app_metrics_error", [{"value": [1000, "1"]}]),
    ]:
        bad = copy.deepcopy(record)
        bad["metrics"][name] = replacement
        with pytest.raises(ValueError):
            logic.validate_observation(bad)
    bad = copy.deepcopy(record)
    bad["direct_7node_sample"] = {"nodes": [{"server": "mongo", "error": "ssh_failed"}]}
    with pytest.raises(ValueError, match="direct_node"):
        logic.validate_observation(bad)


def test_observation_allows_collection_crossing_fresh_timestamp():
    # record.time은 수집 시작 시각이다. 수집 중 SQL 집계가 갱신될 수 있다.
    record = {"time": 1000, "metrics": {}}
    for name in [
        "cpu",
        "memory",
        "disk_free",
        "app_connections",
        "db_connections",
        "db_running",
        "db_max_connections",
        "db_replica_lag",
    ]:
        record["metrics"][name] = [{"value": [1000, "1"]}]
    for name, count, value in [
        ("up", 19, "1"),
        ("backend", 2, "1"),
        ("mysql_up", 2, "1"),
        ("app_metrics_error", 2, "0"),
        ("app_metrics_timestamp", 2, "1002"),
    ]:
        record["metrics"][name] = [{"value": [1000, value]} for _ in range(count)]
    logic.validate_observation(record)
    record["metrics"]["app_metrics_timestamp"][0]["value"][1] = "1020"
    with pytest.raises(ValueError, match="stale_app_metrics"):
        logic.validate_observation(record)


def test_write_stage_stops_even_for_one_error_below_one_percent():
    clean = {
        "users": 400,
        "spawned": 400,
        "availability_errors": 0,
        "all_phase_failed_requests": 0,
        "contract_errors": 0,
        "fixture_exhausted": 0,
        "exit_code": 0,
    }
    logic.require_clean_stage(clean)
    for field in [
        "availability_errors",
        "all_phase_failed_requests",
        "contract_errors",
        "fixture_exhausted",
        "exit_code",
    ]:
        with pytest.raises(ValueError, match="stage_not_clean"):
            logic.require_clean_stage({**clean, field: 1})
    with pytest.raises(ValueError, match="spawned"):
        logic.require_clean_stage({**clean, "spawned": 399})
