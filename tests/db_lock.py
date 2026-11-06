"""#78: MariaDB 연결 단위 명명 잠금으로 pytest 실행을 직렬화한다.

업무 테이블·트랜잭션·격리 수준은 바꾸지 않는다. 같은 DB를 사용하는 모든
pytest 실행이 이 잠금 규약을 사용해야 하며, suite 내부의 스레드는 제한하지 않는다.
"""

import math
import os
from collections.abc import Callable
from contextlib import suppress
from time import monotonic, sleep

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

LOCK_NAME = "spacecube_test:pytest:suite:v1"
DEFAULT_TIMEOUT = 600.0


class DatabaseTestLockError(Exception):
    """접속정보·비밀번호·SQL 인자를 포함하지 않는 검증 오류."""


def lock_timeout(value=None):
    """대기 시간은 초 단위 0~3600. 0은 기다리지 않고 한 번만 획득 시도한다."""
    if value is None:
        value = os.environ.get("TEST_DB_LOCK_TIMEOUT", str(DEFAULT_TIMEOUT))
    try:
        timeout = float(value)
        if not math.isfinite(timeout) or not 0 <= timeout <= 3600:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise DatabaseTestLockError("TEST_DB_LOCK_TIMEOUT은 0~3600초여야 합니다.") from None
    return timeout


def validate_test_database_url(raw):
    """DB 이름과 실제 접속 호스트를 확인한 다음에만 네트워크 연결을 허용한다."""
    try:
        url = make_url(raw)
        if (
            url.drivername != "mysql+pymysql"
            or url.database != "spacecube_test"
            or (url.host or "").lower() not in {"localhost", "127.0.0.1", "::1"}
            or set(url.query) - {"charset"}
        ):
            raise ValueError
    except Exception:
        raise DatabaseTestLockError(
            "CHECK_DB_URL은 로컬 MariaDB spacecube_test의 mysql+pymysql 주소여야 합니다. "
            "URL query는 charset만 허용합니다."
        ) from None
    return url


class DatabaseTestLock:
    def __init__(
        self,
        raw_url,
        *,
        timeout=DEFAULT_TIMEOUT,
        name=LOCK_NAME,
        on_wait: Callable[[], None] | None = None,
    ):
        self.url = validate_test_database_url(raw_url)
        self.timeout = lock_timeout(timeout)
        if not isinstance(name, str) or not name or len(name) > 64:
            raise DatabaseTestLockError("테스트 잠금 이름은 1~64자여야 합니다.")
        self.name = name
        self.on_wait = on_wait
        self._engine = None
        self._connection = None
        self._owner = None

    def __enter__(self):
        if self._connection is not None:
            raise DatabaseTestLockError("이미 획득한 테스트 잠금입니다.")
        try:
            self._engine = create_engine(
                self.url,
                poolclass=NullPool,
                hide_parameters=True,
                isolation_level="AUTOCOMMIT",
                connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5},
            )
            self._connection = self._engine.connect()
            deadline = monotonic() + self.timeout
            notified = False
            while True:
                acquired = self._connection.scalar(
                    text("SELECT GET_LOCK(:name, 0)"), {"name": self.name}
                )
                if acquired == 1:
                    self._owner = self._connection.scalar(text("SELECT CONNECTION_ID()"))
                    return self
                if acquired != 0:
                    raise DatabaseTestLockError("MariaDB가 테스트 실행 잠금을 획득하지 못했습니다.")
                if not notified and self.on_wait is not None:
                    self.on_wait()
                    notified = True
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise DatabaseTestLockError(
                        "테스트 DB 실행 잠금 대기 시간이 지났습니다. 다른 검증 종료 후 다시 실행하세요."
                    )
                sleep(min(0.1, remaining))
        except DatabaseTestLockError:
            self._close()
            raise
        except Exception as error:
            self._close()
            raise DatabaseTestLockError(
                f"테스트 잠금 연결·확인 실패 ({type(error).__name__}). DB 접속 설정을 확인하세요."
            ) from None
        except BaseException:
            self._close()
            raise

    def assert_held(self):
        if self._connection is None or self._owner is None:
            raise DatabaseTestLockError("테스트 실행 잠금이 없습니다.")
        try:
            owner = self._connection.scalar(text("SELECT IS_USED_LOCK(:name)"), {"name": self.name})
        except Exception as error:
            raise DatabaseTestLockError(
                f"테스트 실행 잠금 연결을 잃었습니다 ({type(error).__name__})."
            ) from None
        if owner != self._owner:
            raise DatabaseTestLockError("테스트 실행 잠금 소유권을 잃었습니다.")

    def release(self):
        if self._connection is None:
            return
        try:
            if self._owner is not None:
                released = self._connection.scalar(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": self.name}
                )
                if released != 1:
                    raise DatabaseTestLockError(
                        "테스트 실행 잠금이 이미 해제됐거나 소유권이 다릅니다."
                    )
        except DatabaseTestLockError:
            raise
        except Exception as error:
            raise DatabaseTestLockError(
                f"테스트 실행 잠금 해제 실패 ({type(error).__name__})."
            ) from None
        finally:
            self._close()

    def _close(self):
        if self._connection is not None:
            with suppress(Exception):
                self._connection.close()
        if self._engine is not None:
            with suppress(Exception):
                self._engine.dispose()
        self._connection = self._engine = self._owner = None

    def __exit__(self, error_type, error, traceback):
        try:
            self.release()
        except DatabaseTestLockError:
            if error_type is None:
                raise
