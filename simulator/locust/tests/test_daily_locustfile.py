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
    run = configure_run(monkeypatch)
    for _ in range(4):
        run.environment.stats.log_request("GET", "GET /venues", 10, 10)
    run.target_users = 20
    run.peak_users = 20
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


# 회귀 검증: 기본 조회 모드·일일 상한·예상 충돌과 배선 오류를 구분한다.
def scenario_environment(profile, users=1):
    from locust.stats import RequestStats

    return SimpleNamespace(
        user_classes=[getattr(daily_locustfile, profile)],
        parsed_options=SimpleNamespace(num_users=users),
        runner=SimpleNamespace(user_count=users),
        stats=RequestStats(),
        process_exit_code=0,
    )


def configure_run(monkeypatch, profile="Student", users=1, writes=False):
    monkeypatch.setenv("SYNTHETIC_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LOCUST_DATES", "2026-11-06,2026-11-07")
    monkeypatch.delenv("LOCUST_ACCOUNTS_FILE", raising=False)
    monkeypatch.setenv("LOCUST_ALLOW_WRITES", "1" if writes else "0")
    return DailyRun(scenario_environment(profile, users))


def test_default_read_only_needs_no_accounts_and_sends_no_login_or_events(monkeypatch):
    run = configure_run(monkeypatch)
    assert run.allow_writes is False
    monkeypatch.setattr(daily_locustfile, "RUN", run)
    user = object.__new__(daily_locustfile.Student)

    class NoPost:
        def post(self, *_args, **_kwargs):
            pytest.fail("조회 모드는 POST를 보내면 안 됩니다.")

    user.client = NoPost()
    user.on_start()
    assert user.event("search") is True
    assert user.token == ""


@pytest.mark.parametrize(
    ("profile", "users"), [("Student", 21), ("Worker", 16), ("Gathering", 11), ("Explorer", 6)]
)
def test_daily_user_cap_rejects_capacity_test_sizes(monkeypatch, profile, users):
    with pytest.raises(ValueError, match="일일"):
        configure_run(monkeypatch, profile, users)


def test_booking_mode_requires_accounts_but_read_only_does_not(monkeypatch):
    with pytest.raises(ValueError, match="LOCUST_ACCOUNTS_FILE"):
        configure_run(monkeypatch, writes=True)


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (201, {"reservation_id": 7}, "created"),
        (200, {"reservation_id": 7}, "replayed"),
        (409, {"code": "SLOT_TAKEN"}, "conflict"),
        (409, {"code": "OTHER"}, "error"),
        (401, {"code": "UNAUTHORIZED"}, "error"),
        (400, {"code": "VALIDATION"}, "error"),
        (200, {}, "error"),
    ],
)
def test_only_expected_booking_conflict_is_accepted(status, body, expected):
    assert daily_locustfile.booking_outcome(status, body) == expected


def test_first_reservation_exhausts_default_budget(monkeypatch):
    run = configure_run(monkeypatch)
    monkeypatch.setattr(daily_locustfile, "RUN", run)
    user = object.__new__(daily_locustfile.Student)
    user.bookings = 0
    assert user.booking_budget_available() is True
    user.bookings = 1
    assert user.booking_budget_available() is False


def test_write_flag_typo_is_not_silently_enabled(monkeypatch):
    monkeypatch.setenv("SYNTHETIC_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LOCUST_DATES", "2026-11-06")
    monkeypatch.setenv("LOCUST_ALLOW_WRITES", "yes")
    with pytest.raises(ValueError, match="LOCUST_ALLOW_WRITES"):
        DailyRun(scenario_environment("Student"))


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body
        self.failed = False
        self.succeeded = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def json(self):
        return self.body

    def failure(self, _message):
        self.failed = True

    def success(self):
        self.succeeded = True


def prepared_student(monkeypatch):
    run = configure_run(monkeypatch)
    run.allow_writes = True
    monkeypatch.setattr(daily_locustfile, "RUN", run)
    user = object.__new__(daily_locustfile.Student)
    user.headers = {"X-Synthetic": "1"}
    user.bookings = 0
    user.session_id = "00000000-0000-4000-8000-000000000001"
    user.event = lambda *_args: True
    monkeypatch.setattr(daily_locustfile.random, "choice", lambda values: values[0])
    monkeypatch.setattr(daily_locustfile.random, "shuffle", lambda _values: None)
    run.dates = ["2026-11-06"]

    def get_json(path, **_kwargs):
        if path == "/venues":
            return {"items": [{"venue_id": 1}, {"venue_id": 2}, {"venue_id": 3}]}
        if path.endswith("/slots"):
            return [{"hour": hour, "taken": False} for hour in range(14, 18)]
        return {"min_hours": 1, "capacity_max": 8}

    user.get_json = get_json
    return run, user


def test_booking_budget_stops_additional_posts_after_one_success(monkeypatch):
    run, user = prepared_student(monkeypatch)
    calls = []

    def post(path, **kwargs):
        calls.append((path, kwargs))
        return FakeResponse(201, {"reservation_id": 7})

    user.client = SimpleNamespace(post=post)
    user.visit()
    user.visit()
    assert len(calls) == 1
    assert user.bookings == 1
    assert run.outcomes["created"] == 1


def test_slot_conflict_retries_at_most_two_alternatives(monkeypatch):
    run, user = prepared_student(monkeypatch)
    responses = []

    def post(*_args, **_kwargs):
        response = FakeResponse(409, {"code": "SLOT_TAKEN"})
        responses.append(response)
        return response

    user.client = SimpleNamespace(post=post)
    user.visit()
    assert len(responses) == 3
    assert all(r.succeeded and not r.failed for r in responses)
    assert run.outcomes["conflict"] == 3
    assert user.bookings == 0


def test_invalid_synthetic_key_is_a_failure_not_expected_conflict(monkeypatch):
    run, user = prepared_student(monkeypatch)
    response = FakeResponse(401, {"code": "UNAUTHORIZED"})
    user.client = SimpleNamespace(post=lambda *_args, **_kwargs: response)
    user.visit()
    assert response.failed and not response.succeeded
    assert run.issues["reservation_failed"] == 1


def test_http_401_count_is_separate_from_server_error_count(monkeypatch):
    run = configure_run(monkeypatch)
    monkeypatch.setattr(daily_locustfile, "RUN", run)
    daily_locustfile.on_request(response=FakeResponse(401, {}))
    daily_locustfile.on_request(response=FakeResponse(503, {}))
    daily_locustfile.on_request(response=None, exception=TimeoutError())
    assert run.statuses == {"401": 1, "503": 1, "0": 1}
    assert run.server_errors == 2
    assert run.peak_users == 1


@pytest.mark.parametrize("bad_slots", [{}, None, [{"hour": "14", "taken": False}]])
def test_read_only_still_rejects_malformed_slot_response(monkeypatch, bad_slots):
    run, user = prepared_student(monkeypatch)
    run.allow_writes = False
    original = user.get_json
    user.get_json = lambda path, **kwargs: (
        bad_slots if path.endswith("/slots") else original(path, **kwargs)
    )
    user.visit()
    assert run.issues["invalid_slots"] > 0


def test_non_object_venue_is_reported_not_unhandled(monkeypatch):
    run, user = prepared_student(monkeypatch)
    user.get_json = lambda *_args, **_kwargs: {"items": [None]}
    user.visit()
    assert run.issues["invalid_venue"] == 1


def test_task_exception_marks_failure_without_recording_exception_text(monkeypatch):
    run = configure_run(monkeypatch)
    monkeypatch.setattr(daily_locustfile, "RUN", run)
    daily_locustfile.on_user_error(None, RuntimeError("DO_NOT_LOG"), None)
    assert run.issues == {"task_exception": 1}
