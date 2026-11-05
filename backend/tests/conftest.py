"""A 회원 API 테스트에서 공유하는 로컬 MariaDB fixture."""

import os
import secrets
from uuid import uuid4

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
    """로컬 테스트 DB만 연결하고 테스트별 외부 트랜잭션을 롤백한다."""
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
