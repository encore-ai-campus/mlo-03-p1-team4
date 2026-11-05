"""F-01~04: 로컬 MariaDB에서 회원 API와 실제 인증 흐름을 검사한다."""

import os
import secrets
from uuid import uuid4

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import get_db_write
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path):
    """로컬 테스트 DB만 연결하고 테스트 뒤 외부 트랜잭션을 되돌린다."""
    raw = os.environ.get("CHECK_DB_URL")
    if not raw:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 주소를 지정하세요.")
    try:
        url = make_url(raw)
    except Exception:
        pytest.fail("CHECK_DB_URL 형식을 확인하세요.", pytrace=False)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("회원 테스트는 로컬 MariaDB spacecube_test에서만 실행합니다.")

    monkeypatch.setenv("DB_WRITE_URL", raw)
    monkeypatch.setenv("DB_READ_URL", raw)
    monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:1")
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("SYNTHETIC_API_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("CORS_ORIGINS", "https://testserver")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    get_settings.cache_clear()
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT DATABASE()")) != "spacecube_test":
                pytest.fail("연결된 DB 이름이 spacecube_test가 아닙니다.")
            if "MariaDB" not in connection.scalar(text("SELECT VERSION()")):
                pytest.fail("MariaDB 테스트 DB가 필요합니다.")
            connection.execute(text("SET time_zone = '+09:00'"))
            connection.commit()
            transaction = connection.begin()
            app = create_app()

            def test_db():
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    yield db

            app.dependency_overrides[get_db_write] = test_db
            try:
                with TestClient(
                    app, base_url="https://testserver", headers={"Origin": "https://testserver"}
                ) as test_client:
                    yield test_client, connection
            finally:
                app.dependency_overrides.clear()
                transaction.rollback()
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def member():
    return {
        "email": f"{uuid4().hex}@example.invalid",
        "password": "TestPassword123!",
        "name": "테스트 회원",
        "phone": "01000010001",
        "birth": "000101",
        "gender_digit": "3",
        "marketing_agreed": False,
        "terms_agreed": True,
        "privacy_agreed": True,
    }


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


def test_signup_stores_hash_and_checks_duplicate_email(client, member):
    http, db = client
    result = signup(http, member)
    assert result.status_code == 201
    row = db.execute(
        text("SELECT password_hash, is_synthetic FROM users WHERE user_id = :id"),
        {"id": result.json()["user_id"]},
    ).one()
    assert row.password_hash != member["password"]
    assert bcrypt.checkpw(member["password"].encode(), row.password_hash.encode())
    assert row.is_synthetic == 1
    duplicate = signup(http, member)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "EMAIL_TAKEN"


@pytest.mark.parametrize("supplied_key", [None, "wrong-key"])
def test_signup_rejects_synthetic_header_without_valid_key(client, member, supplied_key):
    http, db = client
    headers = {"X-Synthetic": "1"}
    if supplied_key is not None:
        headers["X-Synthetic-Key"] = supplied_key
    response = http.post("/auth/signup", json=member, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert (
        db.scalar(
            text("SELECT COUNT(*) FROM users WHERE email = :email"), {"email": member["email"]}
        )
        == 0
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("birth", "538991"),
        ("birth", "990230"),
        ("terms_agreed", False),
        ("terms_agreed", "true"),
        ("privacy_agreed", False),
        ("password", "short"),
        ("email", "not-an-email"),
        ("phone", ""),
        ("phone", None),
    ],
)
def test_signup_rejects_invalid_input(client, member, field, value):
    http, _ = client
    member[field] = value
    result = signup(http, member)
    assert result.status_code == 400
    assert result.json()["code"] == "VALIDATION"


def test_email_availability(client, member):
    http, _ = client
    assert http.get("/auth/email-check", params={"email": member["email"]}).json() == {
        "available": True
    }
    assert signup(http, member).status_code == 201
    assert http.get("/auth/email-check", params={"email": member["email"]}).json() == {
        "available": False
    }


def test_login_me_and_logout(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    response = login(http, member)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"  # noqa: S105 -- OAuth 인증 방식 확인
    assert response.json()["access_token"]
    assert "set-cookie" not in response.headers
    me = http.get("/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == member["email"]
    assert "password_hash" not in me.json()
    logout_response = http.post("/auth/logout")
    assert logout_response.status_code == 204
    assert logout_response.content == b""
    assert "set-cookie" not in logout_response.headers
    # Bearer JWT는 서버에서 폐기하지 않으므로 클라이언트가 보관한 토큰을 직접 삭제한다.
    assert http.get("/users/me").status_code == 200
    http.headers.pop("Authorization", None)
    assert http.get("/users/me").status_code == 401


def test_logout_requires_a_valid_bearer_token(client):
    http, _ = client
    assert http.post("/auth/logout").status_code == 401


def test_swagger_declares_bearer_auth_for_member_routes(client):
    http, _ = client
    spec = http.get("/openapi.json").json()
    scheme = spec["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert scheme["bearerFormat"] == "JWT"
    assert "access_token" in scheme["description"]
    assert spec["paths"]["/users/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert spec["paths"]["/auth/logout"]["post"]["security"] == [{"HTTPBearer": []}]


def test_bad_password_and_unauthenticated_access(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    result = login(http, member, "WrongPassword123!")
    assert result.status_code == 401
    assert result.json()["code"] == "INVALID_CREDENTIALS"
    assert http.get("/users/me").status_code == 401


def test_current_user_rejects_deleted_account_even_with_valid_token(client, member):
    http, db = client
    user_id = signup(http, member).json()["user_id"]
    assert login(http, member).status_code == 200
    db.execute(
        text("UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE user_id = :id"), {"id": user_id}
    )
    response = http.get("/users/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_synthetic_key_is_allowed_in_cors_preflight(client):
    http, _ = client
    response = http.options(
        "/auth/signup",
        headers={
            "Origin": "https://testserver",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Synthetic,X-Synthetic-Key",
        },
    )
    assert response.status_code == 200
    assert "x-synthetic-key" in response.headers["access-control-allow-headers"].lower()


def test_missing_user_gets_same_login_error(client, member):
    http, _ = client
    result = login(http, member)
    assert result.status_code == 401
    assert result.json()["code"] == "INVALID_CREDENTIALS"


def test_login_returns_bearer_token_without_cookie(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    response = http.post(
        "/auth/login",
        json={"email": member["email"], "password": member["password"]},
        headers={"Origin": "https://untrusted.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"  # noqa: S105 -- OAuth 인증 방식 확인
    assert "set-cookie" not in response.headers
    assert http.get("/users/me").status_code == 401


def test_update_profile(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200
    result = http.patch("/users/me", json={"name": "변경한 이름", "marketing_agreed": True})
    assert result.status_code == 200
    assert result.json()["name"] == "변경한 이름"
    assert http.get("/users/me").json()["marketing_agreed"] is True


@pytest.mark.parametrize(
    "body", [{}, {"name": "  "}, {"user_id": 99}, {"marketing_agreed": "true"}]
)
def test_update_profile_rejects_invalid_fields(client, member, body):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200
    response = http.patch("/users/me", json=body)
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert http.get("/users/me").json()["name"] == member["name"]


def test_profile_write_rejects_invalid_bearer_token(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200
    response = http.patch(
        "/users/me", json={"name": "변경 시도"}, headers={"Authorization": "Bearer invalid"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
    assert http.get("/users/me").json()["name"] == member["name"]


def test_change_password(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200
    wrong = http.patch(
        "/users/me/password",
        json={"current_password": "WrongPassword123!", "new_password": "NewPassword123!"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "WRONG_PASSWORD"
    changed = http.patch(
        "/users/me/password",
        json={"current_password": member["password"], "new_password": "NewPassword123!"},
    )
    assert changed.status_code == 204
    http.headers.pop("Authorization")
    assert login(http, member).status_code == 401
    assert login(http, member, "NewPassword123!").status_code == 200


def test_withdraw_is_unavailable_until_reservation_integration(client, member):
    http, _ = client
    assert signup(http, member).status_code == 201
    assert login(http, member).status_code == 200
    result = http.delete("/users/me")
    assert result.status_code == 503
    assert result.json()["code"] == "SERVICE_UNAVAILABLE"
    assert http.get("/users/me").status_code == 200
