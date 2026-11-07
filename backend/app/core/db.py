"""F-64: 제한된 primary·replica 풀과 요청 단위 세션.

사용: A·B 라우터와 인증 의존성이 primary 또는 replica 세션을 받는다.
"""

import logging
from collections.abc import Generator
from threading import RLock
from typing import Literal

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.errors import fail
from app.core.metrics import db_read_fallback_counter

DatabaseRole = Literal["write", "read"]
_engines: dict[DatabaseRole, Engine] = {}
_factories: dict[DatabaseRole, sessionmaker[Session]] = {}
_engine_lock = RLock()


def _make_engine(url: str, *, health: bool = False) -> Engine:
    options = (
        {"poolclass": NullPool}
        if health
        else {
            "pool_size": 5,
            "max_overflow": 5,
            "pool_timeout": 3,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        }
    )
    timeout = 0.5 if health else 5
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={
            "connect_timeout": timeout,
            "read_timeout": timeout,
            "write_timeout": timeout,
            "init_command": (
                "SET SESSION sql_mode = "
                "'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,"
                "NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'"
            ),
        },
        **options,
    )

    @event.listens_for(engine, "connect")
    def set_timezone(connection, record):
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+09:00'")

    return engine


def _effective_role(role: DatabaseRole) -> DatabaseRole:
    if role == "read" and get_settings().db_read_url is None:
        return "write"
    return role


def get_engine(role: DatabaseRole = "write") -> Engine:
    role = _effective_role(role)
    with _engine_lock:
        if role not in _engines:
            settings = get_settings()
            value = settings.db_read_url if role == "read" else settings.db_write_url
            if value is None:
                raise fail("SERVICE_UNAVAILABLE", 503)
            # lru_cache만으로는 첫 동시 호출 때 중복 생성을 막을 수 없다.
            _engines[role] = _make_engine(value.get_secret_value())
        return _engines[role]


def _new_session(role: DatabaseRole) -> Session:
    role = _effective_role(role)
    with _engine_lock:
        if role not in _factories:
            _factories[role] = sessionmaker(bind=get_engine(role), expire_on_commit=False)
        return _factories[role]()


def new_write_session() -> Session:
    return _new_session("write")


def get_db_write() -> Generator[Session, None, None]:
    """쓰기·인증·내 정보 라우터에 primary 세션을 제공하고 종료 시 닫는다."""
    with new_write_session() as session:
        yield session
    # close()는 서비스에서 커밋하지 않은 읽기 트랜잭션도 정리한다.


def get_db_read() -> Generator[Session, None, None]:
    """공개 조회에 replica를 제공하고 최초 연결 실패 시 primary로 대체한다."""
    if get_settings().db_read_url is None:
        yield from get_db_write()
        return

    session = _new_session("read")
    try:
        session.execute(text("SELECT 1"))
    except (OperationalError, PoolTimeoutError):
        session.close()
        db_read_fallback_counter.inc()
        logging.getLogger("spacecube.app").warning("replica 연결 실패, primary 사용")
        yield from get_db_write()
        return
    except BaseException:
        session.close()
        raise

    try:
        yield session
    finally:
        session.close()
    # 세션을 넘긴 뒤 실패한 SQL과 커밋 결과가 불명확한 쓰기는 자동 재실행하지 않는다.


def check_database(role: DatabaseRole) -> bool:
    settings = get_settings()
    value = settings.db_read_url if role == "read" else settings.db_write_url
    if role == "read" and value is None:
        return True
    if value is None:
        return False

    engine = None
    try:
        # 업무용 풀 고갈과 헬스 확인을 분리한다. HTTP 마감은 health_service가 제한한다.
        engine = _make_engine(value.get_secret_value(), health=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        if engine is not None:
            engine.dispose()


def close_databases() -> None:
    with _engine_lock:
        engines = list(_engines.values())
        _engines.clear()
        _factories.clear()
    # 종료할 때 사용하지 않았던 엔진을 새로 만들지 않는다.
    for engine in engines:
        engine.dispose()
