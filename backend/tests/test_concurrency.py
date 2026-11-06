"""F-04·32: 실제 MariaDB에서 예약 경쟁과 탈퇴 직렬화를 검증한다."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier, Event, Lock, get_ident
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user
from app.core.errors import AppError, register_error_handlers
from app.core.metrics import reservation_counter
from app.models.user import User
from app.repositories import reservation_repo
from app.routers.reservations import router
from app.services import reservation_service, user_service

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
        monkeypatch.setattr(reservation_repo, "get_now", lambda: NOW)
        monkeypatch.setattr(user_service, "get_now", lambda: NOW)
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


def _authenticate(db, user_id, authenticated=None, before_service=None):
    """실제 인증 의존성으로 스냅샷을 열고 양쪽 요청의 인증 완료를 맞춘다."""
    request = Request({"type": "http", "headers": []})
    assert get_current_user(request, user_id, db).user_id == user_id
    if authenticated is not None:
        authenticated.wait(timeout=10)
    if before_service is not None:
        assert before_service.wait(10)


def _create_booking(state, user_id, body, authenticated=None, before_service=None):
    with Session(bind=state["engine"]) as db:
        _authenticate(db, user_id, authenticated, before_service)
        return reservation_service.create_reservation(
            db,
            reservation_service.ReservationCreate.model_validate(body),
            user_id=user_id,
            session_id=None,
            is_synthetic=False,
        )


def _withdraw(state, user_id, authenticated=None, before_service=None):
    with Session(bind=state["engine"]) as db:
        try:
            _authenticate(db, user_id, authenticated, before_service)
            user_service.withdraw(db, user_id)
            return None
        except AppError as error:
            return error


def _reservation_rows_for_user(engine, user_id):
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT COUNT(*) FROM reservations WHERE user_id=:user"), {"user": user_id}
        )


def _assert_booking_rows(state, user_id, expected):
    """다른 연결에서 예약·칸·결제의 최종 커밋 결과를 확인한다."""
    with state["engine"].connect() as connection:
        for query in (
            "SELECT COUNT(*) FROM reservations WHERE user_id=:user",
            "SELECT COUNT(*) FROM reservation_slots s JOIN reservations r "
            "ON r.reservation_id=s.reservation_id WHERE r.user_id=:user",
            "SELECT COUNT(*) FROM payments p JOIN reservations r "
            "ON r.reservation_id=p.reservation_id WHERE r.user_id=:user",
        ):
            assert connection.scalar(text(query), {"user": user_id}) == expected


def test_booking_lock_makes_withdrawal_observe_committed_reservation(
    concurrency_environment, monkeypatch
):
    """예약이 회원 잠금을 먼저 잡으면 탈퇴가 커밋된 예약을 보고 409를 반환한다."""
    state = concurrency_environment
    user_id = state["user_ids"][0]
    body = _booking(state["venue_id"])
    authenticated = Barrier(2)
    booking_paused = Event()
    release_booking = Event()
    withdraw_lock_attempted = Event()
    booking_thread_id = {}
    original_create = reservation_service.reservation_repo.create
    original_get_active = user_service.user_repo.get_active

    def pause_booking_after_member_lock(*args, **kwargs):
        booking_paused.set()
        assert release_booking.wait(10)
        return original_create(*args, **kwargs)

    def observe_withdraw_lock(db, user_id, *, for_update=False):
        if for_update:
            if "id" not in booking_thread_id:
                booking_thread_id["id"] = get_ident()
            elif get_ident() != booking_thread_id["id"]:
                withdraw_lock_attempted.set()
        return original_get_active(db, user_id, for_update=for_update)

    monkeypatch.setattr(
        reservation_service.reservation_repo, "create", pause_booking_after_member_lock
    )
    monkeypatch.setattr(user_service.user_repo, "get_active", observe_withdraw_lock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        booking = pool.submit(_create_booking, state, user_id, body, authenticated)
        withdrawal = pool.submit(_withdraw, state, user_id, authenticated, booking_paused)
        assert booking_paused.wait(10)
        assert withdraw_lock_attempted.wait(10)
        release_booking.set()
        _, booking_status = booking.result(timeout=15)
        withdrawal_error = withdrawal.result(timeout=15)

    assert booking_status == 201
    assert isinstance(withdrawal_error, AppError)
    assert withdrawal_error.code == "HAS_UPCOMING_RESERVATION"
    assert withdrawal_error.status == 409
    assert withdrawal_error.detail == {"count": 1}
    _assert_booking_rows(state, user_id, 1)


def test_withdrawal_lock_makes_waiting_booking_reject_inactive_user(
    concurrency_environment, monkeypatch
):
    """탈퇴가 회원 잠금을 먼저 잡으면 대기 중인 예약은 최신 탈퇴 상태로 401이다."""
    state = concurrency_environment
    user_id = state["user_ids"][0]
    body = _booking(state["venue_id"])
    authenticated = Barrier(2)
    withdrawal_paused = Event()
    release_withdrawal = Event()
    booking_lock_attempted = Event()
    withdrawal_thread_id = {}
    original_count = reservation_repo.count_cancellable
    original_get_active = reservation_service.user_repo.get_active

    def pause_withdraw_after_member_lock(db, locked_user_id):
        withdrawal_thread_id["id"] = get_ident()
        count = original_count(db, locked_user_id)
        withdrawal_paused.set()
        assert release_withdrawal.wait(10)
        return count

    def observe_booking_lock(db, locked_user_id, *, for_update=False):
        if for_update and get_ident() != withdrawal_thread_id.get("id"):
            booking_lock_attempted.set()
        return original_get_active(db, locked_user_id, for_update=for_update)

    monkeypatch.setattr(reservation_repo, "count_cancellable", pause_withdraw_after_member_lock)
    monkeypatch.setattr(reservation_service.user_repo, "get_active", observe_booking_lock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        withdrawal = pool.submit(_withdraw, state, user_id, authenticated)
        booking = pool.submit(
            _create_booking, state, user_id, body, authenticated, withdrawal_paused
        )
        assert withdrawal_paused.wait(10)
        assert booking_lock_attempted.wait(10)
        release_withdrawal.set()
        assert withdrawal.result(timeout=15) is None
        try:
            booking_error = booking.result(timeout=15)
        except AppError as error:
            booking_error = error

    assert isinstance(booking_error, AppError)
    assert booking_error.code == "UNAUTHORIZED"
    assert booking_error.status == 401
    _assert_booking_rows(state, user_id, 0)


def test_count_cancellable_uses_current_read_after_old_snapshot(
    concurrency_environment, monkeypatch
):
    """먼저 열린 일관 읽기 스냅샷 뒤에 커밋된 예약도 탈퇴 집계가 본다."""
    state = concurrency_environment
    user_id = state["user_ids"][0]
    monkeypatch.setattr(reservation_repo, "get_now", lambda: NOW)
    with Session(bind=state["engine"]) as db:
        assert db.scalar(select(User).where(User.user_id == user_id)) is not None
        with state["engine"].begin() as writer:
            writer.execute(
                text(
                    "INSERT INTO reservations "
                    "(user_id,venue_id,reserve_date,start_hour,end_hour,headcount,total_price,status,is_synthetic) "
                    "VALUES (:user,:venue,:date,13,14,2,11000,'confirmed',FALSE)"
                ),
                {"user": user_id, "venue": state["venue_id"], "date": TODAY + timedelta(days=1)},
            )
        assert reservation_repo.count_cancellable(db, user_id) == 1


def test_duplicate_slot_rollback_rechecks_user_before_retry_result(
    concurrency_environment, monkeypatch
):
    """슬롯 충돌 롤백으로 회원 잠금이 풀린 사이 탈퇴하면 재시도는 401이다."""
    state = concurrency_environment
    winner_id, losing_user_id = state["user_ids"][:2]
    body = _booking(state["venue_id"])
    _create_booking(state, winner_id, body)

    relock_reached = Event()
    release_relock = Event()
    booking_thread_id = None
    lock_calls = 0
    original_get_active = reservation_service.user_repo.get_active

    def pause_relock_after_rollback(db, user_id, *, for_update=False):
        nonlocal booking_thread_id, lock_calls
        if for_update and user_id == losing_user_id:
            if booking_thread_id is None:
                booking_thread_id = get_ident()
            if get_ident() == booking_thread_id:
                lock_calls += 1
                if lock_calls == 2:
                    relock_reached.set()
                    assert release_relock.wait(10)
        return original_get_active(db, user_id, for_update=for_update)

    monkeypatch.setattr(reservation_service.user_repo, "get_active", pause_relock_after_rollback)
    with ThreadPoolExecutor(max_workers=2) as pool:
        booking = pool.submit(_create_booking, state, losing_user_id, body)
        assert relock_reached.wait(10)
        withdrawal = pool.submit(_withdraw, state, losing_user_id)
        assert withdrawal.result(timeout=15) is None
        release_relock.set()
        try:
            booking_error = booking.result(timeout=15)
        except AppError as error:
            booking_error = error

    assert isinstance(booking_error, AppError)
    assert booking_error.code == "UNAUTHORIZED"
    _assert_booking_rows(state, losing_user_id, 0)
    assert _reservation_rows_for_user(state["engine"], winner_id) == 1


@pytest.mark.parametrize("failure", ["validation", "payment"])
def test_booking_failure_rolls_back_rows_and_releases_member_lock(
    concurrency_environment, monkeypatch, failure
):
    """실패한 서비스의 세션이 열린 상태에서도 뒤 탈퇴가 잠금을 얻어 성공한다."""
    state = concurrency_environment
    user_id = state["user_ids"][0]
    body = _booking(state["venue_id"])
    if failure == "validation":
        body["method"] = "invalid"
        expected = AppError
    else:

        def fail_payment(*args, **kwargs):
            raise RuntimeError("테스트 결제 저장 실패")

        monkeypatch.setattr(reservation_service.payment_repo, "create", fail_payment)
        expected = RuntimeError
    with Session(bind=state["engine"]) as db:
        _authenticate(db, user_id)
        with pytest.raises(expected):
            reservation_service.create_reservation(
                db,
                reservation_service.ReservationCreate.model_validate(body),
                user_id=user_id,
                session_id=None,
                is_synthetic=False,
            )
        assert not db.in_transaction()
        _assert_booking_rows(state, user_id, 0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(_withdraw, state, user_id).result(timeout=10) is None


def test_successful_retry_releases_member_lock(concurrency_environment):
    """재시도 200도 트랜잭션을 닫아 뒤 탈퇴의 잠금 획득을 막지 않는다."""
    state = concurrency_environment
    user_id = state["user_ids"][0]
    body = _booking(state["venue_id"])
    first, _ = _create_booking(state, user_id, body)
    with Session(bind=state["engine"]) as db:
        _authenticate(db, user_id)
        retry, status = reservation_service.create_reservation(
            db,
            reservation_service.ReservationCreate.model_validate(body),
            user_id=user_id,
            session_id=None,
            is_synthetic=False,
        )
        assert status == 200
        assert retry.reservation_id == first.reservation_id
        assert not db.in_transaction()
        with ThreadPoolExecutor(max_workers=1) as pool:
            error = pool.submit(_withdraw, state, user_id).result(timeout=10)
        assert isinstance(error, AppError)
        assert error.code == "HAS_UPCOMING_RESERVATION"
    _assert_booking_rows(state, user_id, 1)


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
    assert sum(event[0] == "reservation_complete" for event in state["events"]) == 1
    assert sum(event[0] == "reservation_conflict" for event in state["events"]) == REQUEST_COUNT - 1


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
    assert [event[0] for event in state["events"]] == ["reservation_complete"]


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
    assert sorted(event[0] for event in state["events"]) == [
        "reservation_complete",
        "reservation_conflict",
    ]


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
    assert sum(event[0] == "reservation_cancel_complete" for event in state["events"]) == 1
