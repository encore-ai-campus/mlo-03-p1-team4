"""F-12~13 검색·정렬과 F-20~22 공간 API의 MariaDB 계약을 검증한다."""

import inspect
import os
from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.db import get_db_read
from app.main import app
from app.routers.venues import get_available_dates, get_slots, get_venue
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


@pytest.mark.parametrize(
    ("path", "endpoint"),
    [
        ("/venues/{venue_id}", get_venue),
        ("/venues/{venue_id}/slots", get_slots),
        ("/venues/{venue_id}/available-dates", get_available_dates),
    ],
)
def test_venue_router_is_registered_with_public_read_dependency(path, endpoint):
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
        for route_path, route in api_routes(app.routes)
        if route_path == path and "GET" in route.methods
    ]
    assert len(routes) == 1
    assert str(app.url_path_for(endpoint.__name__, venue_id=7)) == path.replace("{venue_id}", "7")
    assert routes[0].endpoint is endpoint
    assert not inspect.iscoroutinefunction(endpoint)
    assert [dependency.call for dependency in routes[0].dependant.dependencies] == [get_db_read]


def test_slots_today_matches_detail(venue_client, synthetic_venue):
    """별도 API와 상세의 오늘 칸은 같은 계약을 유지한다."""
    _, venue_id, today = synthetic_venue
    response = venue_client.get(f"/venues/{venue_id}/slots", params={"date": today.isoformat()})
    assert response.status_code == 200
    assert response.json() == venue_client.get(f"/venues/{venue_id}").json()["slots"]


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_slots_isolate_dates_and_keep_completed_occupancy(
    venue_client, synthetic_venue, add_reservation, offset
):
    """완료·확정 칸은 해당 날짜에만 점유하며 최소시간으로 표시 칸을 줄이지 않는다."""
    connection, venue_id, today = synthetic_venue
    connection.execute(
        text(
            "UPDATE venues SET open_hour = 10, close_hour = 14, min_hours = 2 WHERE venue_id = :id"
        ),
        {"id": venue_id},
    )
    for day_offset, hour in [(-1, 11), (0, 12), (1, 13)]:
        day = today + timedelta(days=day_offset)
        reservation_id, _ = add_reservation(
            day=day,
            start_hour=hour,
            end_hour=hour + 1,
            status="completed" if day_offset < 0 else "confirmed",
        )
        connection.execute(
            text(
                "INSERT INTO reservation_slots (venue_id, slot_date, slot_hour, reservation_id) "
                "VALUES (:id, :day, :hour, :reservation_id)"
            ),
            {"id": venue_id, "day": day, "hour": hour, "reservation_id": reservation_id},
        )
    response = venue_client.get(
        f"/venues/{venue_id}/slots", params={"date": (today + timedelta(days=offset)).isoformat()}
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "hour": hour,
            "taken": hour == 12 + offset,
            "past": offset < 0 or (offset == 0 and hour <= 12),
        }
        for hour in range(10, 14)
    ]


def test_slots_ignore_other_venues(venue_client, synthetic_venue, add_reservation):
    connection, venue_id, today = synthetic_venue
    other_id = connection.execute(
        text(
            "INSERT INTO venues (region_id, category_id, name, capacity_max, price_per_hour, "
            "open_hour, close_hour) SELECT region_id, category_id, '다른 가상 공간', 4, 10000, "
            "9, 23 FROM venues WHERE venue_id = :id"
        ),
        {"id": venue_id},
    ).lastrowid
    reservation_id, _ = add_reservation(start_hour=13, end_hour=14, status="confirmed")
    connection.execute(
        text("UPDATE reservations SET venue_id = :id WHERE reservation_id = :rid"),
        {"id": other_id, "rid": reservation_id},
    )
    connection.execute(
        text(
            "INSERT INTO reservation_slots (venue_id, slot_date, slot_hour, reservation_id) "
            "VALUES (:id, :day, 13, :rid)"
        ),
        {"id": other_id, "day": today, "rid": reservation_id},
    )
    response = venue_client.get(f"/venues/{venue_id}/slots", params={"date": today.isoformat()})
    assert response.status_code == 200
    assert not any(slot["taken"] for slot in response.json())


@pytest.mark.parametrize(
    ("past_days", "future_days", "offset", "allowed"),
    [
        (365, 365, -365, True),
        (365, 365, 365, True),
        (365, 365, -366, False),
        (365, 365, 366, False),
        (2, 3, -2, True),
        (2, 3, 3, True),
        (2, 3, -3, False),
        (2, 3, 4, False),
        (0, 0, 0, True),
        (0, 0, -1, False),
        (0, 0, 1, False),
    ],
)
def test_slots_configured_date_range(
    venue_client, synthetic_venue, monkeypatch, past_days, future_days, offset, allowed
):
    """기본·변경·0일 설정 모두 양끝 날짜를 포함한다."""
    _, venue_id, today = synthetic_venue
    settings = Settings(
        _env_file=None, booking_past_days=past_days, booking_future_days=future_days
    )
    monkeypatch.setattr(venue_service, "get_settings", lambda: settings)
    response = venue_client.get(
        f"/venues/{venue_id}/slots", params={"date": (today + timedelta(days=offset)).isoformat()}
    )
    if allowed:
        assert response.status_code == 200
        assert response.json() == [
            {"hour": hour, "taken": False, "past": offset < 0 or (offset == 0 and hour <= 12)}
            for hour in range(9, 23)
        ]
    else:
        assert response.status_code == 400
        assert response.json() == {
            "code": "OUT_OF_RANGE",
            "message": "예약할 수 없는 날짜나 시간이에요.",
            "detail": {
                "reason": "date",
                "min_date": (today - timedelta(days=past_days)).isoformat(),
                "max_date": (today + timedelta(days=future_days)).isoformat(),
            },
        }


@pytest.mark.parametrize(
    "requested_date",
    [
        None,
        "",
        "2026-02-30",
        "2026-13-01",
        "20261105",
        "2026-1-05",
        "2026-11-05T00:00:00",
        "not-date",
        "2026-W45-4",
        "1762387200",
    ],
)
def test_slots_reject_missing_or_noncanonical_date(venue_client, synthetic_venue, requested_date):
    _, venue_id, _ = synthetic_venue
    params = {} if requested_date is None else {"date": requested_date}
    response = venue_client.get(f"/venues/{venue_id}/slots", params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == "date"


@pytest.mark.parametrize("venue_id", ["0", "-1", "abc", "1.5", "9223372036854775808"])
def test_slots_reject_invalid_id(venue_client, synthetic_venue, venue_id):
    _, _, today = synthetic_venue
    response = venue_client.get(f"/venues/{venue_id}/slots", params={"date": today.isoformat()})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == "venue_id"


@pytest.mark.parametrize("inactive", [False, True])
def test_slots_missing_or_inactive_404(venue_client, synthetic_venue, inactive):
    connection, venue_id, today = synthetic_venue
    if inactive:
        connection.execute(
            text("UPDATE venues SET is_active = FALSE WHERE venue_id = :id"), {"id": venue_id}
        )
    requested_id = venue_id if inactive else 9223372036854775807
    response = venue_client.get(f"/venues/{requested_id}/slots", params={"date": today.isoformat()})
    assert response.status_code == 404
    assert response.json() == {
        "code": "VENUE_NOT_FOUND",
        "message": "공간을 찾을 수 없어요.",
        "detail": None,
    }


def test_slots_reread_occupancy(venue_client, synthetic_venue, add_reservation):
    """조회 후 추가된 칸을 다음 요청과 F-20에서 즉시 반영한다."""
    connection, venue_id, today = synthetic_venue
    path = f"/venues/{venue_id}/slots"
    before = venue_client.get(path, params={"date": today.isoformat()})
    assert before.status_code == 200
    assert not any(slot["taken"] for slot in before.json())
    reservation_id, _ = add_reservation(start_hour=13, end_hour=14, status="confirmed")
    connection.execute(
        text(
            "INSERT INTO reservation_slots (venue_id, slot_date, slot_hour, reservation_id) "
            "VALUES (:id, :day, 13, :rid)"
        ),
        {"id": venue_id, "day": today, "rid": reservation_id},
    )
    after = venue_client.get(path, params={"date": today.isoformat()})
    assert after.status_code == 200
    assert [slot["hour"] for slot in after.json() if slot["taken"]] == [13]
    assert after.json() == venue_client.get(f"/venues/{venue_id}").json()["slots"]


@pytest.mark.parametrize("current_hour", [0, 9, 23])
def test_slots_today_hour_boundaries(venue_client, synthetic_venue, monkeypatch, current_hour):
    _, venue_id, today = synthetic_venue
    monkeypatch.setattr(
        venue_service, "get_now", lambda: datetime.combine(today, time(current_hour))
    )
    response = venue_client.get(f"/venues/{venue_id}/slots", params={"date": today.isoformat()})
    assert response.status_code == 200
    assert response.json() == [
        {"hour": hour, "taken": False, "past": hour <= current_hour} for hour in range(9, 23)
    ]


@pytest.fixture
def add_taken_slots(synthetic_venue, add_reservation):
    """필요한 날짜·시각의 가상 예약과 점유 칸을 외부 롤백 범위 안에 만든다."""
    connection, own_venue_id, _ = synthetic_venue

    def create(day, hours, *, status="confirmed", other_venue_id=None):
        venue_id = own_venue_id if other_venue_id is None else other_venue_id
        for hour in hours:
            reservation_id, _ = add_reservation(
                day=day, start_hour=hour, end_hour=hour + 1, status=status
            )
            if other_venue_id is not None:
                connection.execute(
                    text("UPDATE reservations SET venue_id = :id WHERE reservation_id = :rid"),
                    {"id": venue_id, "rid": reservation_id},
                )
            connection.execute(
                text(
                    "INSERT INTO reservation_slots (venue_id, slot_date, slot_hour, reservation_id) "
                    "VALUES (:id, :day, :hour, :rid)"
                ),
                {"id": venue_id, "day": day, "hour": hour, "rid": reservation_id},
            )

    return create


def test_available_dates_default_public_contract(venue_client, synthetic_venue):
    """예약 불가능한 날도 담을 수 있는 날짜 목록 계약과 기본 14일을 확인한다."""
    _, venue_id, today = synthetic_venue
    response = venue_client.get(f"/venues/{venue_id}/available-dates")
    assert response.status_code == 200
    assert response.json() == {
        "venue_id": venue_id,
        "offset": 0,
        "days": 14,
        "min_date": (today - timedelta(days=365)).isoformat(),
        "max_date": (today + timedelta(days=365)).isoformat(),
        "dates": [
            {"date": (today + timedelta(days=i)).isoformat(), "free": 14, "bookable": True}
            for i in range(14)
        ],
    }


@pytest.mark.parametrize("offset", [-14, 0, 14])
def test_available_dates_include_past_free_hours(venue_client, synthetic_venue, offset):
    _, venue_id, today = synthetic_venue
    response = venue_client.get(
        f"/venues/{venue_id}/available-dates", params={"offset": offset, "days": 3}
    )
    assert response.status_code == 200
    assert response.json()["dates"] == [
        {"date": (today + timedelta(days=offset + i)).isoformat(), "free": 14, "bookable": True}
        for i in range(3)
    ]


@pytest.mark.parametrize(
    ("min_hours", "taken", "free", "bookable"),
    [
        (1, [], 6, True),
        (4, [], 6, True),
        (1, [9, 10, 11, 12, 13, 14], 0, False),
        (2, [10, 12, 14], 3, False),
        (2, [9, 10, 11, 12], 2, True),
        (2, [11, 12, 13, 14], 2, True),
        (3, [9, 10, 11], 3, True),
        (4, [9, 10, 11], 3, False),
    ],
)
def test_available_dates_require_consecutive_hours(
    venue_client, synthetic_venue, add_taken_slots, min_hours, taken, free, bookable
):
    """빈 칸 총수와 연속 길이를 구분하고 마지막 시각까지 이어진 빈 칸도 센다."""
    connection, venue_id, today = synthetic_venue
    connection.execute(
        text(
            "UPDATE venues SET open_hour = 9, close_hour = 15, min_hours = :minimum WHERE venue_id = :id"
        ),
        {"id": venue_id, "minimum": min_hours},
    )
    add_taken_slots(today, taken)
    response = venue_client.get(f"/venues/{venue_id}/available-dates", params={"days": 1})
    assert response.status_code == 200
    assert response.json()["dates"] == [
        {"date": today.isoformat(), "free": free, "bookable": bookable}
    ]
    slots = venue_client.get(f"/venues/{venue_id}/slots", params={"date": today.isoformat()})
    assert slots.status_code == 200
    assert sum(not slot["taken"] for slot in slots.json()) == free


def test_available_dates_ignore_occupancy_outside_operating_hours(
    venue_client, synthetic_venue, add_taken_slots
):
    """영업시간 변경 전의 점유가 있어도 현재 영업시간만 세며 최소시간 미달은 불가다."""
    connection, venue_id, today = synthetic_venue
    add_taken_slots(today, [9, 10, 14, 22])
    connection.execute(
        text(
            "UPDATE venues SET open_hour = 12, close_hour = 14, min_hours = 3 WHERE venue_id = :id"
        ),
        {"id": venue_id},
    )
    response = venue_client.get(f"/venues/{venue_id}/available-dates", params={"days": 1})
    assert response.status_code == 200
    assert response.json()["dates"] == [{"date": today.isoformat(), "free": 2, "bookable": False}]


def test_available_dates_isolate_venues_dates_and_keep_completed_slots(
    venue_client, synthetic_venue, add_taken_slots
):
    connection, venue_id, today = synthetic_venue
    other_id = connection.execute(
        text(
            "INSERT INTO venues (region_id, category_id, name, capacity_max, price_per_hour) "
            "SELECT region_id, category_id, '날짜 검증용 다른 공간', 4, 10000 FROM venues WHERE venue_id = :id"
        ),
        {"id": venue_id},
    ).lastrowid
    add_taken_slots(today, range(9, 23), other_venue_id=other_id)
    add_taken_slots(today - timedelta(days=2), range(9, 23), status="completed")
    add_taken_slots(today + timedelta(days=2), range(9, 23))
    for offset, hours in [(-1, [9]), (0, [9, 10]), (1, [9, 10, 11])]:
        add_taken_slots(
            today + timedelta(days=offset), hours, status="completed" if offset < 0 else "confirmed"
        )
    response = venue_client.get(
        f"/venues/{venue_id}/available-dates", params={"offset": -1, "days": 3}
    )
    assert response.status_code == 200
    assert response.json()["dates"] == [
        {"date": (today + timedelta(days=offset)).isoformat(), "free": free, "bookable": True}
        for offset, free in [(-1, 13), (0, 12), (1, 11)]
    ]


@pytest.mark.parametrize(
    ("past_days", "future_days", "offset", "days", "count"),
    [
        (365, 365, -365, 14, 14),
        (365, 365, 364, 14, 2),
        (365, 365, 365, 14, 1),
        (365, 365, -366, 14, None),
        (365, 365, 366, 14, None),
        (2, 3, -2, 31, 6),
        (2, 3, 0, 31, 4),
        (2, 3, 3, 1, 1),
        (2, 3, -3, 1, None),
        (2, 3, 4, 1, None),
        (0, 0, 0, 14, 1),
        (0, 0, -1, 1, None),
        (0, 0, 1, 1, None),
        (365, 365, 10**30, 14, None),
        (365, 365, -(10**30), 14, None),
    ],
)
def test_available_dates_configured_range_and_clipped_last_page(
    venue_client, synthetic_venue, monkeypatch, past_days, future_days, offset, days, count
):
    """범위 양끝·0일·짧은 범위와 큰 offset을 확인하고 days는 요청값을 보존한다."""
    _, venue_id, today = synthetic_venue
    monkeypatch.setattr(
        venue_service,
        "get_settings",
        lambda: Settings(
            _env_file=None, booking_past_days=past_days, booking_future_days=future_days
        ),
    )
    response = venue_client.get(
        f"/venues/{venue_id}/available-dates", params={"offset": offset, "days": days}
    )
    min_date = (today - timedelta(days=past_days)).isoformat()
    max_date = (today + timedelta(days=future_days)).isoformat()
    if count is None:
        assert response.status_code == 400
        assert response.json() == {
            "code": "OUT_OF_RANGE",
            "message": "예약할 수 없는 날짜나 시간이에요.",
            "detail": {"reason": "date", "min_date": min_date, "max_date": max_date},
        }
    else:
        assert response.status_code == 200
        assert response.json() == {
            "venue_id": venue_id,
            "offset": offset,
            "days": days,
            "min_date": min_date,
            "max_date": max_date,
            "dates": [
                {
                    "date": (today + timedelta(days=offset + i)).isoformat(),
                    "free": 14,
                    "bookable": True,
                }
                for i in range(count)
            ],
        }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("days", "0"),
        ("days", "-1"),
        ("days", "32"),
        ("days", "1.5"),
        ("days", "abc"),
        ("days", ""),
        ("offset", "abc"),
        ("offset", "1.5"),
        ("offset", ""),
    ],
)
def test_available_dates_invalid_query(venue_client, synthetic_venue, field, value):
    _, venue_id, _ = synthetic_venue
    response = venue_client.get(f"/venues/{venue_id}/available-dates", params={field: value})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == field


@pytest.mark.parametrize("venue_id", ["0", "-1", "abc", "1.5", "9223372036854775808"])
def test_available_dates_invalid_id(venue_client, venue_id):
    response = venue_client.get(f"/venues/{venue_id}/available-dates")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == "venue_id"


@pytest.mark.parametrize("inactive", [False, True])
def test_available_dates_missing_or_inactive(venue_client, synthetic_venue, inactive):
    connection, venue_id, _ = synthetic_venue
    if inactive:
        connection.execute(
            text("UPDATE venues SET is_active = FALSE WHERE venue_id = :id"), {"id": venue_id}
        )
    response = venue_client.get(
        f"/venues/{venue_id if inactive else 9223372036854775807}/available-dates"
    )
    assert response.status_code == 404
    assert response.json() == {
        "code": "VENUE_NOT_FOUND",
        "message": "공간을 찾을 수 없어요.",
        "detail": None,
    }


def test_available_dates_reread_occupancy_and_minimum(
    venue_client, synthetic_venue, add_taken_slots
):
    connection, venue_id, today = synthetic_venue
    connection.execute(
        text(
            "UPDATE venues SET open_hour = 9, close_hour = 11, min_hours = 2 WHERE venue_id = :id"
        ),
        {"id": venue_id},
    )
    path = f"/venues/{venue_id}/available-dates"

    def assert_day(free, bookable):
        response = venue_client.get(path, params={"days": 1})
        assert response.status_code == 200
        assert response.json()["dates"] == [
            {"date": today.isoformat(), "free": free, "bookable": bookable}
        ]

    assert_day(2, True)
    add_taken_slots(today, [10])
    assert_day(1, False)
    connection.execute(
        text("UPDATE venues SET min_hours = 1 WHERE venue_id = :id"), {"id": venue_id}
    )
    assert_day(1, True)
    connection.execute(
        text("DELETE FROM reservation_slots WHERE venue_id = :id AND slot_date = :day"),
        {"id": venue_id, "day": today},
    )
    assert_day(2, True)


def test_available_dates_batch_query_for_maximum_page(venue_client, synthetic_venue):
    """31일 조회도 공간·점유 2회만 SELECT하며 상세용 이미지·평점을 읽지 않는다."""
    connection, venue_id, _ = synthetic_venue
    statements = []

    def collect_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", collect_sql)
    try:
        response = venue_client.get(f"/venues/{venue_id}/available-dates", params={"days": 31})
    finally:
        event.remove(connection, "before_cursor_execute", collect_sql)
    assert response.status_code == 200
    assert len(response.json()["dates"]) == 31
    assert len(statements) == 2
    assert "reservation_slots" in statements[1]
    assert all("venue_images" not in sql and "v_venue_rating" not in sql for sql in statements)


@pytest.fixture
def search_catalog(synthetic_venue):
    """검색용 공간은 고유 키워드로 격리하고 같은 DB 트랜잭션에서 롤백한다."""
    connection, base_id, today = synthetic_venue
    keyword = f"검색검증-{uuid4().hex}"
    base_region = connection.execute(
        text(
            "SELECT r.region_id, r.sido, r.sigungu FROM regions r "
            "JOIN venues v ON v.region_id = r.region_id WHERE v.venue_id = :id"
        ),
        {"id": base_id},
    ).one()
    other_region = connection.execute(
        text(
            "SELECT region_id, sido, sigungu FROM regions WHERE sido <> :sido "
            "ORDER BY region_id LIMIT 1"
        ),
        {"sido": base_region.sido},
    ).one()
    categories = {
        row.code: row.category_id
        for row in connection.execute(text("SELECT category_id, code FROM categories"))
    }
    facility_ids = list(
        connection.execute(
            text("SELECT facility_id FROM facilities ORDER BY facility_id LIMIT 2")
        ).scalars()
    )
    assert len(facility_ids) == 2, "기존 seed.sql 적용이 필요합니다."
    connection.execute(
        text("UPDATE venues SET name = :name WHERE venue_id = :id"),
        {"name": f"{keyword} 기준 공간", "id": base_id},
    )

    def create(
        suffix,
        *,
        category="studyroom",
        region=base_region,
        capacity=6,
        price=10000,
        min_hours=1,
        open_hour=9,
        close_hour=23,
    ):
        source_id = f"search-test-{uuid4().hex}"
        venue_id = connection.execute(
            text(
                "INSERT INTO venues "
                "(region_id, category_id, name, capacity_max, price_per_hour, min_hours, "
                "open_hour, close_hour, source_site, source_id, created_at) "
                "VALUES (:region, :category, :name, :capacity, :price, :min_hours, "
                ":open, :close, 'synthetic', :source_id, :created_at)"
            ),
            {
                "region": region.region_id,
                "category": categories[category],
                "name": f"{keyword} {suffix}",
                "capacity": capacity,
                "price": price,
                "min_hours": min_hours,
                "open": open_hour,
                "close": close_hour,
                "source_id": source_id,
                "created_at": datetime.combine(today, time(12)),
            },
        ).lastrowid
        return venue_id

    def link_facilities(venue_id, ids):
        connection.execute(
            text(
                "INSERT INTO venue_facilities (venue_id, facility_id) "
                "VALUES (:venue_id, :facility_id)"
            ),
            [{"venue_id": venue_id, "facility_id": facility_id} for facility_id in ids],
        )

    connection.execute(
        text(
            "UPDATE venues SET region_id = :region, category_id = :category, "
            "capacity_max = 6, price_per_hour = 30000, min_hours = 2, open_hour = 9, close_hour = 15 "
            "WHERE venue_id = :id"
        ),
        {"id": base_id, "region": base_region.region_id, "category": categories["studyroom"]},
    )
    link_facilities(base_id, facility_ids)
    return {
        "base_id": base_id,
        "keyword": keyword,
        "today": today,
        "base_region": base_region,
        "other_region": other_region,
        "facility_ids": facility_ids,
        "connection": connection,
        "create": create,
        "link_facilities": link_facilities,
    }


def test_search_default_public_contract_and_q_across_fields(venue_client, search_catalog):
    data = search_catalog
    response = venue_client.get("/venues", params={"q": data["keyword"]})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 10
    assert body["total"] == 1
    item = body["items"][0]
    assert set(item) == {
        "venue_id",
        "name",
        "category",
        "region",
        "capacity_max",
        "price_per_hour",
        "open_hour",
        "close_hour",
        "rating_avg",
        "review_count",
        "image",
        "facilities",
        "is_new",
        "slots",
    }
    assert item["venue_id"] == data["base_id"]
    assert item["name"] == f"{data['keyword']} 기준 공간"
    assert item["price_per_hour"] == 30000
    assert item["image"] == "art:group-0"
    assert item["facilities"] == [
        row["name"]
        for row in venue_client.get("/facilities").json()
        if row["facility_id"] in data["facility_ids"]
    ]
    assert item["is_new"] is True
    assert item["slots"] == [
        {"hour": hour, "taken": False, "past": hour <= 12} for hour in range(9, 15)
    ]

    facility_name = item["facilities"][0]
    for query in (facility_name, data["base_region"].sigungu):
        matches = venue_client.get("/venues", params={"q": query}).json()["items"]
        assert data["base_id"] in [match["venue_id"] for match in matches]


def test_search_combines_type_region_people_and_all_facilities(venue_client, search_catalog):
    data = search_catalog
    studio = data["create"](
        "스튜디오", category="studio", region=data["other_region"], capacity=10, min_hours=1
    )
    small_cafe = data["create"]("작은 카페", category="cafe", capacity=2)
    data["link_facilities"](studio, [data["facility_ids"][0]])
    data["link_facilities"](small_cafe, [data["facility_ids"][1]])

    cases = [
        ({"category": "studio"}, [studio]),
        (
            {"category": "all", "sido": "전국", "sigungu": "전체"},
            [data["base_id"], studio, small_cafe],
        ),
        ({"sido": data["base_region"].sido}, [data["base_id"], small_cafe]),
        ({"people": 5}, [data["base_id"], studio]),
        ({"facilities": ",".join(map(str, data["facility_ids"]))}, [data["base_id"]]),
        ({"facilities": str(data["facility_ids"][0])}, [data["base_id"], studio]),
    ]
    for filters, expected_ids in cases:
        response = venue_client.get("/venues", params={"q": data["keyword"], **filters})
        assert response.status_code == 200
        assert {item["venue_id"] for item in response.json()["items"]} == set(expected_ids)
        assert response.json()["total"] == len(expected_ids)


def test_search_filters_requested_hours_and_now_against_live_slots(
    venue_client, search_catalog, add_taken_slots
):
    data = search_catalog
    studio = data["create"](
        "오늘 가능한 스튜디오", category="studio", open_hour=13, close_hour=15, min_hours=1
    )
    response = venue_client.get(
        "/venues",
        params={
            "q": data["keyword"],
            "category": "studio",
            "start_hour": 13,
            "hours": 2,
            "date": data["today"].isoformat(),
        },
    )
    assert response.status_code == 200
    assert [item["venue_id"] for item in response.json()["items"]] == [studio]

    one_hour = data["create"](
        "최소 한 시간 스튜디오", category="studio", open_hour=9, close_hour=10, min_hours=1
    )
    response = venue_client.get(
        "/venues",
        params={
            "q": data["keyword"],
            "start_hour": 9,
            "hours": 1,
            "date": data["today"].isoformat(),
        },
    )
    assert response.status_code == 200
    assert [item["venue_id"] for item in response.json()["items"]] == [one_hour]

    response = venue_client.get(
        "/venues",
        params={
            "q": data["keyword"],
            "category": "studio",
            "start_hour": 13,
            "hours": 2,
            "date": (data["today"] - timedelta(days=1)).isoformat(),
            "now": "true",
        },
    )
    assert [item["venue_id"] for item in response.json()["items"]] == [studio]
    assert response.json()["items"][0]["slots"] == [
        {"hour": 13, "taken": False, "past": False},
        {"hour": 14, "taken": False, "past": False},
    ]

    add_taken_slots(data["today"], [13, 14], other_venue_id=studio)
    blocked = venue_client.get(
        "/venues",
        params={"q": data["keyword"], "category": "studio", "now": "true"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["items"] == []


def test_search_sorts_and_paginates_after_filtering(venue_client, search_catalog):
    data = search_catalog
    cheap = data["create"]("저가 공간", price=5000)
    expensive = data["create"]("고가 공간", price=30000)
    default_order = venue_client.get("/venues", params={"q": data["keyword"]})
    assert default_order.status_code == 200
    assert [item["venue_id"] for item in default_order.json()["items"]] == [
        data["base_id"],
        cheap,
        expensive,
    ]
    response = venue_client.get("/venues", params={"q": data["keyword"], "sort": "price"})
    assert response.status_code == 200
    assert [item["venue_id"] for item in response.json()["items"]] == [
        cheap,
        data["base_id"],
        expensive,
    ]

    first_page = venue_client.get(
        "/venues", params={"q": data["keyword"], "page": 1, "size": 2}
    ).json()
    last_page = venue_client.get(
        "/venues", params={"q": data["keyword"], "page": 2, "size": 2}
    ).json()
    assert first_page["total"] == last_page["total"] == 3
    assert first_page["page"] == 1 and first_page["size"] == 2
    assert len(first_page["items"]) == 2
    assert last_page["items"][0]["venue_id"] == expensive
    assert last_page["items"][0]["venue_id"] not in [
        item["venue_id"] for item in first_page["items"]
    ]


def test_search_rating_sort_reads_the_venue_rating_view(
    venue_client, search_catalog, add_reservation
):
    data = search_catalog
    high_rating = data["create"]("높은 평점 공간", price=5000)
    low_rating = data["create"]("낮은 평점 공간", price=15000)
    connection = data["connection"]
    today = data["today"]
    created_at = datetime.combine(today, time(12))
    for target, ratings in [(data["base_id"], [4, 5]), (high_rating, [5]), (low_rating, [3])]:
        for rating in ratings:
            reservation_id, user_id = add_reservation()
            connection.execute(
                text("UPDATE reservations SET venue_id = :venue_id WHERE reservation_id = :id"),
                {"venue_id": target, "id": reservation_id},
            )
            connection.execute(
                text(
                    "INSERT INTO reviews (reservation_id, user_id, rating, content, created_at) "
                    "VALUES (:reservation_id, :user_id, :rating, '검색 평점 검증', :created_at)"
                ),
                {
                    "reservation_id": reservation_id,
                    "user_id": user_id,
                    "rating": rating,
                    "created_at": created_at,
                },
            )
    response = venue_client.get("/venues", params={"q": data["keyword"], "sort": "rating"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["venue_id"] for item in items] == [high_rating, data["base_id"], low_rating]
    assert [item["rating_avg"] for item in items] == [5.0, 4.5, 3.0]


def test_search_popular_sort_excludes_cancelled_past_and_old_reservations(
    venue_client, search_catalog, add_reservation
):
    data = search_catalog
    popular = data["create"]("인기 공간", price=5000)
    medium = data["create"]("중간 인기 공간", price=15000)
    connection = data["connection"]
    today = data["today"]
    now = datetime.combine(today, time(12, 30))

    def book(venue_id, *, day=today, status="confirmed", created_at=now):
        reservation_id, _ = add_reservation(day=day, status=status)
        connection.execute(
            text(
                "UPDATE reservations SET venue_id = :venue_id, created_at = :created_at "
                "WHERE reservation_id = :id"
            ),
            {"venue_id": venue_id, "created_at": created_at, "id": reservation_id},
        )

    book(popular)
    book(popular)
    book(medium)
    book(popular, status="cancelled")
    book(medium, day=today - timedelta(days=1))
    book(medium, created_at=now - timedelta(days=7, seconds=1))
    response = venue_client.get("/venues", params={"q": data["keyword"], "sort": "popular"})
    assert response.status_code == 200
    assert [item["venue_id"] for item in response.json()["items"]] == [
        popular,
        medium,
        data["base_id"],
    ]


def test_search_validates_filters_and_date_range(venue_client, search_catalog):
    data = search_catalog
    invalid_cases = [
        ({"sort": "newest"}, "sort"),
        ({"category": "unknown-type"}, "category"),
        ({"facilities": "abc"}, "facilities"),
        ({"start_hour": 10}, "hours"),
        ({"hours": 2}, "start_hour"),
        ({"start_hour": 8, "hours": 1}, None),
        ({"start_hour": 10, "hours": 5}, None),
        ({"people": 0}, "people"),
        ({"page": 0}, "page"),
        ({"size": 51}, "size"),
        ({"date": "2026-02-30"}, "date"),
    ]
    for params, field in invalid_cases:
        response = venue_client.get("/venues", params={"q": data["keyword"], **params})
        assert response.status_code == 400
        assert response.json()["code"] in {"VALIDATION", "OUT_OF_RANGE"}
        if field is not None:
            assert response.json()["detail"]["fields"][0]["field"] == field

    outside = venue_client.get("/venues", params={"q": data["keyword"], "date": "0001-01-01"})
    assert outside.status_code == 400
    assert outside.json()["code"] == "OUT_OF_RANGE"
    assert outside.json()["detail"]["reason"] == "date"


def test_search_uses_bounded_queries_for_page_items(venue_client, search_catalog):
    data = search_catalog
    data["create"]("두 번째 공간")
    statements = []

    def collect_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement.lower())

    event.listen(data["connection"], "before_cursor_execute", collect_sql)
    try:
        response = venue_client.get("/venues", params={"q": data["keyword"]})
    finally:
        event.remove(data["connection"], "before_cursor_execute", collect_sql)
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(statements) == 5
    assert "venue_facilities" in statements[2]
    assert "venue_images" in statements[3]
    assert "reservation_slots" in statements[4]


def test_new_venues_include_recent_active_rows_and_return_remaining_days(
    venue_client, search_catalog
):
    data = search_catalog
    latest = data["create"]("오늘 최신 공간")
    day_13 = data["create"]("13일 전 공간")
    day_14 = data["create"]("14일 전 공간")
    future = data["create"]("미래 등록 공간")
    inactive = data["create"]("비활성 NEW 공간")
    connection = data["connection"]
    today = data["today"]
    timestamps = {
        data["base_id"]: datetime.combine(today, time(16)),
        latest: datetime.combine(today, time(16)),
        day_13: datetime.combine(today - timedelta(days=13), time(23, 59, 59)),
        day_14: datetime.combine(today - timedelta(days=14), time(23, 59, 59)),
        future: datetime.combine(today + timedelta(days=1), time.min),
        inactive: datetime.combine(today, time(18)),
    }
    for venue_id, created_at in timestamps.items():
        connection.execute(
            text("UPDATE venues SET created_at = :created_at WHERE venue_id = :id"),
            {"id": venue_id, "created_at": created_at},
        )
    connection.execute(
        text("UPDATE venues SET is_active = FALSE WHERE venue_id = :id"), {"id": inactive}
    )

    response = venue_client.get("/venues/new")

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 10
    assert body["total"] == 3
    assert [item["venue_id"] for item in body["items"]] == [
        latest,
        data["base_id"],
        day_13,
    ]
    assert body["items"][0]["registered_on"] == today.isoformat()
    assert body["items"][0]["new_days_left"] == 14
    assert body["items"][1]["new_days_left"] == 14
    assert body["items"][2]["registered_on"] == (today - timedelta(days=13)).isoformat()
    assert body["items"][2]["new_days_left"] == 1
    assert all(item["is_new"] for item in body["items"])
    assert all(item["image"] == "art:group-0" for item in body["items"])
    assert set(body["items"][0]) == {
        "venue_id",
        "name",
        "category",
        "region",
        "capacity_max",
        "price_per_hour",
        "open_hour",
        "close_hour",
        "rating_avg",
        "review_count",
        "image",
        "facilities",
        "is_new",
        "slots",
        "registered_on",
        "new_days_left",
    }


def test_new_venues_paginate_after_filtering(venue_client, search_catalog):
    data = search_catalog
    latest = data["create"]("페이지 최신 공간")
    oldest = data["create"]("페이지 과거 공간")
    connection = data["connection"]
    connection.execute(
        text("UPDATE venues SET created_at = :created_at WHERE venue_id = :id"),
        {"id": latest, "created_at": datetime.combine(data["today"], time(18))},
    )
    connection.execute(
        text("UPDATE venues SET created_at = :created_at WHERE venue_id = :id"),
        {
            "id": oldest,
            "created_at": datetime.combine(data["today"] - timedelta(days=13), time(12)),
        },
    )
    first_page = venue_client.get("/venues/new", params={"page": 1, "size": 2}).json()
    second_page = venue_client.get("/venues/new", params={"page": 2, "size": 2}).json()

    assert first_page["total"] == second_page["total"] == 3
    assert first_page["page"] == 1 and first_page["size"] == 2
    assert second_page["page"] == 2 and second_page["size"] == 2
    assert [item["venue_id"] for item in first_page["items"]] == [latest, data["base_id"]]
    assert [item["venue_id"] for item in second_page["items"]] == [oldest]


def test_new_venues_validate_page_and_size(venue_client):
    for params, field in [({"page": 0}, "page"), ({"size": 0}, "size"), ({"size": 51}, "size")]:
        response = venue_client.get("/venues/new", params=params)
        assert response.status_code == 400
        assert response.json()["code"] == "VALIDATION"
        assert response.json()["detail"]["fields"][0]["field"] == field


def test_new_venues_use_bounded_queries_for_page_items(venue_client, search_catalog):
    data = search_catalog
    statements = []
    connection = data["connection"]

    def collect_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement.lower())

    event.listen(connection, "before_cursor_execute", collect_sql)
    try:
        response = venue_client.get("/venues/new")
    finally:
        event.remove(connection, "before_cursor_execute", collect_sql)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(statements) == 5
    assert "v_venue_rating" in statements[1]
    assert "venue_facilities" in statements[2]
    assert "venue_images" in statements[3]
    assert "reservation_slots" in statements[4]
