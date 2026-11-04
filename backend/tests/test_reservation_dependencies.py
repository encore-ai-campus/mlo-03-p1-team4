"""F-50: B 모델·소유권 조회와 A 후기 작성 연결 검증. DB는 CHECK_DB_URL로 지정한다."""

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, text
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, configure_mappers
from sqlalchemy.pool import NullPool

from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user
from app.main import app
from app.models.reservation import Payment, Reservation, ReservationSlot
from app.repositories import reservation_repo
from app.services import review_service

MODELS = (Reservation, ReservationSlot, Payment)
TODAY = date(2026, 11, 4)
NOW = datetime.fromisoformat("2026-11-04T12:00:00")


@pytest.mark.parametrize("model", MODELS)
def test_model_matches_migration(model):
    """실제 마이그레이션에서 컬럼·타입·기본값·키·제약을 추출해 대조한다."""
    migration = (Path(__file__).parents[2] / "db/migrations/0001_init.sql").read_text(
        encoding="utf-8"
    )
    ddl = re.search(
        rf"CREATE TABLE {model.__tablename__} \((.*?)\) ENGINE=InnoDB;", migration, re.S
    )[1]
    ddl = re.sub(r"--[^\n]*", "", ddl)
    table = model.__table__
    columns = re.findall(
        r"^\s+(\w+)\s+(BIGINT|SMALLINT|TINYINT|INT|DATE(?:TIME)?|BOOLEAN|ENUM\([^)]*\))\s+(NOT NULL|NULL)([^\n]*)",
        ddl,
        re.M,
    )
    assert [column[0] for column in columns] == list(table.columns.keys())
    for name, sql_type, nullable, suffix in columns:
        column = table.c[name]
        compiled = str(column.type.compile(dialect=dialect())).replace(" ", "")
        assert compiled == {"BOOLEAN": "BOOL", "INT": "INTEGER"}.get(sql_type, sql_type)
        assert column.nullable == (nullable == "NULL")
        default = re.search(r"DEFAULT ([^,\s]+)", suffix)
        assert (str(column.server_default.arg) if column.server_default else None) == (
            default[1] if default else None
        )
        assert (column.autoincrement is True) == ("AUTO_INCREMENT" in suffix)
    assert list(table.primary_key.columns.keys()) == [
        name.strip() for name in re.search(r"PRIMARY KEY \(([^)]+)\)", ddl)[1].split(",")
    ]
    for keyword, actual in (
        (
            "UNIQUE KEY",
            {
                c.name: list(c.columns.keys())
                for c in table.constraints
                if isinstance(c, UniqueConstraint)
            },
        ),
        ("(?<!UNIQUE )KEY", {i.name: list(i.columns.keys()) for i in table.indexes}),
    ):
        expected = {
            name: [part.strip() for part in parts.split(",")]
            for name, parts in re.findall(rf"{keyword} (\w+) \(([^)]+)\)", ddl)
        }
        assert actual == expected
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    expected_checks = dict(re.findall(r"CONSTRAINT (\w+)\s+CHECK \(([^\n]+)\)", ddl))
    assert {k: "".join(v.split()) for k, v in checks.items()} == {
        k: "".join(v.split()) for k, v in expected_checks.items()
    }
    actual_fks = {
        c.name: (list(c.column_keys), [e.target_fullname for e in c.elements], c.ondelete)
        for c in table.foreign_key_constraints
    }
    expected_fks = {}
    for name, source, target, fields, ondelete in re.findall(
        r"CONSTRAINT (\w+)\s+FOREIGN KEY \(([^)]+)\)\s+REFERENCES (\w+)\s*\(([^)]+)\)(?: ON DELETE (\w+))?",
        ddl,
    ):
        expected_fks[name] = (
            [s.strip() for s in source.split(",")],
            [f"{target}.{s.strip()}" for s in fields.split(",")],
            ondelete or None,
        )
    assert actual_fks == expected_fks
    assert table.dialect_options["mysql"]["engine"] == "InnoDB"


def test_models_configure_without_venue_relationship():
    """누락된 공간 모델 때문에 A의 매퍼 구성이 실패하지 않아야 한다."""
    configure_mappers()


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
        with engine.connect() as conn, conn.begin() as outer:
            assert conn.scalar(text("SELECT DATABASE()")) == "spacecube_test"
            assert "MariaDB" in conn.scalar(text("SELECT VERSION()"))
            conn.execute(text("SET time_zone = '+09:00'"))
            conn.execute(
                text(
                    "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'"
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
    """DDL은 실행하지 않고 기존 seed를 참조한다. 모든 테스트 행은 외부 트랜잭션에서 롤백한다."""
    category_id = connection.scalar(text("SELECT MIN(category_id) FROM categories"))
    region_id = connection.scalar(text("SELECT MIN(region_id) FROM regions"))
    assert category_id is not None and region_id is not None, "기존 seed.sql 적용이 필요합니다."
    user_id = connection.execute(
        text(
            "INSERT INTO users (email,password_hash,name,birth,gender_digit,terms_agreed_at,privacy_agreed_at,is_synthetic) "
            "VALUES (:email,'unused-test-hash','검증회원','000101','3',:now,:now,TRUE)"
        ),
        {"email": f"{uuid4().hex}@example.invalid", "now": NOW},
    ).lastrowid
    venue_id = connection.execute(
        text(
            "INSERT INTO venues (region_id,category_id,name,capacity_max,price_per_hour,source_site) "
            "VALUES (:region,:category,'의존성 검증 공간',4,10000,'synthetic')"
        ),
        {"region": region_id, "category": category_id},
    ).lastrowid

    def create_reservation(status="completed", reserve_date=TODAY, created_at=NOW):
        return connection.execute(
            text(
                "INSERT INTO reservations (user_id,venue_id,reserve_date,start_hour,end_hour,headcount,total_price,status,is_synthetic,created_at) "
                "VALUES (:user,:venue,:day,9,10,1,10000,:status,TRUE,:created)"
            ),
            {
                "user": user_id,
                "venue": venue_id,
                "day": reserve_date,
                "status": status,
                "created": created_at,
            },
        ).lastrowid

    return user_id, venue_id, create_reservation


@pytest.mark.parametrize("status", ["confirmed", "completed", "cancelled"])
def test_owned_reservation(connection, sample, status):
    user, venue, create = sample
    reservation_id = create(status)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        result = reservation_repo.get_owned(db, user, reservation_id)
        assert type(result) is tuple
        assert result == (reservation_id, venue, TODAY, 9, 10, status, NOW)
        assert type(result[2]) is date and type(result[6]) is datetime
        assert reservation_repo.get_owned(db, user + 1, reservation_id) is None
        assert reservation_repo.get_owned(db, user, 0) is None


@pytest.mark.parametrize(
    ("case", "status", "days_ago", "created_days_ago", "expected_status", "code"),
    [
        ("success", "completed", 0, 0, 201, None),
        ("other_owner", "completed", 0, 0, 404, "RESERVATION_NOT_FOUND"),
        ("not_completed", "confirmed", 0, 0, 403, "NOT_COMPLETED"),
        ("expired", "completed", 8, 8, 403, "REVIEW_PERIOD_OVER"),
        ("duplicate", "completed", 0, 0, 409, "REVIEW_EXISTS"),
        ("deadline", "completed", 7, 7, 201, None),
        ("past_booking", "completed", 30, 0, 201, None),
    ],
)
def test_a_review_creation(
    connection, sample, monkeypatch, case, status, days_ago, created_days_ago, expected_status, code
):
    """실제 A 라우터·서비스·리포지토리와 MariaDB를 사용한다. 인증 자체는 A 테스트 범위다."""
    user, _, create = sample
    reservation_id = create(
        status, TODAY - timedelta(days=days_ago), NOW - timedelta(days=created_days_ago)
    )
    monkeypatch.setattr(review_service, "get_today", lambda: TODAY)
    monkeypatch.setattr(review_service, "get_now", lambda: NOW)

    def test_db():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db

    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_write] = test_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user + 1 if case == "other_owner" else user
    )
    try:
        with TestClient(app) as client:
            path = f"/reservations/{reservation_id}/review"
            body = {"rating": 5, "content": "의존성 연결 검증"}
            if case == "duplicate":
                assert client.post(path, json=body).status_code == 201
            response = client.post(path, json=body)
        assert response.status_code == expected_status, response.text
        if code:
            assert response.json()["code"] == code
        else:
            stored = connection.execute(
                text(
                    "SELECT reservation_id,user_id,rating,content FROM reviews WHERE review_id=:id"
                ),
                {"id": response.json()["review_id"]},
            ).one()
            assert tuple(stored) == (reservation_id, user, 5, body["content"])
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
