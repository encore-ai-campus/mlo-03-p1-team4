"""#78: 로컬 테스트 DB를 공유하는 pytest 실행끼리 직렬화한다."""

import os

import pytest

from tests.db_lock import DatabaseTestLock, DatabaseTestLockError, lock_timeout


@pytest.fixture(scope="session", autouse=True)
def shared_test_database_lock(request):
    """업무 fixture보다 먼저 획득하고 pytest 실행이 끝날 때 해제한다."""
    raw = os.environ.get("CHECK_DB_URL")
    if not raw:
        # DB가 필요 없는 단위 테스트는 연결 설정 없이도 실행할 수 있다.
        yield None
        return

    reporter = request.config.pluginmanager.getplugin("terminalreporter")

    def waiting():
        if reporter is not None:
            reporter.write_line(
                "spacecube_test를 다른 pytest가 사용 중입니다. 실행 잠금을 기다립니다."
            )

    try:
        with DatabaseTestLock(raw, timeout=lock_timeout(), on_wait=waiting) as lock:
            yield lock
    except DatabaseTestLockError as error:
        pytest.exit(f"테스트 DB 실행 잠금: {error}", returncode=2)


@pytest.fixture(autouse=True)
def require_test_database_lock(shared_test_database_lock):
    """잠금 연결을 잃었다면 다음 테스트의 DB 변경 전에 검증을 중단한다."""
    if shared_test_database_lock is not None:
        try:
            shared_test_database_lock.assert_held()
        except DatabaseTestLockError as error:
            pytest.exit(f"테스트 DB 실행 잠금: {error}", returncode=2)
