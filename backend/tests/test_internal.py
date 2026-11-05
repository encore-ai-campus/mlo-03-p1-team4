"""F-61: 실제 MariaDB에서 내부 공간 등록의 계약·원자성·출처 경쟁을 검증한다."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core import deps
from app.core.db import get_db_read, get_db_write
from app.main import create_app
from app.services import internal_service

KEY = "internal-venue-test-key"
HEADERS = {"X-Internal-Key": KEY}


def _database_url():
    """설정이 없는 경우에도 SQLite 등으로 대체하지 않는다."""
    raw = os.environ.get("CHECK_DB_URL")
    if not raw:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 접속 정보를 지정하세요.")
    url = make_url(raw)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("로컬 MariaDB spacecube_test에서만 실행합니다.")
    return url


def assert_test_database(connection):
    assert connection.scalar(text("SELECT DATABASE()")) == "spacecube_test"
    assert "MariaDB" in connection.scalar(text("SELECT VERSION()"))
    connection.execute(text("SET time_zone = '+09:00'"))
    connection.execute(text("SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'"))


@pytest.fixture
def internal_connection():
    engine = create_engine(_database_url(), poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            assert_test_database(connection)
            try:
                yield connection
            finally:
                outer.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def internal_app(monkeypatch):
    monkeypatch.setattr(
        deps, "get_settings", lambda: SimpleNamespace(internal_api_key=SecretStr(KEY))
    )
    return create_app()


@pytest.fixture
def internal_api(internal_connection, internal_app):
    def write_db():
        with Session(bind=internal_connection, join_transaction_mode="create_savepoint") as db:
            yield db

    def reject_read_replica():
        raise AssertionError("내부 쓰기에 replica를 사용하면 안 됩니다.")

    internal_app.dependency_overrides[get_db_write] = write_db
    internal_app.dependency_overrides[get_db_read] = reject_read_replica
    with TestClient(internal_app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def venue_payload(internal_connection):
    region = internal_connection.execute(
        text("SELECT sido,sigungu FROM regions ORDER BY region_id LIMIT 1")
    ).one()
    category = internal_connection.scalar(
        text("SELECT code FROM categories ORDER BY category_id LIMIT 1")
    )
    facilities = list(
        internal_connection.scalars(
            text("SELECT name FROM facilities ORDER BY facility_id LIMIT 2")
        )
    )
    assert category and len(facilities) == 2, "기존 0001·seed 적용이 필요합니다."
    return {
        "source_site": "synthetic",
        "source_id": uuid4().hex,
        "name": "종로구 시연 공간",
        "category_code": category,
        "sido": region.sido,
        "sigungu": region.sigungu,
        "capacity_max": 6,
        "price_per_hour": 12000,
        "min_hours": 2,
        "open_hour": 9,
        "close_hour": 23,
        "description": "유형별 생성 설명",
        "notice": "생성 이용 안내",
        "facilities": facilities,
        "images": ["art:group-0", "art:seminar-1"],
    }


def source_count(connection, body):
    return connection.scalar(
        text("SELECT COUNT(*) FROM venues WHERE source_site=:site AND source_id=:source"),
        {"site": body["source_site"], "source": body["source_id"]},
    )


def stored_collections(connection, venue_id):
    facilities = list(
        connection.scalars(
            text(
                "SELECT f.name FROM venue_facilities vf JOIN facilities f USING(facility_id) "
                "WHERE vf.venue_id=:id ORDER BY f.facility_id"
            ),
            {"id": venue_id},
        )
    )
    images = list(
        connection.scalars(
            text("SELECT url FROM venue_images WHERE venue_id=:id ORDER BY sort_order,image_id"),
            {"id": venue_id},
        )
    )
    return facilities, images


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Internal-Key": "wrong"}, {"X-Synthetic-Key": KEY}, {"Authorization": "Bearer fake"}],
)
def test_missing_or_wrong_key_is_rejected_before_database_access(internal_app, headers):
    def unavailable_db():
        raise AssertionError("키 검증 실패 때는 DB에 접근하면 안 됩니다.")

    internal_app.dependency_overrides[get_db_write] = unavailable_db
    with TestClient(internal_app, raise_server_exceptions=False) as api:
        response = api.post("/internal/venues", headers=headers, json={})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_unconfigured_internal_key_is_rejected(internal_app, monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: SimpleNamespace(internal_api_key=None))
    with TestClient(internal_app) as api:
        response = api.post("/internal/venues", headers=HEADERS, json={})
    assert response.status_code == 401


@pytest.mark.parametrize("site", ["spacecloud", "shareit", "synthetic"])
def test_create_and_identical_retry_return_201_then_200(
    internal_connection, internal_api, venue_payload, site
):
    body = {**venue_payload, "source_site": site}
    first = internal_api.post("/internal/venues", headers=HEADERS, json=body)
    assert first.status_code == 201, first.text
    assert set(first.json()) == {"venue_id", "ignored_facilities"}
    assert first.json()["ignored_facilities"] == []
    second = internal_api.post("/internal/venues", headers=HEADERS, json=body)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    assert source_count(internal_connection, body) == 1
    assert stored_collections(internal_connection, first.json()["venue_id"]) == (
        body["facilities"],
        body["images"],
    )
    operation = internal_api.get("/openapi.json").json()["paths"]["/internal/venues"]["post"]
    assert {"200", "201", "400", "401"} <= operation["responses"].keys()
    assert any(p["name"] == "X-Internal-Key" and p["required"] for p in operation["parameters"])


def test_update_replaces_collections_preserves_created_at_and_separates_sources(
    internal_connection, internal_api, venue_payload
):
    first = internal_api.post("/internal/venues", headers=HEADERS, json=venue_payload)
    assert first.status_code == 201
    venue_id = first.json()["venue_id"]
    original_time = datetime.fromisoformat("2026-10-01T09:00:00")
    internal_connection.execute(
        text("UPDATE venues SET created_at=:ts WHERE venue_id=:id"),
        {"id": venue_id, "ts": original_time},
    )
    changed = {
        **venue_payload,
        "name": "종로구 변경 공간",
        "price_per_hour": 18000,
        "facilities": [venue_payload["facilities"][1], "없는 시설", "없는 시설"],
        "images": ["art:cafe-1"],
        "description": None,
    }
    updated = internal_api.post("/internal/venues", headers=HEADERS, json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"venue_id": venue_id, "ignored_facilities": ["없는 시설"]}
    row = internal_connection.execute(
        text("SELECT name,price_per_hour,created_at,description FROM venues WHERE venue_id=:id"),
        {"id": venue_id},
    ).one()
    assert tuple(row) == (changed["name"], 18000, original_time, None)
    assert stored_collections(internal_connection, venue_id) == (
        [venue_payload["facilities"][1]],
        ["art:cafe-1"],
    )
    other = internal_api.post(
        "/internal/venues", headers=HEADERS, json={**venue_payload, "source_site": "shareit"}
    )
    assert other.status_code == 201
    assert other.json()["venue_id"] != venue_id


def test_omitted_collections_clear_existing_facilities_and_images(
    internal_connection, internal_api, venue_payload
):
    first = internal_api.post("/internal/venues", headers=HEADERS, json=venue_payload)
    assert first.status_code == 201
    minimal = {
        k: v
        for k, v in venue_payload.items()
        if k
        not in {
            "facilities",
            "images",
            "description",
            "notice",
            "min_hours",
            "open_hour",
            "close_hour",
        }
    }
    updated = internal_api.post("/internal/venues", headers=HEADERS, json=minimal)
    assert updated.status_code == 200
    assert stored_collections(internal_connection, first.json()["venue_id"]) == ([], [])
    row = internal_connection.execute(
        text("SELECT min_hours,open_hour,close_hour FROM venues WHERE venue_id=:id"),
        {"id": first.json()["venue_id"]},
    ).one()
    assert tuple(row) == (1, 9, 23)


def test_known_facilities_are_deduplicated_with_database_collation(
    internal_connection, internal_api, venue_payload
):
    facility = venue_payload["facilities"][0]
    body = {**venue_payload, "facilities": [facility, facility, facility.lower()]}
    created = internal_api.post("/internal/venues", headers=HEADERS, json=body)
    assert created.status_code == 201
    assert created.json()["ignored_facilities"] == []
    assert stored_collections(internal_connection, created.json()["venue_id"])[0] == [facility]


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"sido": "미등록시", "sigungu": "미등록구"}, "UNKNOWN_REGION"),
        ({"category_code": "unknown"}, "UNKNOWN_CATEGORY"),
        ({"source_site": "roovook"}, "VALIDATION"),
        ({"source_site": "sparkplus"}, "VALIDATION"),
        ({"price_per_hour": 0}, "VALIDATION"),
        ({"price_per_hour": 2147483648}, "VALIDATION"),
        ({"capacity_max": 0}, "VALIDATION"),
        ({"capacity_max": 32768}, "VALIDATION"),
        ({"capacity_max": True}, "VALIDATION"),
        ({"min_hours": 0}, "VALIDATION"),
        ({"min_hours": 5}, "VALIDATION"),
        ({"open_hour": 8}, "VALIDATION"),
        ({"close_hour": 24}, "VALIDATION"),
        ({"open_hour": 22, "close_hour": 22}, "VALIDATION"),
        ({"source_id": " "}, "VALIDATION"),
        ({"source_id": "x" * 51}, "VALIDATION"),
        ({"name": "가" * 101}, "VALIDATION"),
        ({"description": "가" * 21846}, "VALIDATION"),
        ({"images": ["https://example.invalid/photo.jpg"]}, "VALIDATION"),
        ({"images": ["art:group-0"] * 129}, "VALIDATION"),
        ({"is_synthetic": True}, "VALIDATION"),
    ],
)
def test_documented_input_errors_do_not_write_venues(
    internal_connection, internal_api, venue_payload, changes, code
):
    body = {**venue_payload, **changes}
    response = internal_api.post("/internal/venues", headers=HEADERS, json=body)
    assert response.status_code == 400, response.text
    assert response.json()["code"] == code
    assert set(response.json()) == {"code", "message", "detail"}
    assert source_count(internal_connection, venue_payload) == 0
    if code == "UNKNOWN_REGION":
        assert response.json()["detail"] == {"sido": body["sido"], "sigungu": body["sigungu"]}
    if code == "UNKNOWN_CATEGORY":
        assert response.json()["detail"] == {"category_code": "unknown"}


@pytest.mark.parametrize("existing", [False, True])
def test_collection_failure_rolls_back_the_whole_registration(
    internal_connection, internal_api, venue_payload, monkeypatch, existing
):
    venue_id = None
    if existing:
        first = internal_api.post("/internal/venues", headers=HEADERS, json=venue_payload)
        assert first.status_code == 201
        venue_id = first.json()["venue_id"]
    original = internal_service.venue_repo.replace_facilities_and_images

    def fail_after_replacement(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("시설·그림 교체 후 실패를 재현")

    monkeypatch.setattr(
        internal_service.venue_repo, "replace_facilities_and_images", fail_after_replacement
    )
    failed = internal_api.post(
        "/internal/venues",
        headers=HEADERS,
        json={**venue_payload, "name": "실패 변경", "facilities": [], "images": []},
    )
    assert failed.status_code == 500
    assert failed.json()["code"] == "INTERNAL_ERROR"
    assert source_count(internal_connection, venue_payload) == int(existing)
    if existing:
        assert stored_collections(internal_connection, venue_id) == (
            venue_payload["facilities"],
            venue_payload["images"],
        )
        assert (
            internal_connection.scalar(
                text("SELECT name FROM venues WHERE venue_id=:id"), {"id": venue_id}
            )
            == venue_payload["name"]
        )


def test_concurrent_same_source_keeps_one_venue_and_complete_collections(internal_app):
    engine = create_engine(_database_url(), poolclass=NullPool, hide_parameters=True)
    source_id = uuid4().hex
    try:
        with engine.begin() as connection:
            assert_test_database(connection)
            region = connection.execute(
                text("SELECT sido,sigungu FROM regions ORDER BY region_id LIMIT 1")
            ).one()
            category = connection.scalar(
                text("SELECT code FROM categories ORDER BY category_id LIMIT 1")
            )
            facilities = list(
                connection.scalars(text("SELECT name FROM facilities ORDER BY facility_id LIMIT 2"))
            )
        versions = [
            {
                "source_site": "synthetic",
                "source_id": source_id,
                "name": f"경쟁 공간 {i}",
                "category_code": category,
                "sido": region.sido,
                "sigungu": region.sigungu,
                "capacity_max": 6,
                "price_per_hour": 10000,
                "facilities": [facilities[i]],
                "images": [f"art:group-{i}"],
            }
            for i in range(2)
        ]

        def write_db():
            with Session(bind=engine) as db:
                yield db

        internal_app.dependency_overrides[get_db_write] = write_db
        barrier = Barrier(8)
        with TestClient(internal_app, raise_server_exceptions=False) as api:

            def submit(i):
                barrier.wait(timeout=30)
                return api.post("/internal/venues", headers=HEADERS, json=versions[i % 2])

            with ThreadPoolExecutor(max_workers=8) as pool:
                responses = list(pool.map(submit, range(8)))
        assert [r.status_code for r in responses].count(201) == 1
        assert [r.status_code for r in responses].count(200) == 7, [r.text for r in responses]
        ids = {r.json()["venue_id"] for r in responses}
        assert len(ids) == 1
        venue_id = ids.pop()
        with engine.connect() as connection:
            assert source_count(connection, versions[0]) == 1
            name = connection.scalar(
                text("SELECT name FROM venues WHERE venue_id=:id"), {"id": venue_id}
            )
            version = next(v for v in versions if v["name"] == name)
            assert stored_collections(connection, venue_id) == (
                version["facilities"],
                version["images"],
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM venues WHERE source_site='synthetic' AND source_id=:source"),
                {"source": source_id},
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM venues WHERE source_site='synthetic' AND source_id=:source"
                    ),
                    {"source": source_id},
                )
                == 0
            )
        engine.dispose()
