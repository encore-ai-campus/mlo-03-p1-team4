"""F-30~32: 예약 API의 입력·트랜잭션·재시도·충돌을 로컬 MariaDB로 검증한다."""

import os
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core import synthetic
from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user
from app.core.errors import AppError
from app.core.metrics import reservation_counter
from app.main import create_app
from app.services import reservation_service

TODAY = date(2026, 11, 5)
NOW = datetime.fromisoformat("2026-11-05T12:00:00")


@pytest.fixture
def connection():
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
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            assert conn.scalar(text("SELECT DATABASE()")) == "spacecube_test"
            assert "MariaDB" in conn.scalar(text("SELECT VERSION()"))
            conn.execute(text("SET time_zone = '+09:00'"))
            conn.execute(
                text(
                    "SET SESSION sql_mode = "
                    "'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'"
                )
            )
            try:
                yield conn
            finally:
                outer.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def sample(connection):
    category_id = connection.scalar(text("SELECT MIN(category_id) FROM categories"))
    region_id = connection.scalar(text("SELECT MIN(region_id) FROM regions"))
    assert category_id is not None and region_id is not None, "기존 seed.sql 적용이 필요합니다."

    def create_user():
        return connection.execute(
            text(
                "INSERT INTO users "
                "(email,password_hash,name,birth,gender_digit,terms_agreed_at,privacy_agreed_at,is_synthetic) "
                "VALUES (:email,'unused-test-hash','예약 검증 회원','000101','3',:now,:now,FALSE)"
            ),
            {"email": f"{uuid4().hex}@example.invalid", "now": NOW},
        ).lastrowid

    user_id = create_user()
    venue_id = connection.execute(
        text(
            "INSERT INTO venues "
            "(region_id,category_id,name,capacity_max,price_per_hour,min_hours,open_hour,close_hour,source_site,source_id) "
            "VALUES (:region,:category,'예약 검증 공간',6,11000,1,9,23,'synthetic',:source_id)"
        ),
        {"region": region_id, "category": category_id, "source_id": uuid4().hex},
    ).lastrowid
    return {"user_id": user_id, "venue_id": venue_id, "create_user": create_user}


@pytest.fixture
def api(connection, sample, monkeypatch):
    test_app = create_app()

    def test_db():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db

    def test_user(request: Request):
        user_id = int(request.headers.get("X-Test-User-Id", sample["user_id"]))
        return CurrentUser(user_id)

    event_log = []

    def record_event(*args, **kwargs):
        event_log.append((args[2], kwargs))

    test_app.state.booking_events = event_log
    test_app.dependency_overrides[get_db_write] = test_db
    test_app.dependency_overrides[get_current_user] = test_user
    monkeypatch.setattr(reservation_service, "get_today", lambda: TODAY)
    monkeypatch.setattr(reservation_service, "get_now", lambda: NOW)
    monkeypatch.setattr(reservation_service, "log_event", record_event)
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


def booking(venue_id, *, day=TODAY + timedelta(days=1), start=13, hours=2, people=2, method="card"):
    return {
        "venue_id": venue_id,
        "date": day.isoformat(),
        "start_hour": start,
        "hours": hours,
        "headcount": people,
        "method": method,
    }


def count_venue_reservations(connection, venue_id):
    return connection.scalar(
        text("SELECT COUNT(*) FROM reservations WHERE venue_id=:venue"), {"venue": venue_id}
    )


def count_reservation_payments(connection, reservation_id):
    return connection.scalar(
        text("SELECT COUNT(*) FROM payments WHERE reservation_id=:id"), {"id": reservation_id}
    )


def count_reservation_slots(connection, reservation_id):
    return connection.scalar(
        text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
        {"id": reservation_id},
    )


def test_main_exposes_booking_contract_and_requires_authentication(connection, sample, api):
    """공식 앱에서 경로·201/200/409 계약과 인증 전 예약 차단을 확인한다."""
    operation = api.get("/openapi.json").json()["paths"]["/reservations"]["post"]
    assert {"200", "201", "409"} <= operation["responses"].keys()
    override = api.app.dependency_overrides.pop(get_current_user)
    try:
        response = api.post("/reservations", json=booking(sample["venue_id"]))
    finally:
        api.app.dependency_overrides[get_current_user] = override
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert count_venue_reservations(connection, sample["venue_id"]) == 0


def test_unconfigured_synthetic_key_rejects_booking(connection, sample, api, monkeypatch):
    """공통 키 미설정이면 헤더에 임의 키를 넣어도 예약을 만들지 못한다."""
    monkeypatch.setattr(synthetic, "get_settings", lambda: SimpleNamespace(synthetic_api_key=None))
    response = api.post(
        "/reservations",
        json=booking(sample["venue_id"]),
        headers={"X-Synthetic": "1", "X-Synthetic-Key": "unconfigured-key"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert count_venue_reservations(connection, sample["venue_id"]) == 0
    assert api.app.state.booking_events == []


def test_create_reservation_writes_three_tables_and_returns_mock_payment(connection, sample, api):
    before_ok = reservation_counter.labels(result="ok")._value.get()
    response = api.post(
        "/reservations",
        json=booking(sample["venue_id"]),
        headers={"X-Session-Id": "cb98d91e-b62c-46e7-bbd4-ec158672e4ec"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "reservation_id": body["reservation_id"],
        "status": "confirmed",
        "venue_id": sample["venue_id"],
        "date": (TODAY + timedelta(days=1)).isoformat(),
        "start_hour": 13,
        "end_hour": 15,
        "headcount": 2,
        "total_price": 22000,
        "payment": {
            "method": "card",
            "status": "paid",
            "paid_at": "2026-11-05T12:00:00+09:00",
        },
    }
    reservation_id = body["reservation_id"]
    assert connection.execute(
        text("SELECT status,total_price,is_synthetic FROM reservations WHERE reservation_id=:id"),
        {"id": reservation_id},
    ).one() == ("confirmed", 22000, 0)
    assert connection.execute(
        text("SELECT method,status FROM payments WHERE reservation_id=:id"), {"id": reservation_id}
    ).one() == ("card", "paid")
    assert list(
        connection.scalars(
            text(
                "SELECT slot_hour FROM reservation_slots WHERE reservation_id=:id ORDER BY slot_hour"
            ),
            {"id": reservation_id},
        )
    ) == [13, 14]
    assert reservation_counter.labels(result="ok")._value.get() == before_ok + 1
    assert [event[0] for event in api.app.state.booking_events] == ["reserve_ok"]


def test_synthetic_booking_requires_its_own_key_and_sets_the_database_flag(
    connection, sample, api, monkeypatch
):
    monkeypatch.setattr(
        synthetic,
        "get_settings",
        lambda: SimpleNamespace(synthetic_api_key=SecretStr("reservation-test-key")),
    )
    body = booking(sample["venue_id"])
    missing_key = api.post("/reservations", json=body, headers={"X-Synthetic": "1"})
    assert missing_key.status_code == 401
    assert missing_key.json()["code"] == "UNAUTHORIZED"

    wrong_key = api.post(
        "/reservations",
        json=body,
        headers={"X-Synthetic": "1", "X-Synthetic-Key": "wrong-key"},
    )
    assert wrong_key.status_code == 401
    assert wrong_key.json()["code"] == "UNAUTHORIZED"

    response = api.post(
        "/reservations",
        json=body,
        headers={"X-Synthetic": "1", "X-Synthetic-Key": "reservation-test-key"},
    )

    assert response.status_code == 201
    is_synthetic = connection.scalar(
        text("SELECT is_synthetic FROM reservations WHERE reservation_id=:id"),
        {"id": response.json()["reservation_id"]},
    )
    assert is_synthetic == 1
    assert api.app.state.booking_events[-1][1]["is_synthetic"] is True


@pytest.mark.parametrize("day_offset", [-1, 1])
def test_retry_within_ten_minutes_returns_original_booking_without_extra_rows(
    connection, sample, api, day_offset
):
    before_ok = reservation_counter.labels(result="ok")._value.get()
    body = booking(sample["venue_id"], day=TODAY + timedelta(days=day_offset))
    first = api.post("/reservations", json=body)
    second = api.post(
        "/reservations",
        json={**body, "headcount": 5, "method": "phone"},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    reservation_id = first.json()["reservation_id"]
    assert count_venue_reservations(connection, sample["venue_id"]) == 1
    assert count_reservation_payments(connection, reservation_id) == 1
    assert count_reservation_slots(connection, reservation_id) == 2
    assert reservation_counter.labels(result="ok")._value.get() == before_ok + 1
    assert [event[0] for event in api.app.state.booking_events] == ["reserve_ok"]


def test_retry_after_cancellation_and_rebooking_returns_the_new_paid_reservation(
    connection, sample, api
):
    body = booking(sample["venue_id"])
    first = api.post("/reservations", json=body)
    assert first.status_code == 201
    cancelled_id = first.json()["reservation_id"]
    cancelled = api.post(f"/reservations/{cancelled_id}/cancel")
    assert cancelled.status_code == 200

    rebooked = api.post("/reservations", json={**body, "method": "phone"})
    assert rebooked.status_code == 201
    new_id = rebooked.json()["reservation_id"]
    assert new_id != cancelled_id
    before_ok = reservation_counter.labels(result="ok")._value.get()
    retried = api.post("/reservations", json=body)

    assert retried.status_code == 200
    assert retried.json() == rebooked.json()
    assert retried.json()["payment"]["status"] == "paid"
    assert count_venue_reservations(connection, sample["venue_id"]) == 2
    assert count_reservation_slots(connection, cancelled_id) == 0
    assert count_reservation_slots(connection, new_id) == 2
    assert count_reservation_payments(connection, cancelled_id) == 1
    assert count_reservation_payments(connection, new_id) == 1
    assert reservation_counter.labels(result="ok")._value.get() == before_ok
    assert [event[0] for event in api.app.state.booking_events] == [
        "reserve_ok",
        "reserve_cancel_ok",
        "reserve_ok",
    ]


def test_retry_after_cancellation_reports_conflict_when_another_user_books_the_slots(
    connection, sample, api
):
    body = booking(sample["venue_id"])
    first = api.post("/reservations", json=body)
    assert first.status_code == 201
    cancelled = api.post(f"/reservations/{first.json()['reservation_id']}/cancel")
    assert cancelled.status_code == 200
    other = api.post(
        "/reservations",
        json=body,
        headers={"X-Test-User-Id": str(sample["create_user"]())},
    )
    assert other.status_code == 201

    retried = api.post("/reservations", json=body)

    assert retried.status_code == 409
    assert retried.json()["code"] == "SLOT_TAKEN"
    assert retried.json()["detail"] == {"slots": [13, 14]}
    assert count_venue_reservations(connection, sample["venue_id"]) == 2
    assert [event[0] for event in api.app.state.booking_events] == [
        "reserve_ok",
        "reserve_cancel_ok",
        "reserve_ok",
        "reserve_conflict",
    ]


@pytest.mark.parametrize("day_offset", [-1, 1])
def test_retry_excludes_refunded_payment_for_an_active_reservation(
    connection, sample, api, day_offset
):
    """예약 상태 조건과 별개로 결제 paid 조건도 재시도 성공에 필요하다."""
    body = booking(sample["venue_id"], day=TODAY + timedelta(days=day_offset))
    first = api.post("/reservations", json=body)
    assert first.status_code == 201
    reservation_id = first.json()["reservation_id"]
    connection.execute(
        text("UPDATE payments SET status='refunded', refunded_at=:now WHERE reservation_id=:id"),
        {"id": reservation_id, "now": NOW},
    )

    retried = api.post("/reservations", json=body)

    assert retried.status_code == 409
    assert retried.json()["code"] == "SLOT_TAKEN"
    assert retried.json()["detail"] == {
        "slots": [13, 14],
        "mine": True,
        "reservation_id": reservation_id,
    }
    assert count_venue_reservations(connection, sample["venue_id"]) == 1


def test_retry_older_than_ten_minutes_is_conflict_with_own_reservation(connection, sample, api):
    body = booking(sample["venue_id"])
    first = api.post("/reservations", json=body)
    reservation_id = first.json()["reservation_id"]
    connection.execute(
        text("UPDATE reservations SET created_at=:created_at WHERE reservation_id=:id"),
        {"created_at": NOW - timedelta(minutes=10, seconds=1), "id": reservation_id},
    )

    response = api.post("/reservations", json=body)

    assert first.status_code == 201
    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_TAKEN"
    assert response.json()["detail"] == {
        "slots": [13, 14],
        "mine": True,
        "reservation_id": reservation_id,
    }


def test_multiple_own_reservations_return_the_smallest_id(connection, sample, api):
    first = api.post("/reservations", json=booking(sample["venue_id"], start=13, hours=1))
    second = api.post("/reservations", json=booking(sample["venue_id"], start=14, hours=1))
    conflict = api.post("/reservations", json=booking(sample["venue_id"], start=13, hours=2))

    first_id = first.json()["reservation_id"]
    second_id = second.json()["reservation_id"]
    assert first.status_code == second.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {
        "slots": [13, 14],
        "mine": True,
        "reservation_id": min(first_id, second_id),
    }
    assert [event[0] for event in api.app.state.booking_events] == ["reserve_ok", "reserve_ok"]


def test_mixed_owner_conflict_does_not_reveal_another_reservation_id(connection, sample, api):
    own = api.post("/reservations", json=booking(sample["venue_id"], start=13, hours=1))
    other_user = sample["create_user"]()
    other = api.post(
        "/reservations",
        json=booking(sample["venue_id"], start=14, hours=1),
        headers={"X-Test-User-Id": str(other_user)},
    )

    conflict = api.post("/reservations", json=booking(sample["venue_id"], start=13, hours=2))

    assert own.status_code == other.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {"slots": [13, 14]}
    assert [event[0] for event in api.app.state.booking_events] == [
        "reserve_ok",
        "reserve_ok",
        "reserve_conflict",
    ]


@pytest.mark.parametrize(
    ("changes", "code", "reason"),
    [
        ({"date": (TODAY - timedelta(days=366)).isoformat()}, "OUT_OF_RANGE", "date"),
        ({"start_hour": 8}, "OUT_OF_RANGE", "hours"),
        ({"hours": 0}, "OUT_OF_RANGE", "min_hours"),
        ({"hours": 5}, "OUT_OF_RANGE", "max_hours"),
        ({"headcount": 7}, "TOO_MANY_PEOPLE", None),
        ({"method": "cash"}, "INVALID_METHOD", None),
    ],
)
def test_booking_validation_returns_documented_error(
    connection, sample, api, changes, code, reason
):
    response = api.post("/reservations", json={**booking(sample["venue_id"]), **changes})
    body = response.json()
    assert response.status_code == 400
    assert body["code"] == code
    if reason:
        assert body["detail"]["reason"] == reason
    assert count_venue_reservations(connection, sample["venue_id"]) == 0


def test_past_time_is_created_completed_and_unknown_or_inactive_venue_is_not_found(
    connection, sample, api
):
    past = api.post(
        "/reservations",
        json=booking(sample["venue_id"], day=TODAY - timedelta(days=1), start=9, hours=1),
    )
    unknown = api.post("/reservations", json=booking(sample["venue_id"] + 999999))
    connection.execute(
        text("UPDATE venues SET is_active=FALSE WHERE venue_id=:venue"),
        {"venue": sample["venue_id"]},
    )
    inactive = api.post("/reservations", json=booking(sample["venue_id"]))

    assert past.status_code == 201 and past.json()["status"] == "completed"
    assert unknown.status_code == 404 and unknown.json()["code"] == "VENUE_NOT_FOUND"
    assert inactive.status_code == 404 and inactive.json()["code"] == "VENUE_NOT_FOUND"


def test_payment_insert_failure_rolls_back_reservation_and_slots(
    connection, sample, api, monkeypatch
):
    payments_before = connection.scalar(text("SELECT COUNT(*) FROM payments"))

    def fail_payment(*args, **kwargs):
        raise AppError("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.", 500)

    monkeypatch.setattr(reservation_service.payment_repo, "create", fail_payment)
    response = api.post("/reservations", json=booking(sample["venue_id"]))

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert count_venue_reservations(connection, sample["venue_id"]) == 0
    assert (
        connection.scalar(
            text("SELECT COUNT(*) FROM reservation_slots WHERE venue_id=:venue"),
            {"venue": sample["venue_id"]},
        )
        == 0
    )
    assert connection.scalar(text("SELECT COUNT(*) FROM payments")) == payments_before


def test_cancel_refunds_and_releases_only_owned_reservation_slots(connection, sample, api):
    first = api.post("/reservations", json=booking(sample["venue_id"]))
    second = api.post(
        "/reservations",
        json=booking(sample["venue_id"], start=16, hours=1, method="phone"),
    )
    assert first.status_code == second.status_code == 201
    first_id = first.json()["reservation_id"]
    second_id = second.json()["reservation_id"]
    before_cancel = reservation_counter.labels(result="cancel")._value.get()

    response = api.post(f"/reservations/{first_id}/cancel")

    assert response.status_code == 200
    assert response.json() == {
        "reservation_id": first_id,
        "status": "cancelled",
        "total_price": 22000,
        "payment": {
            "method": "card",
            "status": "refunded",
            "paid_at": "2026-11-05T12:00:00+09:00",
            "refunded_at": "2026-11-05T12:00:00+09:00",
        },
        "can_cancel": False,
    }
    assert (
        connection.scalar(
            text("SELECT status FROM reservations WHERE reservation_id=:id"), {"id": first_id}
        )
        == "cancelled"
    )
    assert (
        connection.scalar(
            text("SELECT status FROM payments WHERE reservation_id=:id"), {"id": first_id}
        )
        == "refunded"
    )
    assert count_reservation_slots(connection, first_id) == 0
    assert count_reservation_slots(connection, second_id) == 1
    assert reservation_counter.labels(result="cancel")._value.get() == before_cancel + 1
    assert [event[0] for event in api.app.state.booking_events] == [
        "reserve_ok",
        "reserve_ok",
        "reserve_cancel_ok",
    ]

    rebooked = api.post("/reservations", json=booking(sample["venue_id"], method="phone"))
    assert rebooked.status_code == 201
    assert rebooked.json()["reservation_id"] != first_id
    assert count_reservation_slots(connection, rebooked.json()["reservation_id"]) == 2


def test_cancel_reports_hidden_ownership_and_documented_state_errors(connection, sample, api):
    future = api.post("/reservations", json=booking(sample["venue_id"]))
    at_start = api.post(
        "/reservations", json=booking(sample["venue_id"], day=TODAY, start=12, hours=1)
    )
    completed = api.post(
        "/reservations", json=booking(sample["venue_id"], day=TODAY - timedelta(days=1))
    )
    assert future.status_code == at_start.status_code == completed.status_code == 201

    unknown = api.post("/reservations/9223372036854775000/cancel")
    other = api.post(
        f"/reservations/{future.json()['reservation_id']}/cancel",
        headers={"X-Test-User-Id": str(sample["create_user"]())},
    )
    at_start_response = api.post(f"/reservations/{at_start.json()['reservation_id']}/cancel")
    completed_response = api.post(f"/reservations/{completed.json()['reservation_id']}/cancel")
    first_cancel = api.post(f"/reservations/{future.json()['reservation_id']}/cancel")
    repeated = api.post(f"/reservations/{future.json()['reservation_id']}/cancel")

    assert (unknown.status_code, unknown.json()["code"]) == (404, "RESERVATION_NOT_FOUND")
    assert (other.status_code, other.json()["code"]) == (404, "RESERVATION_NOT_FOUND")
    assert (at_start_response.status_code, at_start_response.json()["code"]) == (
        409,
        "NOT_CANCELLABLE",
    )
    assert (completed_response.status_code, completed_response.json()["code"]) == (
        409,
        "NOT_CANCELLABLE",
    )
    assert first_cancel.status_code == 200
    assert (repeated.status_code, repeated.json()["code"]) == (409, "ALREADY_CANCELLED")


def test_cancel_refund_failure_rolls_back_status_and_released_slots(
    connection, sample, api, monkeypatch
):
    created = api.post("/reservations", json=booking(sample["venue_id"]))
    assert created.status_code == 201
    reservation_id = created.json()["reservation_id"]
    before_cancel = reservation_counter.labels(result="cancel")._value.get()
    events_before = len(api.app.state.booking_events)

    def fail_refund(*args, **kwargs):
        raise RuntimeError("simulated payment repository failure")

    monkeypatch.setattr(reservation_service.payment_repo, "refund", fail_refund)
    response = api.post(f"/reservations/{reservation_id}/cancel")

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert (
        connection.scalar(
            text("SELECT status FROM reservations WHERE reservation_id=:id"),
            {"id": reservation_id},
        )
        == "confirmed"
    )
    assert (
        connection.scalar(
            text("SELECT status FROM payments WHERE reservation_id=:id"),
            {"id": reservation_id},
        )
        == "paid"
    )
    assert count_reservation_slots(connection, reservation_id) == 2
    assert reservation_counter.labels(result="cancel")._value.get() == before_cancel
    assert len(api.app.state.booking_events) == events_before


def test_cancel_route_requires_authentication_and_positive_id(connection, sample, api):
    invalid = api.post("/reservations/0/cancel")
    override = api.app.dependency_overrides.pop(get_current_user)
    try:
        unauthenticated = api.post("/reservations/1/cancel")
    finally:
        api.app.dependency_overrides[get_current_user] = override

    assert (invalid.status_code, invalid.json()["code"]) == (400, "VALIDATION")
    assert (unauthenticated.status_code, unauthenticated.json()["code"]) == (
        401,
        "UNAUTHORIZED",
    )
