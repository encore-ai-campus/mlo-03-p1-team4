"""F-03: 내 정보 조회·수정과 비밀번호 변경 API."""

import os
from datetime import datetime, time, timedelta
from uuid import uuid4

import bcrypt
import pytest
from sqlalchemy import text

from app.core.clock import get_today
from app.repositories import reservation_repo


def signup(client, member):
    return client.post(
        "/auth/signup",
        json=member,
        headers={"X-Synthetic": "1", "X-Synthetic-Key": os.environ["SYNTHETIC_API_KEY"]},
    )


def login(client, member, password=None):
    response = client.post(
        "/auth/login",
        json={"email": member["email"], "password": password or member["password"]},
    )
    if response.status_code == 200:
        client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return response


def create_reservation(db, user_id, reserve_date, *, status="confirmed", start_hour=9):
    category_id = db.scalar(text("SELECT MIN(category_id) FROM categories"))
    region_id = db.scalar(text("SELECT MIN(region_id) FROM regions"))
    assert category_id is not None and region_id is not None, "spacecube_test seed가 필요합니다."

    venue_id = db.execute(
        text(
            "INSERT INTO venues "
            "(region_id,category_id,name,capacity_max,price_per_hour,source_site,source_id) "
            "VALUES (:region,:category,'탈퇴 테스트 공간',4,10000,'synthetic',:source_id)"
        ),
        {
            "region": region_id,
            "category": category_id,
            "source_id": f"withdraw-{uuid4().hex}",
        },
    ).lastrowid
    return db.execute(
        text(
            "INSERT INTO reservations "
            "(user_id,venue_id,reserve_date,start_hour,end_hour,headcount,total_price,status,is_synthetic) "
            "VALUES (:user,:venue,:reserve_date,:start_hour,:end_hour,1,10000,:status,TRUE)"
        ),
        {
            "user": user_id,
            "venue": venue_id,
            "reserve_date": reserve_date,
            "start_hour": start_hour,
            "end_hour": start_hour + 1,
            "status": status,
        },
    ).lastrowid


def test_get_me_requires_auth_and_returns_only_documented_fields(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert http.get("/users/me").status_code == 401
    assert login(http, member).status_code == 200

    response = http.get("/users/me")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "user_id",
        "email",
        "name",
        "phone",
        "birth",
        "gender_digit",
        "marketing_agreed",
        "terms_agreed_at",
        "privacy_agreed_at",
        "created_at",
    }
    assert body["email"] == member["email"]
    assert "password_hash" not in body
    for field in ("terms_agreed_at", "privacy_agreed_at", "created_at"):
        assert body[field].endswith("+09:00")


def test_update_me_changes_profile_fields(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200

    response = http.patch(
        "/users/me",
        json={"name": "  변경한 이름  ", "phone": "010-1111-2222", "marketing_agreed": True},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "변경한 이름"
    assert response.json()["phone"] == "010-1111-2222"
    assert response.json()["marketing_agreed"] is True
    assert http.get("/users/me").json()["name"] == "변경한 이름"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "  "},
        {"name": None},
        {"phone": "012-1234-5678"},
        {"marketing_agreed": "true"},
        {"user_id": 99},
    ],
)
def test_update_me_rejects_invalid_or_unsupported_fields(client, member, body):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200

    response = http.patch("/users/me", json=body)
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    current = http.get("/users/me").json()
    assert current["name"] == member["name"]
    assert current["marketing_agreed"] is member["marketing_agreed"]


def test_member_profile_and_password_routes_require_auth(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert http.get("/users/me").status_code == 401
    assert http.patch("/users/me", json={"name": "새 이름"}).status_code == 401
    assert http.delete("/users/me").status_code == 401
    assert (
        http.patch(
            "/users/me/password",
            json={"current_password": member["password"], "new_password": "NewPassword123!"},
        ).status_code
        == 401
    )


def test_password_change_wrong_current_password_keeps_original_hash(client, member):
    http, db = client
    user_id = signup(http, member).json()["user_id"]
    assert login(http, member).status_code == 200
    original_hash = db.scalar(
        text("SELECT password_hash FROM users WHERE user_id = :id"), {"id": user_id}
    )

    response = http.patch(
        "/users/me/password",
        json={"current_password": "WrongPassword123!", "new_password": "NewPassword123!"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "code": "WRONG_PASSWORD",
        "message": "현재 비밀번호가 맞지 않아요.",
        "detail": None,
    }
    assert (
        db.scalar(text("SELECT password_hash FROM users WHERE user_id = :id"), {"id": user_id})
        == original_hash
    )
    assert login(http, member).status_code == 200


@pytest.mark.parametrize("new_password", ["short", "가" * 25])
def test_password_change_rejects_password_outside_byte_limits(client, member, new_password):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200

    response = http.patch(
        "/users/me/password",
        json={"current_password": member["password"], "new_password": new_password},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"]["fields"][0]["field"] == "new_password"


def test_password_change_stores_hash_and_changes_login_password(client, member):
    http, db = client
    user_id = signup(http, member).json()["user_id"]
    assert login(http, member).status_code == 200
    new_password = "NewPassword123!"  # noqa: S105 -- 테스트용 비밀번호

    response = http.patch(
        "/users/me/password",
        json={"current_password": member["password"], "new_password": new_password},
    )
    assert response.status_code == 204
    assert response.content == b""
    password_hash = db.scalar(
        text("SELECT password_hash FROM users WHERE user_id = :id"), {"id": user_id}
    )
    assert password_hash != member["password"]
    assert bcrypt.checkpw(new_password.encode(), password_hash.encode())
    # 기존 액세스 토큰은 만료 전까지 유효하다. 다음 로그인부터 새 비밀번호가 필요하다.
    assert http.get("/users/me").status_code == 200
    old_login = login(http, member)
    assert old_login.status_code == 401
    assert old_login.json()["code"] == "INVALID_CREDENTIALS"
    assert login(http, member, new_password).status_code == 200


def test_withdraw_is_blocked_by_cancellable_reservations(client, member, monkeypatch):
    http, db = client
    user_id = signup(http, member).json()["user_id"]
    assert login(http, member).status_code == 200
    fixed_now = datetime.combine(get_today(), time(12))
    monkeypatch.setattr(reservation_repo, "get_now", lambda: fixed_now)
    create_reservation(db, user_id, fixed_now.date() + timedelta(days=1))
    create_reservation(db, user_id, fixed_now.date() + timedelta(days=2))

    response = http.delete("/users/me")

    assert response.status_code == 409
    assert response.json() == {
        "code": "HAS_UPCOMING_RESERVATION",
        "message": "이용 예정 예약이 있어요. 예약 내역에서 먼저 취소해 주세요.",
        "detail": {"count": 2},
    }
    assert http.get("/users/me").status_code == 200
    row = db.execute(
        text("SELECT email, phone, deleted_at FROM users WHERE user_id = :id"), {"id": user_id}
    ).one()
    assert row.email == member["email"]
    assert row.phone == member["phone"]
    assert row.deleted_at is None
    assert (
        db.scalar(text("SELECT COUNT(*) FROM reservations WHERE user_id = :id"), {"id": user_id})
        == 2
    )


def test_withdraw_anonymizes_when_no_cancellable_reservations(client, member, monkeypatch):
    http, db = client
    user_id = signup(http, member).json()["user_id"]
    assert login(http, member).status_code == 200
    old_token = http.headers["Authorization"]
    old_hash = db.scalar(
        text("SELECT password_hash FROM users WHERE user_id = :id"), {"id": user_id}
    )
    fixed_now = datetime.combine(get_today(), time(12))
    today = fixed_now.date()
    monkeypatch.setattr(reservation_repo, "get_now", lambda: fixed_now)

    # 시작 정각·이미 시작한 예약·완료·취소 예약은 탈퇴를 막지 않는다.
    create_reservation(db, user_id, today, status="confirmed", start_hour=12)
    create_reservation(db, user_id, today, status="confirmed", start_hour=11)
    create_reservation(db, user_id, today + timedelta(days=1), status="completed")
    create_reservation(db, user_id, today + timedelta(days=2), status="cancelled")

    response = http.delete("/users/me")

    assert response.status_code == 204
    assert response.content == b""
    row = db.execute(
        text(
            "SELECT email,name,phone,birth,password_hash,marketing_agreed,deleted_at "
            "FROM users WHERE user_id = :id"
        ),
        {"id": user_id},
    ).one()
    assert row.email == f"deleted+{user_id}@invalid"
    assert row.name == "탈퇴회원"
    assert row.phone is None
    assert row.birth == "000000"
    assert row.password_hash != old_hash
    assert not bcrypt.checkpw(member["password"].encode(), row.password_hash.encode())
    assert not row.marketing_agreed
    assert row.deleted_at is not None
    assert (
        db.scalar(text("SELECT COUNT(*) FROM reservations WHERE user_id = :id"), {"id": user_id})
        == 4
    )
    assert http.headers["Authorization"] == old_token
    assert http.get("/users/me").status_code == 401

    # 탈퇴 과정에서 이메일을 비워 같은 주소로 다시 가입할 수 있다.
    replacement = signup(http, member)
    assert replacement.status_code == 201
    assert replacement.json()["user_id"] != user_id
