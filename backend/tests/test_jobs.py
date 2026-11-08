"""F-35: MariaDB 이용 완료 배치의 경계·트랜잭션·동시 실행을 확인한다."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier, Event, local
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.jobs import complete_reservations as completion_job
from app.repositories import reservation_repo
from app.services import reservation_service

TODAY = date(2026, 11, 6)
NOW = datetime.fromisoformat("2026-11-06T15:00:00")
JOB_NOW = datetime.fromisoformat("2026-11-06T16:00:00")
BEFORE_JOB_NOW = datetime.fromisoformat("2026-11-06T14:59:00")


def _database_url():
    raw = os.environ.get("CHECK_DB_URL")
    if not raw:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 접속 정보를 지정하세요.")
    try:
        url = make_url(raw)
    except Exception:
        pytest.fail("CHECK_DB_URL 형식을 확인하세요.", pytrace=False)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("이용 완료 배치는 로컬 MariaDB spacecube_test에서만 테스트합니다.")
    return url


@pytest.fixture
def connection():
    engine = create_engine(_database_url(), poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            assert conn.scalar(text("SELECT DATABASE()")) == "spacecube_test"
            assert "MariaDB" in conn.scalar(text("SELECT VERSION()"))
            conn.execute(text("SET time_zone = '+09:00'"))
            conn.execute(
                text(
                    "SET SESSION sql_mode = "
                    "'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
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
    now = datetime.combine(TODAY, datetime.min.time())
    user_id = connection.execute(
        text(
            "INSERT INTO users "
            "(email,password_hash,name,birth,gender_digit,terms_agreed_at,privacy_agreed_at,is_synthetic) "
            "VALUES (:email,'unused-test-hash','완료 배치 검증 회원','000101','3',:now,:now,TRUE)"
        ),
        {"email": f"{uuid4().hex}@example.invalid", "now": now},
    ).lastrowid
    venue_id = connection.execute(
        text(
            "INSERT INTO venues "
            "(region_id,category_id,name,capacity_max,price_per_hour,min_hours,open_hour,close_hour,source_site,source_id) "
            "VALUES (:region,:category,'완료 배치 검증 공간',6,11000,1,9,23,'synthetic',:source_id)"
        ),
        {"region": region_id, "category": category_id, "source_id": uuid4().hex},
    ).lastrowid

    specs = {
        "yesterday": (TODAY - timedelta(days=1), 10, 11, "confirmed", True),
        "ends_14": (TODAY, 13, 14, "confirmed", False),
        "ends_15": (TODAY, 14, 15, "confirmed", False),
        "ends_16": (TODAY, 15, 16, "confirmed", False),
        "tomorrow": (TODAY + timedelta(days=1), 14, 15, "confirmed", False),
        "cancelled": (TODAY - timedelta(days=1), 11, 12, "cancelled", False),
        "already_completed": (TODAY - timedelta(days=2), 12, 13, "completed", False),
    }
    reservation_ids = {}
    for name, (reserve_date, start_hour, end_hour, status, is_synthetic) in specs.items():
        reservation_id = connection.execute(
            text(
                "INSERT INTO reservations "
                "(user_id,venue_id,reserve_date,start_hour,end_hour,headcount,total_price,status,is_synthetic,created_at) "
                "VALUES (:user,:venue,:day,:start,:end,2,22000,:status,:synthetic,:created)"
            ),
            {
                "user": user_id,
                "venue": venue_id,
                "day": reserve_date,
                "start": start_hour,
                "end": end_hour,
                "status": status,
                "synthetic": is_synthetic,
                "created": now,
            },
        ).lastrowid
        reservation_ids[name] = reservation_id
        connection.execute(
            text(
                "INSERT INTO payments "
                "(reservation_id,method,status,paid_at,refunded_at) "
                "VALUES (:id,'card',:payment_status,:paid_at,:refunded_at)"
            ),
            {
                "id": reservation_id,
                "payment_status": "refunded" if status == "cancelled" else "paid",
                "paid_at": now,
                "refunded_at": now if status == "cancelled" else None,
            },
        )
        if status != "cancelled":
            connection.execute(
                text(
                    "INSERT INTO reservation_slots (venue_id,slot_date,slot_hour,reservation_id) "
                    "VALUES (:venue,:day,:hour,:id)"
                ),
                {"venue": venue_id, "day": reserve_date, "hour": start_hour, "id": reservation_id},
            )

    return {"venue_id": venue_id, "user_id": user_id, "reservations": reservation_ids}


def _status(connection, reservation_id):
    return connection.scalar(
        text("SELECT status FROM reservations WHERE reservation_id=:id"), {"id": reservation_id}
    )


def _run_in_savepoint(connection):
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        return reservation_service.complete_ended_reservations(db)


def test_completion_cutoff_is_inclusive_at_hour_and_keeps_slots_and_payments(
    connection, sample, monkeypatch
):
    """종료 정각부터 완료하고 칸·결제·다른 상태는 건드리지 않는다."""
    clock_reads = []
    current = BEFORE_JOB_NOW
    monkeypatch.setattr(
        reservation_service, "get_now", lambda: clock_reads.append(current) or current
    )
    rows = sample["reservations"]

    assert _run_in_savepoint(connection) == 2
    assert _status(connection, rows["yesterday"]) == "completed"
    assert _status(connection, rows["ends_14"]) == "completed"
    assert _status(connection, rows["ends_15"]) == "confirmed"
    assert _status(connection, rows["ends_16"]) == "confirmed"
    assert _status(connection, rows["tomorrow"]) == "confirmed"
    assert _status(connection, rows["cancelled"]) == "cancelled"
    assert _status(connection, rows["already_completed"]) == "completed"

    current = NOW
    assert _run_in_savepoint(connection) == 1
    assert _status(connection, rows["ends_15"]) == "completed"
    assert _run_in_savepoint(connection) == 0
    assert clock_reads == [BEFORE_JOB_NOW, NOW, NOW]

    changed_ids = [rows["yesterday"], rows["ends_14"], rows["ends_15"]]
    for reservation_id in changed_ids:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT status FROM payments WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == "paid"
        )


def test_completion_rolls_back_if_commit_fails(connection, sample, monkeypatch):
    """COMMIT 실패는 UPDATE도 롤백하고 예외를 호출자에게 돌려준다."""
    monkeypatch.setattr(reservation_service, "get_now", lambda: NOW)
    reservation_id = sample["reservations"]["ends_15"]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:

        def fail_commit():
            raise RuntimeError("commit failure")

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="commit failure"):
            reservation_service.complete_ended_reservations(db)

    assert _status(connection, reservation_id) == "confirmed"


def test_job_main_logs_committed_count_and_closes_database(monkeypatch):
    calls = []

    class SessionContext:
        def __enter__(self):
            calls.append("session-enter")
            return object()

        def __exit__(self, *_):
            calls.append("session-exit")

    monkeypatch.setattr(completion_job, "setup_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(completion_job, "new_write_session", lambda: SessionContext())
    monkeypatch.setattr(completion_job, "complete_ended_reservations", lambda db: 7)
    monkeypatch.setattr(completion_job, "close_databases", lambda: calls.append("close"))
    monkeypatch.setattr(
        completion_job.logger,
        "info",
        lambda message, *, extra: calls.append((message, extra)),
    )

    assert completion_job.main() == 0
    assert calls == [
        "logging",
        "session-enter",
        "session-exit",
        ("이용 완료 배치 완료", {"count": 7, "completed": 7}),
        "close",
    ]


def test_job_main_returns_failure_without_logging_exception_message(monkeypatch):
    calls = []

    class SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_):
            return None

    def fail(_db):
        raise RuntimeError("secret connection string")

    monkeypatch.setattr(completion_job, "setup_logging", lambda: None)
    monkeypatch.setattr(completion_job, "new_write_session", lambda: SessionContext())
    monkeypatch.setattr(completion_job, "complete_ended_reservations", fail)
    monkeypatch.setattr(completion_job, "close_databases", lambda: calls.append("close"))
    monkeypatch.setattr(
        completion_job.logger,
        "error",
        lambda message, *, extra: calls.append((message, extra)),
    )

    assert completion_job.main() == 1
    assert calls == [
        ("이용 완료 배치 실패", {"error_type": "RuntimeError"}),
        "close",
    ]


@pytest.fixture
def committed_scenario():
    """실제 별도 세션 동시성 테스트용 커밋 행을 만들고 기존 상태까지 복구한다."""
    engine = create_engine(_database_url(), poolclass=NullPool, hide_parameters=True)
    user_id = venue_id = None
    reservation_ids = []
    baseline_ids = []
    try:
        with engine.begin() as conn:
            conn.execute(text("SET time_zone = '+09:00'"))
            baseline_ids = list(
                conn.scalars(
                    text(
                        "SELECT reservation_id FROM reservations WHERE status='confirmed' "
                        "AND (reserve_date < :today OR (reserve_date=:today AND end_hour <= :hour))"
                    ),
                    {"today": TODAY, "hour": JOB_NOW.hour},
                )
            )
            category_id = conn.scalar(text("SELECT MIN(category_id) FROM categories"))
            region_id = conn.scalar(text("SELECT MIN(region_id) FROM regions"))
            assert category_id is not None and region_id is not None, (
                "기존 seed.sql 적용이 필요합니다."
            )
            user_id = conn.execute(
                text(
                    "INSERT INTO users "
                    "(email,password_hash,name,birth,gender_digit,terms_agreed_at,privacy_agreed_at,is_synthetic) "
                    "VALUES (:email,'unused-test-hash','배치 동시성 검증 회원','000101','3',:now,:now,TRUE)"
                ),
                {"email": f"{uuid4().hex}@example.invalid", "now": NOW},
            ).lastrowid
            venue_id = conn.execute(
                text(
                    "INSERT INTO venues "
                    "(region_id,category_id,name,capacity_max,price_per_hour,min_hours,open_hour,close_hour,source_site,source_id) "
                    "VALUES (:region,:category,'배치 동시성 검증 공간',6,11000,1,9,23,'synthetic',:source_id)"
                ),
                {"region": region_id, "category": category_id, "source_id": uuid4().hex},
            ).lastrowid

            for reserve_date, start_hour, end_hour in (
                (TODAY - timedelta(days=1), 10, 11),
                (TODAY, 14, 15),
                (TODAY, 15, 16),
            ):
                reservation_id = conn.execute(
                    text(
                        "INSERT INTO reservations "
                        "(user_id,venue_id,reserve_date,start_hour,end_hour,headcount,total_price,status,is_synthetic,created_at) "
                        "VALUES (:user,:venue,:day,:start,:end,2,11000,'confirmed',TRUE,:created)"
                    ),
                    {
                        "user": user_id,
                        "venue": venue_id,
                        "day": reserve_date,
                        "start": start_hour,
                        "end": end_hour,
                        "created": NOW,
                    },
                ).lastrowid
                reservation_ids.append(reservation_id)
                if start_hour == 15:
                    conn.execute(
                        text(
                            "INSERT INTO reservation_slots (venue_id,slot_date,slot_hour,reservation_id) "
                            "VALUES (:venue,:day,:hour,:id)"
                        ),
                        {
                            "venue": venue_id,
                            "day": reserve_date,
                            "hour": start_hour,
                            "id": reservation_id,
                        },
                    )
                    conn.execute(
                        text(
                            "INSERT INTO payments (reservation_id,method,status,paid_at) "
                            "VALUES (:id,'card','paid',:paid_at)"
                        ),
                        {"id": reservation_id, "paid_at": NOW},
                    )

        yield {
            "engine": engine,
            "user_id": user_id,
            "venue_id": venue_id,
            "reservation_ids": reservation_ids,
            "race_reservation_id": reservation_ids[-1],
            "baseline_ids": baseline_ids,
            "expected_count": len(baseline_ids) + len(reservation_ids),
        }
    finally:
        try:
            with engine.begin() as conn:
                for baseline_id in baseline_ids:
                    conn.execute(
                        text("UPDATE reservations SET status='confirmed' WHERE reservation_id=:id"),
                        {"id": baseline_id},
                    )
                for test_id in reservation_ids:
                    conn.execute(
                        text("DELETE FROM payments WHERE reservation_id=:id"), {"id": test_id}
                    )
                    conn.execute(
                        text("DELETE FROM reservation_slots WHERE reservation_id=:id"),
                        {"id": test_id},
                    )
                    conn.execute(
                        text("DELETE FROM reservations WHERE reservation_id=:id"), {"id": test_id}
                    )
                if venue_id is not None:
                    conn.execute(text("DELETE FROM venues WHERE venue_id=:id"), {"id": venue_id})
                if user_id is not None:
                    conn.execute(text("DELETE FROM users WHERE user_id=:id"), {"id": user_id})
        finally:
            engine.dispose()


def test_two_independent_job_sessions_complete_each_due_reservation_once(
    committed_scenario, monkeypatch
):
    scenario = committed_scenario
    monkeypatch.setattr(reservation_service, "get_now", lambda: JOB_NOW)
    barrier = Barrier(2)

    def run_job():
        with Session(scenario["engine"]) as db:
            barrier.wait(timeout=20)
            return reservation_service.complete_ended_reservations(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_job(), range(2)))

    assert sum(results) == scenario["expected_count"]
    assert sorted(results) == [0, scenario["expected_count"]]
    with scenario["engine"].connect() as conn:
        for reservation_id in scenario["reservation_ids"]:
            assert (
                conn.scalar(
                    text("SELECT status FROM reservations WHERE reservation_id=:id"),
                    {"id": reservation_id},
                )
                == "completed"
            )


def test_cancel_winning_race_is_not_resurrected_by_completion_update(
    committed_scenario, monkeypatch
):
    scenario = committed_scenario
    reservation_id = scenario["race_reservation_id"]
    cancellation_locked = Event()
    allow_cancellation = Event()
    completion_update_started = Event()
    clock_context = local()
    original_lock = reservation_repo.get_owned_for_update
    original_complete = reservation_repo.complete_ended

    def fixed_now():
        if getattr(clock_context, "role", None) == "cancel":
            return BEFORE_JOB_NOW
        return JOB_NOW

    def hold_cancellation_lock(db, *, user_id, reservation_id):
        reservation = original_lock(db, user_id=user_id, reservation_id=reservation_id)
        if reservation_id == scenario["race_reservation_id"]:
            cancellation_locked.set()
            if not allow_cancellation.wait(timeout=20):
                raise TimeoutError("cancellation coordination timed out")
        return reservation

    def signal_completion_update(db, *, today, now_hour):
        completion_update_started.set()
        return original_complete(db, today=today, now_hour=now_hour)

    monkeypatch.setattr(reservation_service, "get_now", fixed_now)
    monkeypatch.setattr(reservation_service, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(reservation_repo, "get_owned_for_update", hold_cancellation_lock)
    monkeypatch.setattr(reservation_repo, "complete_ended", signal_completion_update)

    def cancel():
        clock_context.role = "cancel"
        with Session(scenario["engine"]) as db:
            return reservation_service.cancel_reservation(
                db,
                user_id=scenario["user_id"],
                reservation_id=reservation_id,
                session_id=None,
            )

    def complete():
        clock_context.role = "complete"
        with Session(scenario["engine"]) as db:
            return reservation_service.complete_ended_reservations(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel_future = pool.submit(cancel)
        try:
            assert cancellation_locked.wait(timeout=20)
            completion_future = pool.submit(complete)
            assert completion_update_started.wait(timeout=20)
            assert not completion_future.done()
        finally:
            allow_cancellation.set()
        cancelled = cancel_future.result(timeout=30)
        completed_count = completion_future.result(timeout=30)

    assert cancelled.status == "cancelled"
    assert completed_count == scenario["expected_count"] - 1
    with scenario["engine"].connect() as conn:
        assert (
            conn.scalar(
                text("SELECT status FROM reservations WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == "cancelled"
        )
        assert (
            conn.scalar(
                text("SELECT status FROM payments WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == "refunded"
        )
        assert (
            conn.scalar(
                text("SELECT COUNT(*) FROM reservation_slots WHERE reservation_id=:id"),
                {"id": reservation_id},
            )
            == 0
        )
