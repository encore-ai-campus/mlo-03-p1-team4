"""F-10 유형 목록 계약·MariaDB 조회·5분 캐시를 검증한다.

A의 실제 app.main, core.db, models.base가 필요하다. 테스트 앱이나 대체 Base는 만들지 않는다.
CHECK_DB_URL은 0001_init.sql과 seed.sql을 적용한 로컬 spacecube_test를 가리켜야 한다.
"""

import inspect
import os

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.db import get_db_read
from app.main import app
from app.models.catalog import Category
from app.repositories import catalog_repo
from app.routers.catalog import get_categories
from app.services import catalog_service

EXPECTED_CATEGORIES = [
    {"code": "studyroom", "name": "스터디룸"},
    {"code": "studio", "name": "스튜디오"},
    {"code": "cafe", "name": "카페"},
    {"code": "lectureroom", "name": "강의실"},
    {"code": "partyroom", "name": "파티룸"},
]


@pytest.fixture(autouse=True)
def reset_category_cache(monkeypatch):
    """테스트 사이에 응답 캐시나 만료 시각이 섞이지 않게 한다."""
    monkeypatch.setattr(catalog_service, "_categories_cache", None)
    monkeypatch.setattr(catalog_service, "_cache_expires_at", 0.0)


@pytest.fixture
def catalog_connection():
    raw_url = os.environ.get("CHECK_DB_URL")
    if not raw_url:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 접속 정보를 지정해 주세요.")

    url = make_url(raw_url)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("유형 테스트는 mysql+pymysql의 로컬 spacecube_test에서만 실행합니다.")

    engine = create_engine(url, poolclass=NullPool, echo=False)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            assert connection.scalar(text("SELECT DATABASE()")) == "spacecube_test"
            assert "MariaDB" in connection.scalar(text("SELECT VERSION()"))
            connection.execute(text("SET time_zone = '+09:00'"))
            connection.execute(
                text(
                    "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,"
                    "NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'"
                )
            )
            try:
                yield connection
            finally:
                # 이름 변경 시험까지 모두 되돌린다. DDL·seed·다른 표에는 손대지 않는다.
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def catalog_client(catalog_connection):
    def override_read_db():
        with Session(bind=catalog_connection) as db:
            yield db

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_read] = override_read_db
    try:
        # 실제 앱의 등록된 라우터를 사용한다. lifespan의 운영 DB 연결은 시작하지 않는다.
        client = TestClient(app)
        try:
            yield client
        finally:
            client.close()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_categories_public_contract(catalog_client):
    """인증 없이 200과 유형 5개를 받으며 내부 category_id는 노출하지 않는다."""
    response = catalog_client.get("/categories")

    assert response.status_code == 200
    assert response.json() == EXPECTED_CATEGORIES


def test_categories_use_read_dependency():
    """실제 앱에 경로가 등록돼 있고 동기 읽기 의존성만 쓰는지 확인한다."""

    def api_routes(routes):
        # FastAPI가 include_router를 묶음으로 보관하는 버전도 내부 경로까지 확인한다.
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
            else:
                included_router = getattr(route, "original_router", None)
                if included_router is not None:
                    yield from api_routes(included_router.routes)

    routes = [
        route
        for route in api_routes(app.routes)
        if route.path == "/categories" and "GET" in route.methods
    ]

    assert len(routes) == 1
    assert str(app.url_path_for("get_categories")) == "/categories"
    assert routes[0].endpoint is get_categories
    assert not inspect.iscoroutinefunction(get_categories)
    assert [dependency.call for dependency in routes[0].dependant.dependencies] == [get_db_read]


def test_categories_read_names_from_database(catalog_client, catalog_connection):
    """하드코딩한 목록이 아니라 DB에 저장된 이름을 반환해야 한다."""
    catalog_connection.execute(
        update(Category).where(Category.code == "studyroom").values(name="테스트 스터디룸")
    )

    response = catalog_client.get("/categories")

    assert response.status_code == 200
    assert response.json() == [
        {"code": "studyroom", "name": "테스트 스터디룸"},
        *EXPECTED_CATEGORIES[1:],
    ]


def test_categories_refresh_cache_after_five_minutes(
    catalog_client, catalog_connection, monkeypatch
):
    """5분 전에는 캐시를 재사용하고 만료 시 DB 변경을 반영한다."""
    clock = [1000.0]
    monkeypatch.setattr(catalog_service, "monotonic", lambda: clock[0])

    initial = catalog_client.get("/categories")
    assert initial.status_code == 200
    assert initial.json() == EXPECTED_CATEGORIES
    catalog_connection.execute(
        update(Category).where(Category.code == "studyroom").values(name="캐시 갱신 확인")
    )

    clock[0] = 1299.0
    cached = catalog_client.get("/categories")
    assert cached.status_code == 200
    assert cached.json() == EXPECTED_CATEGORIES

    clock[0] = 1300.0
    refreshed = catalog_client.get("/categories")
    assert refreshed.status_code == 200
    assert refreshed.json() == [
        {"code": "studyroom", "name": "캐시 갱신 확인"},
        *EXPECTED_CATEGORIES[1:],
    ]


def test_categories_do_not_cache_database_errors(catalog_connection, monkeypatch):
    """DB 조회 실패를 빈 목록 성공으로 숨기거나 캐시에 저장하지 않는다."""

    def fail_query(_db):
        raise OperationalError("유형 조회", {}, RuntimeError("테스트용 연결 실패"))

    with Session(bind=catalog_connection) as db:
        with monkeypatch.context() as patch:
            patch.setattr(catalog_repo, "list_categories", fail_query)
            with pytest.raises(OperationalError):
                catalog_service.list_categories(db)

        categories = catalog_service.list_categories(db)

    assert [category.model_dump() for category in categories] == EXPECTED_CATEGORIES
