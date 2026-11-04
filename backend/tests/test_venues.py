"""F-20 실제 상세 API와 MariaDB, 이미지·NEW·시간 칸 계약을 검증한다."""

import inspect
import os
from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.db import get_db_read
from app.main import app
from app.routers.venues import get_venue
from app.services import venue_service


@pytest.mark.parametrize("images", [[], [""], ["", ""]])
def test_missing_images_use_room_art_default_in_cover_and_gallery(images):
    """이미지 누락 시 대표 이미지와 갤러리 모두 group-0을 반환한다."""
    image, gallery = venue_service.resolve_images(images)

    assert image == "art:group-0"
    assert gallery == ["art:group-0"]


def test_existing_images_keep_repository_order_and_cover():
    """실제 그림이 있으면 첫 그림을 대표로 사용하고 전달받은 목록은 변경하지 않는다."""
    images = ["art:studio-1", "art:cafe-0"]

    image, gallery = venue_service.resolve_images(images)

    assert image == "art:studio-1"
    assert gallery == ["art:studio-1", "art:cafe-0"]
    assert gallery is not images
    assert images == ["art:studio-1", "art:cafe-0"]


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        ("2026-11-05T00:00:00", True),
        ("2026-11-05T23:59:59", True),
        ("2026-10-23T00:00:00", True),
        ("2026-10-23T23:59:59", True),
        ("2026-10-22T23:59:59", False),
        ("2026-11-06T00:00:00", False),
    ],
)
def test_new_uses_fourteen_korean_calendar_dates_including_today(monkeypatch, created_at, expected):
    """오늘·13일 전은 포함, 14일 전·다음 날은 제외하며 시·분·초로 경계를 나누지 않는다."""
    monkeypatch.setattr(venue_service, "get_today", lambda: date(2026, 11, 5))

    assert venue_service.is_new_venue(datetime.fromisoformat(created_at)) is expected


@pytest.fixture
def synthetic_venue():
    """테스트 스키마에 가상 공간 한 개를 만들고 종료 시 롤백·잔존 여부까지 확인한다."""
    raw_url = os.environ.get("CHECK_DB_URL")
    if not raw_url:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 접속 정보를 지정해 주세요.")
    url = make_url(raw_url)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("가상 공간 검증은 로컬 MariaDB spacecube_test에서만 실행합니다.")

    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    source_id = f"policy-test-{uuid4().hex}"
    today = venue_service.get_today()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                assert connection.scalar(text("SELECT DATABASE()")) == "spacecube_test"
                assert "MariaDB" in connection.scalar(text("SELECT VERSION()"))
                connection.execute(text("SET time_zone = '+09:00'"))
                connection.execute(
                    text(
                        "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,"
                        "NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'"
                    )
                )
                category_id = connection.scalar(text("SELECT MIN(category_id) FROM categories"))
                region_id = connection.scalar(text("SELECT MIN(region_id) FROM regions"))
                assert category_id is not None and region_id is not None, (
                    "기존 seed.sql 적용이 필요합니다."
                )
                venue_id = connection.execute(
                    text(
                        "INSERT INTO venues "
                        "(region_id, category_id, name, capacity_max, price_per_hour, min_hours, "
                        "open_hour, close_hour, source_site, source_id, created_at) "
                        "VALUES (:region_id, :category_id, '정책 검증용 가상 공간', 4, 10000, 1, "
                        "9, 23, 'synthetic', :source_id, :created_at)"
                    ),
                    {
                        "region_id": region_id,
                        "category_id": category_id,
                        "source_id": source_id,
                        "created_at": datetime.combine(today, time(12)),
                    },
                ).lastrowid
                yield connection, venue_id, today
            finally:
                transaction.rollback()
                assert (
                    connection.scalar(
                        text(
                            "SELECT COUNT(*) FROM venues "
                            "WHERE source_site = 'synthetic' AND source_id = :source_id"
                        ),
                        {"source_id": source_id},
                    )
                    == 0
                )
    finally:
        engine.dispose()


def test_synthetic_venue_policies_from_real_mariadb(synthetic_venue, monkeypatch):
    """DB에서 읽은 이미지·DATETIME을 공통 함수에 넘기며 상세 HTTP API는 호출하지 않는다."""
    connection, venue_id, today = synthetic_venue
    monkeypatch.setattr(venue_service, "get_today", lambda: today)

    def read_images():
        return list(
            connection.execute(
                text(
                    "SELECT url FROM venue_images WHERE venue_id = :venue_id "
                    "ORDER BY sort_order, image_id"
                ),
                {"venue_id": venue_id},
            ).scalars()
        )

    row = connection.execute(
        text(
            "SELECT name, source_site, capacity_max, price_per_hour FROM venues WHERE venue_id = :id"
        ),
        {"id": venue_id},
    ).one()
    assert tuple(row) == ("정책 검증용 가상 공간", "synthetic", 4, 10000)
    assert read_images() == []
    assert venue_service.resolve_images(read_images()) == ("art:group-0", ["art:group-0"])

    connection.execute(
        text("INSERT INTO venue_images (venue_id, url, sort_order) VALUES (:id, :url, :position)"),
        [
            {"id": venue_id, "url": "art:cafe-0", "position": 1},
            {"id": venue_id, "url": "art:studio-1", "position": 0},
        ],
    )
    assert venue_service.resolve_images(read_images()) == (
        "art:studio-1",
        ["art:studio-1", "art:cafe-0"],
    )

    for age_days, expected in [(0, True), (13, True), (14, False), (-1, False)]:
        connection.execute(
            text("UPDATE venues SET created_at = :created_at WHERE venue_id = :id"),
            {
                "id": venue_id,
                "created_at": datetime.combine(today - timedelta(days=age_days), time(12)),
            },
        )
        stored_time = connection.scalar(
            text("SELECT created_at FROM venues WHERE venue_id = :id"), {"id": venue_id}
        )
        assert isinstance(stored_time, datetime)
        assert stored_time.tzinfo is None
        assert venue_service.is_new_venue(stored_time) is expected


@pytest.fixture
def venue_client(synthetic_venue, monkeypatch):
    """실제 앱의 공개 DB 세션을 테스트 연결로 바꾸고 한국 시각을 고정한다."""
    connection, _, today = synthetic_venue
    monkeypatch.setattr(venue_service, "get_today", lambda: today)
    monkeypatch.setattr(venue_service, "get_now", lambda: datetime.combine(today, time(12, 30)))

    def override_read_db():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db

    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_read] = override_read_db
    client = TestClient(app)
    try:
        # lifespan의 외부 DB·MongoDB 연결은 시작하지 않고 실제 라우터·서비스·SQL을 사용한다.
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


@pytest.fixture
def add_reservation(synthetic_venue):
    """평점 뷰·점유 칸을 검증하는 가상 회원과 예약을 같은 롤백 범위에 넣는다."""
    connection, venue_id, today = synthetic_venue
    now = datetime.combine(today, time(12))
    user_id = connection.execute(
        text(
            "INSERT INTO users "
            "(email, password_hash, name, birth, gender_digit, terms_agreed_at, "
            "privacy_agreed_at, is_synthetic) "
            "VALUES (:email, 'unused-test-hash', '검증회원', '000101', '3', :now, :now, TRUE)"
        ),
        {"email": f"{uuid4().hex}@example.invalid", "now": now},
    ).lastrowid

    def create(*, day=None, start_hour=9, end_hour=10, status="completed"):
        reservation_id = connection.execute(
            text(
                "INSERT INTO reservations "
                "(user_id, venue_id, reserve_date, start_hour, end_hour, headcount, "
                "total_price, status, is_synthetic, created_at) "
                "VALUES (:user_id, :venue_id, :day, :start, :end, 1, :price, :status, TRUE, :now)"
            ),
            {
                "user_id": user_id,
                "venue_id": venue_id,
                "day": today if day is None else day,
                "start": start_hour,
                "end": end_hour,
                "price": (end_hour - start_hour) * 10000,
                "status": status,
                "now": now,
            },
        ).lastrowid
        return reservation_id, user_id

    return create


def test_detail_public_contract_without_images_facilities_or_reviews(venue_client, synthetic_venue):
    """인증 없이 상세 계약 전체를 받고 내부 출처·키는 노출하지 않는다."""
    connection, venue_id, _ = synthetic_venue
    context = connection.execute(
        text(
            "SELECT c.code, c.name, r.sido, r.sigungu FROM venues v "
            "JOIN categories c ON c.category_id = v.category_id "
            "JOIN regions r ON r.region_id = v.region_id WHERE v.venue_id = :id"
        ),
        {"id": venue_id},
    ).one()

    response = venue_client.get(f"/venues/{venue_id}")

    assert response.status_code == 200
    assert response.json() == {
        "venue_id": venue_id,
        "name": "정책 검증용 가상 공간",
        "category": {"code": context[0], "name": context[1]},
        "region": {"sido": context[2], "sigungu": context[3]},
        "capacity_max": 4,
        "price_per_hour": 10000,
        "min_hours": 1,
        "open_hour": 9,
        "close_hour": 23,
        "rating_avg": 0.0,
        "review_count": 0,
        "image": "art:group-0",
        "images": ["art:group-0"],
        "facilities": [],
        "is_new": True,
        "description": None,
        "notice": None,
        "slots": [{"hour": hour, "taken": False, "past": hour <= 12} for hour in range(9, 23)],
    }
    assert (
        connection.scalar(
            text("SELECT COUNT(*) FROM venue_images WHERE venue_id = :id"), {"id": venue_id}
        )
        == 0
    )


def test_detail_preserves_image_order_and_facility_ids(venue_client, synthetic_venue):
    """그림·시설을 여러 개 넣어도 중복 없이 정렬하고 상세 설명·최소시간을 반환한다."""
    connection, venue_id, _ = synthetic_venue
    connection.execute(
        text("INSERT INTO venue_images (venue_id, url, sort_order) VALUES (:id, :url, :position)"),
        [
            {"id": venue_id, "url": "art:cafe-0", "position": 1},
            {"id": venue_id, "url": "art:studio-1", "position": 0},
            {"id": venue_id, "url": "art:group-1", "position": 0},
        ],
    )
    facilities = (
        connection.execute(
            text("SELECT facility_id, name FROM facilities ORDER BY facility_id LIMIT 2")
        )
        .mappings()
        .all()
    )
    assert len(facilities) == 2, "기존 seed.sql 적용이 필요합니다."
    connection.execute(
        text("INSERT INTO venue_facilities (venue_id, facility_id) VALUES (:id, :facility_id)"),
        [{"id": venue_id, "facility_id": row["facility_id"]} for row in reversed(facilities)],
    )
    connection.execute(
        text(
            "UPDATE venues SET description = '검증용 소개', notice = '검증용 안내', "
            "min_hours = 2 WHERE venue_id = :id"
        ),
        {"id": venue_id},
    )

    response = venue_client.get(f"/venues/{venue_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["image"] == "art:studio-1"
    assert body["images"] == ["art:studio-1", "art:group-1", "art:cafe-0"]
    assert body["facilities"] == [dict(row) for row in facilities]
    assert body["description"] == "검증용 소개"
    assert body["notice"] == "검증용 안내"
    assert body["min_hours"] == 2


def test_detail_reads_rating_view_and_ignores_deleted_reviews(
    venue_client, synthetic_venue, add_reservation
):
    """평점을 하드코딩하지 않고 기존 뷰의 평균·건수를 JSON 숫자로 반환한다."""
    connection, venue_id, today = synthetic_venue
    for rating, deleted in [(4, False), (5, False), (1, True)]:
        reservation_id, user_id = add_reservation()
        connection.execute(
            text(
                "INSERT INTO reviews (reservation_id, user_id, rating, content, created_at, deleted_at) "
                "VALUES (:reservation_id, :user_id, :rating, '검증용 후기', :now, :deleted_at)"
            ),
            {
                "reservation_id": reservation_id,
                "user_id": user_id,
                "rating": rating,
                "now": datetime.combine(today, time(12)),
                "deleted_at": datetime.combine(today, time(12)) if deleted else None,
            },
        )

    response = venue_client.get(f"/venues/{venue_id}")

    assert response.status_code == 200
    assert response.json()["rating_avg"] == 4.5
    assert isinstance(response.json()["rating_avg"], float)
    assert response.json()["review_count"] == 2


def test_detail_today_slots_use_occupancy_and_operating_hours(
    venue_client, synthetic_venue, add_reservation
):
    """완료 예약의 칸도 점유로 표시하고 다른 날짜는 제외하며 지난 빈 칸을 유지한다."""
    connection, venue_id, today = synthetic_venue
    connection.execute(
        text("UPDATE venues SET open_hour = 10, close_hour = 14 WHERE venue_id = :id"),
        {"id": venue_id},
    )
    for day, hour, status in [
        (today, 10, "completed"),
        (today + timedelta(days=1), 12, "confirmed"),
    ]:
        reservation_id, _ = add_reservation(
            day=day, start_hour=hour, end_hour=hour + 1, status=status
        )
        connection.execute(
            text(
                "INSERT INTO reservation_slots (venue_id, slot_date, slot_hour, reservation_id) "
                "VALUES (:venue_id, :day, :hour, :reservation_id)"
            ),
            {"venue_id": venue_id, "day": day, "hour": hour, "reservation_id": reservation_id},
        )

    response = venue_client.get(f"/venues/{venue_id}")

    assert response.status_code == 200
    assert response.json()["slots"] == [
        {"hour": 10, "taken": True, "past": True},
        {"hour": 11, "taken": False, "past": True},
        {"hour": 12, "taken": False, "past": True},
        {"hour": 13, "taken": False, "past": False},
    ]


@pytest.mark.parametrize(
    ("age_days", "expected"), [(0, True), (13, True), (14, False), (-1, False)]
)
def test_detail_new_flag_uses_database_korean_date(
    venue_client, synthetic_venue, age_days, expected
):
    connection, venue_id, today = synthetic_venue
    connection.execute(
        text("UPDATE venues SET created_at = :created_at WHERE venue_id = :id"),
        {
            "id": venue_id,
            "created_at": datetime.combine(today - timedelta(days=age_days), time(12)),
        },
    )

    response = venue_client.get(f"/venues/{venue_id}")

    assert response.status_code == 200
    assert response.json()["is_new"] is expected


@pytest.mark.parametrize("case", ["missing", "inactive"])
def test_detail_missing_and_inactive_have_same_404(venue_client, synthetic_venue, case):
    connection, venue_id, _ = synthetic_venue
    if case == "inactive":
        connection.execute(
            text("UPDATE venues SET is_active = FALSE WHERE venue_id = :id"), {"id": venue_id}
        )
        requested_id = venue_id
    else:
        requested_id = 9223372036854775807

    response = venue_client.get(f"/venues/{requested_id}")

    assert response.status_code == 404
    assert response.json() == {
        "code": "VENUE_NOT_FOUND",
        "message": "공간을 찾을 수 없어요.",
        "detail": None,
    }


@pytest.mark.parametrize("venue_id", ["0", "-1", "abc", "1.5", "9223372036854775808"])
def test_detail_invalid_id_uses_common_validation(venue_client, venue_id):
    response = venue_client.get(f"/venues/{venue_id}")

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == "venue_id"


def test_detail_reads_latest_values_without_writing(venue_client, synthetic_venue):
    connection, venue_id, _ = synthetic_venue
    initial = venue_client.get(f"/venues/{venue_id}")
    assert initial.status_code == 200
    connection.execute(
        text("UPDATE venues SET price_per_hour = 12000 WHERE venue_id = :id"), {"id": venue_id}
    )

    updated = venue_client.get(f"/venues/{venue_id}")

    assert updated.status_code == 200
    assert updated.json()["price_per_hour"] == 12000
    assert (
        connection.scalar(
            text("SELECT COUNT(*) FROM reservations WHERE venue_id = :id"), {"id": venue_id}
        )
        == 0
    )


def test_detail_router_is_registered_with_public_read_dependency():
    def api_routes(routes, prefix=""):
        for route in routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, route
            else:
                included = getattr(route, "original_router", None)
                if included is not None:
                    # 포함 라우터를 지연 보관하는 FastAPI에서도 앱의 최종 경로를 검사한다.
                    context = getattr(route, "include_context", None)
                    yield from api_routes(included.routes, prefix + getattr(context, "prefix", ""))

    routes = [
        route
        for path, route in api_routes(app.routes)
        if path == "/venues/{venue_id}" and "GET" in route.methods
    ]
    assert len(routes) == 1
    assert str(app.url_path_for("get_venue", venue_id=7)) == "/venues/7"
    assert routes[0].endpoint is get_venue
    assert not inspect.iscoroutinefunction(get_venue)
    assert [dependency.call for dependency in routes[0].dependant.dependencies] == [get_db_read]
