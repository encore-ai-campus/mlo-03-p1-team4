"""#20: 매일 실행의 날짜·칸 선택에서 실제 예약 규칙을 확인한다."""

import json
from collections import Counter
from types import SimpleNamespace

import pytest

from simulator.locust import daily_locustfile
from simulator.locust.daily_locustfile import DailyRun, candidate_hours, load_dates, preferred_hours


def test_persona_windows_and_contiguous_slots():
    slots = [
        {"hour": 13, "taken": False},
        {"hour": 14, "taken": False},
        {"hour": 15, "taken": True},
        {"hour": 16, "taken": False},
        {"hour": 17, "taken": False},
        {"hour": 18, "taken": False},
        {"hour": 19, "taken": False},
    ]
    starts = candidate_hours(slots, 2)
    assert starts == [13, 16, 17, 18]
    assert preferred_hours("Student", "2026-11-06", starts, 2) == [16]
    assert preferred_hours("Student", "2026-11-07", starts, 2) == []
    assert preferred_hours("Gathering", "2026-11-07", starts, 2) == [13, 16]
    assert preferred_hours("Worker", "2026-11-06", starts, 2) == []


def test_dates_require_actual_iso_dates():
    assert load_dates("2026-11-06,2026-11-07") == ["2026-11-06", "2026-11-07"]
    with pytest.raises(ValueError):
        load_dates("2026-02-30")
    with pytest.raises(ValueError):
        load_dates("2026-11-06T14:00:00")


def test_run_summary_sent_to_loki_without_account_data(monkeypatch, tmp_path):
    sent = []

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def push(request, timeout):
        assert timeout == 5
        sent.append(json.loads(request.data))
        return Response()

    monkeypatch.setattr(daily_locustfile, "urlopen", push)
    monkeypatch.setenv("LOCUST_LOKI_PUSH_URL", "http://localhost:3100/loki/api/v1/push")
    output = tmp_path / "daily-runs.jsonl"
    monkeypatch.setenv("LOCUST_RUN_LOG", str(output))
    run = object.__new__(DailyRun)
    run.environment = SimpleNamespace(
        stats=SimpleNamespace(total=SimpleNamespace(num_requests=4, num_failures=0)),
        process_exit_code=0,
    )
    run.run_id = "run-test"
    run.profile = "Student"
    run.started_at = "2026-11-06T14:00:00+09:00"
    run.target_users = 20
    run.statuses = Counter({"200": 3, "201": 1})
    run.issues = Counter()
    run.finish()

    local = json.loads(output.read_text(encoding="utf-8"))
    assert local["requests"] == 4
    assert local["loki_delivery"] == "success"
    assert sent[0]["streams"][0]["stream"] == {"job": "locust_daily", "profile": "Student"}
    remote = json.loads(sent[0]["streams"][0]["values"][0][1])
    assert remote["run_id"] == local["run_id"]
    assert "email" not in json.dumps(remote)
    assert "password" not in json.dumps(remote)
