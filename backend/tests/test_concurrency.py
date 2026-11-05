"""F-32: 실제 MariaDB 기본키가 50개 동시 요청 중 한 요청만 확정하는지 확인한다."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user
from app.core.errors import register_error_handlers
from app.core.metrics import reservation_counter
from app.routers.reservations import router
from app.services import reservation_service

TODAY = date(2026, 11, 5)
NOW = datetime.fromisoformat("2026-11-05T12:00:00")
REQUEST_COUNT = 50


def _database_url():
    raw = os.environ.get("CHECK_DB_URL")
    if not raw:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 접속 정보를 지정해 주세요.")
    url = make_url(raw)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("로컬 MariaDB spacecube_test에서만 실행합니다.")
    return url


def _create_test_rows(engine):
    emails = [f"{uuid4().hex}@example.invalid" for _ in range(REQUEST_COUNT)]
    user_ids = []
    with engine.begin() as connection:
        connection.execute(text("SET time_zone = '+09:00'"))
        category_id = connection.scalar(text("SELECT MIN(category_id) FROM categories"))
        region_id = connection.scalar(text("SELECT MIN(region_id) FROM regions"))
        assert category_id is not None and region_id is not None, "기존 seed.sql 적용이 필요합니다."
        for email in emails:
            user_ids.append(
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(email,password_hash,name,birth,gender_digit,terms_agreed_at,privacy_agreed_at,is_synthetic) "
                        "VALUES (:email,'unused-test-hash','동시성 검증 회원','000101','3',:now,:now,FALSE)"
                    ),
                    {"email": email, "now": NOW},
                ).lastrowid
            )
        venue_id = connection.execute(
            text(
                "INSERT INTO venues "
                "(region_id,category_id,name,capacity_max,price_per_hour,min_hours,open_hour,close_hour,source_site,source_id) "
                "VALUES (:region,:category,'동시성 검증 공간',6,11000,1,9,23,'synthetic',:source_id)"
            ),
            {"region": region_id, "category": category_id, "source_id": uuid4().hex},
        ).lastrowid
    return venue_id, user_ids


def _delete_test_rows(engine, venue_id, user_ids):
    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM payments WHERE reservation_id IN "
                "(SELECT reservation_id FROM reservations WHERE venue_id=:venue)"
            ),
            {"venue": venue_id},
        )
        connection.execute(
            text("DELETE FROM reservations WHERE venue_id=:venue"), {"venue": venue_id}
        )
        connection.execute(text("DELETE FROM venues WHERE venue_id=:venue"), {"venue": venue_id})
        for user_id in user_ids:
            connection.execute(text("DELETE FROM users WHERE user_id=:user"), {"user": user_id})


def _create_app(engine):
    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.include_router(router, prefix="/reservations")

    def test_db():
        with Session(bind=engine) as db:
            yield db

    def test_user(request: Request):
        return CurrentUser(int(request.headers["X-Test-User-Id"]))

    test_app.dependency_overrides[get_db_write] = test_db
    test_app.dependency_overrides[get_current_user] = test_user
    event_log = []
    event_lock = Lock()

    def record_event(*args, **kwargs):
        with event_lock:
            event_log.append((args[2], args[1]))

    return test_app, event_log, record_event


def _run_concurrently(test_app, requests):
    barrier = Barrier(len(requests))

    def submit(item):
        user_id, body = item
        barrier.wait(timeout=30)
        return test_client.post(
            "/reservations",
            json=body,
            headers={"X-Test-User-Id": str(user_id)},
        )

    with (
        TestClient(test_app, raise_server_exceptions=False) as test_client,
        ThreadPoolExecutor(max_workers=len(requests)) as pool,
    ):
        return list(pool.map(submit, requests))


def _run_cancel_concurrently(test_app, reservation_id, user_id):
    barrier = Barrier(2)

    def submit(_):
        barrier.wait(timeout=30)
        return test_client.post(
            f"/reservations/{reservation_id}/cancel",
            headers={"X-Test-User-Id": str(user_id)},
        )

    with (
        TestClient(test_app, raise_server_exceptions=False) as test_client,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        return list(pool.map(submit, range(2)))


@pytest.fixture
def concurrency_environment(monkeypatch):
    engine = create_engine(_database_url(), poolclass=NullPool, hide_parameters=True)
    venue_id = None
    user_ids = []
    try:
        venue_id, user_ids = _create_test_rows(engine)
        test_app, event_log, record_event = _create_app(engine)
        monkeypatch.setattr(reservation_service, "get_today", lambda: TODAY)
        monkeypatch.setattr(reservation_service, "get_now", lambda: NOW)
        monkeypatch.setattr(reservation_service, "log_event", record_event)
        yield {
            "engine": engine,
            "venue_id": venue_id,
            "user_ids": user_ids,
            "app": test_app,
            "events": event_log,
            "before_ok": reservation_counter.labels(result="ok")._value.get(),
            "before_conflict": reservation_counter.labels(result="conflict")._value.get(),
        }
    finally:
        if venue_id is not None:
            _delete_test_rows(engine, venue_id, user_ids)
        engine.dispose()


def _booking(venue_id, *, start_hour=13, hours=1):
    return {
        "venue_id": venue_id,
        "date": (TODAY + timedelta(days=1)).isoformat(),
        "start_hour": start_hour,
        "hours": hours,
        "headcount": 2,
        "method": "card",
    }


def _reservation_count(engine, venue_id):
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT COUNT(*) FROM reservations WHERE venue_id=:venue"),
            {"venue": venue_id},
        )


def test_same_slot_with_fifty_simultaneous_users_has_one_winner(concurrency_environment):
    state = concurrency_environment
    body = _booking(state["venue_id"])
    responses = _run_concurrently(state["app"], [(user_id, body) for user_id in state["user_ids"]])

    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == 1
    assert statuses.count(409) == REQUEST_COUNT - 1
    for response in responses:
        if response.status_code == 409:
            assert response.json()["code"] == "SLOT_TAKEN"
            assert response.json()["detail"] == {"slots": [13]}

    assert _reservation_count(state["engine"], state["venue_id"]) == 1
    with state["engine"].connect() as connection:
        reservation_id = connection.scalar(
            text("SELECT reservation_id FROM reservations WHERE venue_id=:venue"),
            {"venue": state["venue_id"]},
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM payments WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 1
        )

    assert reservation_counter.labels(result="ok")._value.get() == state["before_ok"] + 1
    assert (
        reservation_counter.labels(result="conflict")._value.get()
        == state["before_conflict"] + REQUEST_COUNT - 1
    )
    assert sum(event[0] == "reserve_ok" for event in state["events"]) == 1
    assert sum(event[0] == "reserve_conflict" for event in state["events"]) == REQUEST_COUNT - 1


def test_same_user_retries_sent_simultaneously_share_one_reservation(concurrency_environment):
    state = concurrency_environment
    body = _booking(state["venue_id"])
    user_id = state["user_ids"][0]
    responses = _run_concurrently(state["app"], [(user_id, body) for _ in range(REQUEST_COUNT)])

    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == 1
    assert statuses.count(200) == REQUEST_COUNT - 1
    assert len({response.json()["reservation_id"] for response in responses}) == 1
    assert _reservation_count(state["engine"], state["venue_id"]) == 1
    with state["engine"].connect() as connection:
        reservation_id = connection.scalar(
            text("SELECT reservation_id FROM reservations WHERE venue_id=:venue"),
            {"venue": state["venue_id"]},
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM payments WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 1
        )

    assert reservation_counter.labels(result="ok")._value.get() == state["before_ok"] + 1
    assert reservation_counter.labels(result="conflict")._value.get() == state["before_conflict"]
    assert [event[0] for event in state["events"]] == ["reserve_ok"]


def test_simultaneous_overlapping_windows_leave_one_booking(concurrency_environment):
    state = concurrency_environment
    requests = [
        (state["user_ids"][0], _booking(state["venue_id"], start_hour=13, hours=2)),
        (state["user_ids"][1], _booking(state["venue_id"], start_hour=14, hours=2)),
    ]
    responses = _run_concurrently(state["app"], requests)

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "SLOT_TAKEN"
    assert conflict.json()["detail"] == {"slots": [14]}
    assert _reservation_count(state["engine"], state["venue_id"]) == 1
    with state["engine"].connect() as connection:
        reservation_id = connection.scalar(
            text("SELECT reservation_id FROM reservations WHERE venue_id=:venue"),
            {"venue": state["venue_id"]},
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM payments WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 2
        )

    assert reservation_counter.labels(result="ok")._value.get() == state["before_ok"] + 1
    assert (
        reservation_counter.labels(result="conflict")._value.get() == state["before_conflict"] + 1
    )
    assert sorted(event[0] for event in state["events"]) == ["reserve_conflict", "reserve_ok"]


def test_two_simultaneous_cancellations_commit_once(concurrency_environment):
    state = concurrency_environment
    user_id = state["user_ids"][0]
    before_cancel = reservation_counter.labels(result="cancel")._value.get()
    with TestClient(state["app"], raise_server_exceptions=False) as client:
        created = client.post(
            "/reservations",
            json=_booking(state["venue_id"]),
            headers={"X-Test-User-Id": str(user_id)},
        )
    assert created.status_code == 201
    reservation_id = created.json()["reservation_id"]

    responses = _run_cancel_concurrently(state["app"], reservation_id, user_id)

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "ALREADY_CANCELLED"
    assert sum(response.status_code == 200 for response in responses) == 1
    with state["engine"].connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM reservations WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == "cancelled"
        )
        assert (
            connection.scalar(
                text("SELECT status FROM payments WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == "refunded"
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 0
        )

    assert reservation_counter.labels(result="cancel")._value.get() == before_cancel + 1
    assert sum(event[0] == "reserve_cancel_ok" for event in state["events"]) == 1
