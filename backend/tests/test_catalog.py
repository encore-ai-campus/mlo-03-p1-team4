"""F-10·11 유형·지역·시설 계약, MariaDB 조회, 5분 캐시를 검증한다.

A의 실제 app.main, core.db, models.base가 필요하다. 테스트 앱이나 대체 Base는 만들지 않는다.
CHECK_DB_URL은 0001_init.sql과 seed.sql을 적용한 로컬 spacecube_test를 가리켜야 한다.
"""

import inspect
import os
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.db import get_db_read
from app.main import app
from app.models.catalog import Category, Facility, Region
from app.repositories import catalog_repo
from app.routers.catalog import get_categories, get_facilities, get_regions
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
    monkeypatch.setattr(catalog_service, "_regions_cache", None)
    monkeypatch.setattr(catalog_service, "_regions_cache_expires_at", 0.0)
    monkeypatch.setattr(catalog_service, "_facilities_cache", None)
    monkeypatch.setattr(catalog_service, "_facilities_cache_expires_at", 0.0)


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
        pytest.fail("기준 정보 테스트는 mysql+pymysql의 로컬 spacecube_test에서만 실행합니다.")

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


@pytest.mark.parametrize(
    ("path", "endpoint"),
    [("/categories", get_categories), ("/regions", get_regions), ("/facilities", get_facilities)],
)
def test_catalog_routes_use_read_dependency(path, endpoint):
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
        route for route in api_routes(app.routes) if route.path == path and "GET" in route.methods
    ]

    assert len(routes) == 1
    assert str(app.url_path_for(endpoint.__name__)) == path
    assert routes[0].endpoint is endpoint
    assert not inspect.iscoroutinefunction(endpoint)
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


@pytest.fixture
def region_sample(catalog_connection):
    """기존 공간과 충돌하지 않는 지역·공간을 만들고 바깥 트랜잭션에서 롤백한다."""
    prefix = f"F11{uuid4().hex[:8]}"
    sido_a, sido_b, inactive_sido = f"{prefix}A", f"{prefix}B", f"{prefix}C"
    definitions = {
        "a1": (sido_a, "가구"),
        "a2": (sido_a, "나구"),
        "b1": (sido_b, "가구"),
        "inactive": (sido_a, "비활성구"),
        "empty": (sido_a, "공간없음구"),
        "inactive_sido": (inactive_sido, "가구"),
    }
    regions = {
        key: catalog_connection.execute(insert(Region).values(sido=sido, sigungu=sigungu)).lastrowid
        for key, (sido, sigungu) in definitions.items()
    }
    category_id = catalog_connection.scalar(select(Category.category_id).limit(1))
    assert category_id is not None, "기존 seed.sql 적용이 필요합니다."
    for key, active in [
        ("a1", True),
        ("a1", True),
        ("a2", True),
        ("b1", True),
        ("inactive", False),
        ("inactive_sido", False),
    ]:
        catalog_connection.execute(
            text(
                "INSERT INTO venues "
                "(region_id, category_id, name, capacity_max, price_per_hour, source_site, is_active) "
                "VALUES (:region_id, :category_id, :name, 4, 10000, 'synthetic', :active)"
            ),
            {
                "region_id": regions[key],
                "category_id": category_id,
                "name": f"{prefix} 검증 공간",
                "active": active,
            },
        )
    return {
        "prefix": prefix,
        "sido_a": sido_a,
        "sido_b": sido_b,
        "inactive_sido": inactive_sido,
        "regions": regions,
        "items_a": [
            {"region_id": regions["a1"], "sigungu": "가구"},
            {"region_id": regions["a2"], "sigungu": "나구"},
        ],
        "items_b": [{"region_id": regions["b1"], "sigungu": "가구"}],
    }


def test_regions_list_only_active_sidos_without_duplicates(catalog_client, region_sample):
    """활성 공간이 있는 시·도만 기본키 순으로 반환하며 공간·지역 수만큼 중복하지 않는다."""
    response = catalog_client.get("/regions")

    assert response.status_code == 200
    sidos = response.json()
    assert all(isinstance(sido, str) for sido in sidos)
    assert len(sidos) == len(set(sidos))
    assert [sido for sido in sidos if sido.startswith(region_sample["prefix"])] == [
        region_sample["sido_a"],
        region_sample["sido_b"],
    ]


def test_regions_filter_sigungu_and_return_only_public_fields(catalog_client, region_sample):
    """다른 시·도·공간 없는 지역·비활성 지역을 제외하고 실제 지역 ID를 반환한다."""
    for sido_key, items_key in [("sido_a", "items_a"), ("sido_b", "items_b")]:
        response = catalog_client.get("/regions", params={"sido": region_sample[sido_key]})

        assert response.status_code == 200
        assert response.json() == region_sample[items_key]


@pytest.mark.parametrize("case", ["unknown", "inactive"])
def test_regions_without_active_venues_return_empty_list(catalog_client, region_sample, case):
    sido = f"{region_sample['prefix']}없음" if case == "unknown" else region_sample["inactive_sido"]
    response = catalog_client.get("/regions", params={"sido": sido})

    assert response.status_code == 200
    assert response.json() == []


def test_regions_share_snapshot_and_refresh_after_five_minutes(
    catalog_client, catalog_connection, region_sample, monkeypatch
):
    """시·도·시·군·구가 조회 한 번을 공유하고 만료 뒤 비활성화한 지역을 숨긴다."""
    clock = [1000.0]
    calls = []
    original_query = catalog_repo.list_active_regions

    def count_query(db):
        calls.append(True)
        return original_query(db)

    monkeypatch.setattr(catalog_service, "monotonic", lambda: clock[0])
    monkeypatch.setattr(catalog_repo, "list_active_regions", count_query)
    params = {"sido": region_sample["sido_a"]}
    assert catalog_client.get("/regions", params=params).json() == region_sample["items_a"]
    assert region_sample["sido_b"] in catalog_client.get("/regions").json()
    assert (
        catalog_client.get("/regions", params={"sido": region_sample["sido_b"]}).json()
        == (region_sample["items_b"])
    )
    assert len(calls) == 1

    catalog_connection.execute(
        text("UPDATE venues SET is_active = FALSE WHERE region_id IN (:a1, :a2)"),
        {key: region_sample["regions"][key] for key in ("a1", "a2")},
    )
    clock[0] = 1299.0
    assert catalog_client.get("/regions", params=params).json() == region_sample["items_a"]
    assert len(calls) == 1

    clock[0] = 1300.0
    refreshed = catalog_client.get("/regions", params=params)
    assert refreshed.status_code == 200
    assert refreshed.json() == []
    assert region_sample["sido_a"] not in catalog_client.get("/regions").json()
    assert region_sample["sido_b"] in catalog_client.get("/regions").json()
    assert len(calls) == 2


def test_facilities_public_contract_reads_all_database_rows(catalog_client, catalog_connection):
    """공간 연결 여부와 관계없이 DB의 전체 시설을 ID 순으로 반환한다."""
    expected = [
        dict(row)
        for row in catalog_connection.execute(
            select(Facility.facility_id, Facility.name).order_by(Facility.facility_id)
        ).mappings()
    ]
    assert expected, "기존 seed.sql 적용이 필요합니다."

    response = catalog_client.get("/facilities")

    assert response.status_code == 200
    assert response.json() == expected


def test_facilities_refresh_cache_after_five_minutes(
    catalog_client, catalog_connection, monkeypatch
):
    """시설 캐시는 5분 뒤 DB의 이름 변경을 반영한다."""
    clock = [1000.0]
    monkeypatch.setattr(catalog_service, "monotonic", lambda: clock[0])
    initial = catalog_client.get("/facilities")
    assert initial.status_code == 200
    items = initial.json()
    assert items
    facility_id = items[0]["facility_id"]
    test_name = f"검증시설{uuid4().hex[:8]}"
    catalog_connection.execute(
        update(Facility).where(Facility.facility_id == facility_id).values(name=test_name)
    )

    clock[0] = 1299.0
    assert catalog_client.get("/facilities").json() == items
    clock[0] = 1300.0
    refreshed = catalog_client.get("/facilities")
    assert refreshed.status_code == 200
    assert refreshed.json() == [
        {"facility_id": facility_id, "name": test_name},
        *items[1:],
    ]


@pytest.mark.parametrize(
    ("repository_name", "service_name"),
    [("list_active_regions", "list_sidos"), ("list_facilities", "list_facilities")],
)
def test_catalog_does_not_cache_empty_results_as_misses(
    catalog_client, monkeypatch, repository_name, service_name
):
    """빈 목록도 정상 캐시해서 공간 없는 DB에서 매 요청마다 다시 읽지 않는다."""
    calls = []

    def empty_query(_db):
        calls.append(True)
        return []

    monkeypatch.setattr(catalog_repo, repository_name, empty_query)
    path = "/regions" if service_name == "list_sidos" else "/facilities"
    for _ in range(2):
        response = catalog_client.get(path)
        assert response.status_code == 200
        assert response.json() == []
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("repository_name", "service_name"),
    [("list_active_regions", "list_sidos"), ("list_facilities", "list_facilities")],
)
def test_new_catalog_queries_do_not_cache_database_errors(
    catalog_connection, region_sample, monkeypatch, repository_name, service_name
):
    """실패 후 다시 조회할 수 있어야 하며 DB 오류를 빈 목록으로 바꾸지 않는다."""

    def fail_query(_db):
        raise OperationalError("기준 정보 조회", {}, RuntimeError("테스트용 연결 실패"))

    service = getattr(catalog_service, service_name)
    with Session(bind=catalog_connection) as db:
        with monkeypatch.context() as patch:
            patch.setattr(catalog_repo, repository_name, fail_query)
            with pytest.raises(OperationalError):
                service(db)

        result = service(db)

    if service_name == "list_sidos":
        assert region_sample["sido_a"] in result
    else:
        assert result


def test_regions_reject_sido_longer_than_database_column(catalog_client):
    response = catalog_client.get("/regions", params={"sido": "가" * 21})

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == "sido"
