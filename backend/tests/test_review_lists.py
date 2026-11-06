"""F-51 후기 목록 API와 B 조회식을 로컬 MariaDB에서 함께 검증한다."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_reservation_dependencies import NOW

from app.core.db import get_db_read, get_db_write
from app.core.deps import CurrentUser, get_current_user
from app.main import app

pytest_plugins = ("test_reservation_dependencies",)


@pytest.fixture
def review_client(connection, sample):
    """가상 후기만 삽입하고 기존 외부 트랜잭션을 통해 테스트 뒤 롤백한다."""
    user_id, venue_id, create_reservation = sample
    ids = []
    for rating in (5, 2, 3):
        reservation_id = create_reservation()
        review_id = connection.execute(
            text(
                "INSERT INTO reviews (reservation_id,user_id,rating,content,created_at,deleted_at) "
                "VALUES (:reservation,:user,:rating,:content,:created,:deleted)"
            ),
            {
                "reservation": reservation_id,
                "user": user_id,
                "rating": rating,
                "content": f"테스트 후기 {rating}",
                "created": NOW + timedelta(minutes=rating),
                "deleted": NOW if rating == 3 else None,
            },
        ).lastrowid
        ids.append(review_id)

    category = connection.scalar(
        text(
            "SELECT c.code FROM categories c JOIN venues v ON v.category_id=c.category_id "
            "WHERE v.venue_id=:id"
        ),
        {"id": venue_id},
    )

    def test_db():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db

    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_write] = test_db
    app.dependency_overrides[get_db_read] = test_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id)
    try:
        with TestClient(app) as client:
            yield client, user_id, venue_id, category, ids
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


def test_venue_and_my_review_lists_hide_deleted_and_mask_author(review_client):
    client, _, venue_id, category, ids = review_client
    for path in (f"/venues/{venue_id}/reviews", "/users/me/reviews"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 2
        assert [item["review_id"] for item in data["items"]] == ids[:2]
        assert all(item["author"] == "검**" for item in data["items"])
        assert all(item["category"] == category for item in data["items"])
        assert all(item["venue_id"] == venue_id for item in data["items"])
        assert all(item["created_at"].endswith("+09:00") for item in data["items"])


def test_public_category_sort_and_pagination(review_client):
    client, _, _, category, _ = review_client
    first = client.get("/reviews", params={"category": category, "sort": "high", "size": 1})
    second = client.get(
        "/reviews", params={"category": category, "sort": "high", "size": 1, "page": 2}
    )
    assert first.status_code == second.status_code == 200
    page1, page2 = first.json(), second.json()
    assert page1["total"] == page2["total"] >= 2
    assert page1["items"][0]["category"] == page2["items"][0]["category"] == category
    assert page1["items"][0]["rating"] >= page2["items"][0]["rating"]
    assert page1["items"][0]["review_id"] != page2["items"][0]["review_id"]


def test_update_and_delete_review_reflected_in_my_list(review_client):
    client, _, _, _, ids = review_client
    response = client.patch(f"/reviews/{ids[0]}", json={"rating": 4, "content": "수정한 후기"})
    assert response.status_code == 200, response.text
    items = client.get("/users/me/reviews").json()["items"]
    item = next(item for item in items if item["review_id"] == ids[0])
    assert (item["rating"], item["content"]) == (4, "수정한 후기")

    assert client.delete(f"/reviews/{ids[0]}").status_code == 204
    assert client.get("/users/me/reviews").json()["total"] == 1
    missing = client.patch(f"/reviews/{ids[0]}", json={"rating": 3})
    assert (missing.status_code, missing.json()["code"]) == (404, "REVIEW_NOT_FOUND")


def test_withdrawal_preserves_reservations_and_anonymizes_review_author(connection, review_client):
    client, user_id, venue_id, _, ids = review_client

    response = client.delete("/users/me")

    assert response.status_code == 204, response.text
    assert (
        connection.scalar(
            text("SELECT deleted_at IS NOT NULL FROM users WHERE user_id=:id"), {"id": user_id}
        )
        == 1
    )
    # 탈퇴는 이용 기록을 지우거나 예약 상태를 비활성화하지 않는다.
    assert connection.scalar(
        text("SELECT COUNT(*) FROM reservations WHERE user_id=:id AND status='completed'"),
        {"id": user_id},
    ) == len(ids)
    assert connection.scalar(
        text("SELECT COUNT(*) FROM reviews WHERE user_id=:id"), {"id": user_id}
    ) == len(ids)

    response = client.get(f"/venues/{venue_id}/reviews")
    assert response.status_code == 200
    assert all(item["author"] == "탈퇴한 회원" for item in response.json()["items"])


def test_inactive_venue_hides_public_reviews_but_keeps_my_reviews(connection, review_client):
    client, _, venue_id, _, ids = review_client
    connection.execute(
        text("UPDATE venues SET is_active=FALSE WHERE venue_id=:id"), {"id": venue_id}
    )
    assert client.get(f"/venues/{venue_id}/reviews").json()["total"] == 0
    mine = client.get("/users/me/reviews")
    assert mine.status_code == 200
    assert {item["review_id"] for item in mine.json()["items"]} == set(ids[:2])
