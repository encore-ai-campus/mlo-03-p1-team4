"""이슈 #1: B가 사용하는 공통 인터페이스와 연결 설정 검증."""

from datetime import date, datetime
from inspect import signature
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from app.core import clock, db, events, synthetic
from app.core.deps import CurrentUser, get_current_user, get_session_id
from app.core.errors import AppError
from app.core.metrics import reservation_counter
from app.core.pagination import paginate


def request_with(headers):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        }
    )


@pytest.mark.parametrize("health", [False, True])
def test_db_new_connection_sets_strict_mode_and_korean_timezone(monkeypatch, health):
    engine = MagicMock()
    create = MagicMock(return_value=engine)
    callbacks = []
    monkeypatch.setattr(db, "create_engine", create)
    monkeypatch.setattr(db.event, "listens_for", lambda *_: lambda fn: callbacks.append(fn) or fn)
    assert db._make_engine("mysql+pymysql://example@localhost/test", health=health) is engine
    args = create.call_args.kwargs["connect_args"]
    assert args["init_command"] == (
        "SET SESSION sql_mode = "
        "'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,"
        "NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'"
    )
    connection = MagicMock()
    callbacks[0](connection, None)
    connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SET time_zone = '+09:00'"
    )


def test_public_contract_shapes():
    assert list(signature(events.log_event).parameters) == [
        "session_id",
        "user_id",
        "event_type",
        "venue_id",
        "category",
        "payload",
        "is_synthetic",
    ]
    assert CurrentUser(user_id=7).user_id == 7
    assert paginate(["a"], 1, 20, 1) == {"items": ["a"], "page": 1, "size": 20, "total": 1}
    session = "4b1c0000-0000-4000-8000-000000000001"
    assert get_session_id(request_with({"X-Session-Id": session})) == session
    assert get_session_id(request_with({"X-Session-Id": "invalid"})) is None
    assert callable(get_current_user)
    assert callable(db.get_db_read) and callable(db.get_db_write)
    assert reservation_counter is not None
    assert isinstance(clock.get_today(), date)
    assert isinstance(clock.get_now(), datetime)
    assert clock.get_now().tzinfo is None
    error = AppError("UNAUTHORIZED", "로그인이 필요해요.", 401)
    assert (error.code, error.message, error.status, error.detail) == (
        "UNAUTHORIZED",
        "로그인이 필요해요.",
        401,
        None,
    )


def test_public_read_uses_primary_if_replica_connection_fails(monkeypatch):
    replica = MagicMock()
    replica.execute.side_effect = OperationalError("SELECT 1", {}, Exception("unavailable"))
    primary = object()
    monkeypatch.setattr(
        db, "get_settings", lambda: SimpleNamespace(db_read_url=SecretStr("configured"))
    )
    monkeypatch.setattr(db, "_new_session", lambda _role: replica)
    monkeypatch.setattr(db, "get_db_write", lambda: iter([primary]))
    assert list(db.get_db_read()) == [primary]
    replica.close.assert_called_once()


def test_synthetic_key_is_required_when_header_is_present(monkeypatch):
    monkeypatch.setattr(
        synthetic,
        "get_settings",
        lambda: SimpleNamespace(synthetic_api_key=SecretStr("local-test-key")),
    )
    assert synthetic.is_synthetic_request(request_with({})) is False
    assert (
        synthetic.is_synthetic_request(
            request_with(
                {
                    "X-Synthetic": "1",
                    "X-Synthetic-Key": "local-test-key",
                }
            )
        )
        is True
    )
    assert (
        synthetic.is_synthetic_request(
            request_with(
                {
                    "X-Synthetic": "0",
                    "X-Synthetic-Key": "local-test-key",
                }
            )
        )
        is False
    )
    for headers in ({"X-Synthetic": "1"}, {"X-Synthetic": "1", "X-Synthetic-Key": "wrong"}):
        with pytest.raises(AppError) as error:
            synthetic.is_synthetic_request(request_with(headers))
        assert error.value.status == 401
        assert error.value.code == "UNAUTHORIZED"


@pytest.mark.parametrize("configured", [None, SecretStr("")])
def test_synthetic_rejects_missing_or_empty_server_key(monkeypatch, configured):
    monkeypatch.setattr(
        synthetic, "get_settings", lambda: SimpleNamespace(synthetic_api_key=configured)
    )
    assert synthetic.is_synthetic_request(request_with({})) is False
    with pytest.raises(AppError) as error:
        synthetic.is_synthetic_request(
            request_with(
                {
                    "X-Synthetic": "1",
                    "X-Synthetic-Key": "key",
                }
            )
        )
    assert (error.value.status, error.value.code) == (401, "UNAUTHORIZED")
