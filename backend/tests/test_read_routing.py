"""공개 조회의 실제 읽기 연결·primary 대체를 DB 한 대에서 검증한다."""

import os
import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core import db as database
from app.core.config import Settings
from app.core.metrics import db_read_fallback_counter
from app.main import app
from app.services import catalog_service


def fallback_count() -> float:
    """Counter의 공개 수집 결과에서 누적 대체 횟수를 읽는다."""
    return next(
        sample.value
        for metric in db_read_fallback_counter.collect()
        for sample in metric.samples
        if sample.name == "db_read_fallback_total"
    )


@pytest.mark.parametrize("read_mode", ["unset", "same_database", "unreachable"])
def test_real_read_dependency_uses_primary_when_read_connection_fails(monkeypatch, read_mode):
    """읽기 의존성을 대체하지 않고 실제 연결 실패·200 응답·대체 지표를 함께 확인한다."""
    raw_url = os.environ.get("CHECK_DB_URL")
    if not raw_url:
        pytest.fail("CHECK_DB_URL에 로컬 MariaDB spacecube_test 접속 정보를 지정해 주세요.")
    url = make_url(raw_url)
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("읽기 경로 시험은 로컬 MariaDB spacecube_test에서만 실행합니다.")

    # 수신하지 않는 loopback 포트를 예약해 다른 프로그램에 장애를 주지 않고 연결을 거부한다.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        read_url = None
        if read_mode == "same_database":
            read_url = raw_url
        elif read_mode == "unreachable":
            read_url = url.set(
                host="127.0.0.1", port=unavailable.getsockname()[1]
            ).render_as_string(hide_password=False)
        settings = Settings(_env_file=None, db_write_url=raw_url, db_read_url=read_url)
        monkeypatch.setattr(database, "get_settings", lambda: settings)
        # 현재 프로세스의 기존 풀을 닫거나 운영 설정을 변경하지 않도록 시험용 풀만 분리한다.
        monkeypatch.setattr(database, "_engines", {})
        monkeypatch.setattr(database, "_factories", {})
        monkeypatch.setattr(catalog_service, "_categories_cache", None)
        monkeypatch.setattr(catalog_service, "_cache_expires_at", 0.0)
        overrides = app.dependency_overrides.copy()
        app.dependency_overrides.pop(database.get_db_read, None)
        client = TestClient(app)
        try:
            with database.get_engine("write").connect() as connection:
                assert connection.scalar(text("SELECT DATABASE()")) == "spacecube_test"
                assert "MariaDB" in connection.scalar(text("SELECT VERSION()"))
                expected = [
                    dict(row)
                    for row in connection.execute(
                        text("SELECT code, name FROM categories ORDER BY category_id")
                    ).mappings()
                ]
            assert expected, "기존 seed.sql 적용이 필요합니다."
            before = fallback_count()

            response = client.get("/categories")

            assert response.status_code == 200
            assert response.json() == expected
            assert fallback_count() - before == (1 if read_mode == "unreachable" else 0)
        finally:
            client.close()
            database.close_databases()
            app.dependency_overrides.clear()
            app.dependency_overrides.update(overrides)
