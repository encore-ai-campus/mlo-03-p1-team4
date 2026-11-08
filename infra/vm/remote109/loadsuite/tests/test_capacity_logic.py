"""HTTP가 정상이어도 이벤트 누락을 다음 단계에 넘기지 않는다."""

import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "capacity_logic", Path(__file__).parents[1] / "capacity_logic.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_audit_rejects_event_loss_and_remaining_slot():
    db = {
        "rows": [
            "users\t1",
            "cancelled\trefunded\t10",
            "remaining_slots\t0",
            "synthetic_reservations\t10\t10",
            "151\t0\t0",
        ],
        "replication": {},
    }
    data = {
        "dbs": [db, copy.deepcopy(db)],
        "mongo": {
            "own_event_names": [
                {"_id": "reservation_complete", "count": 10},
                {"_id": "reservation_cancel_complete", "count": 10},
            ],
            "own_events": 20,
            "own_synthetic_events": 20,
        },
    }
    assert module.audit_count(data) == 10
    data["mongo"]["own_event_names"][0]["count"] = 9
    with pytest.raises(ValueError, match="event_count_mismatch"):
        module.audit_count(data)
    data["mongo"]["own_event_names"][0]["count"] = 10
    data["dbs"][0]["rows"][2] = "remaining_slots\t1"
    with pytest.raises(ValueError, match="remaining_slots"):
        module.audit_count(data)


def test_latency_gate_requires_two_full_windows():
    rows = [
        {
            "started": n * 0.5,
            "finished": n * 0.5 + 0.01,
            "ms": 600,
            "failed": False,
            "method": "POST",
            "name": "/reservations",
            "status": 201,
        }
        for n in range(360)
    ]
    assert module.latency_failed(rows, 0, "book")
    assert not module.latency_failed(rows[:120], 0, "book")


def test_host_sample_is_mandatory_fresh_and_has_memory():
    good = {"time": 100, "vmware_windows_host": {"ram_free_kib": 16 * 1024**2}}
    module.validate_host_sample(good, 110)
    for record, now, reason in [
        ({}, 110, "host_observation_failed"),
        (good, 180, "host_observation_stale"),
        ({"time": 100, "vmware_windows_host": {"ram_free_kib": 1024}}, 110, "host_memory_low"),
    ]:
        with pytest.raises(ValueError, match=reason):
            module.validate_host_sample(record, now)
