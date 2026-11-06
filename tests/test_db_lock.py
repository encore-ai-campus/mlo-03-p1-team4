"""공유 테스트 DB 실행 잠금의 범위·비밀값 보호·프로세스 수명 검증."""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from threading import Thread
from time import monotonic
from unittest.mock import Mock
from uuid import uuid4

import pytest

from tests import db_lock
from tests.db_lock import DatabaseTestLock, DatabaseTestLockError, lock_timeout

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "raw",
    [
        "not-a-url",
        "mysql://unit:do-not-log@localhost/spacecube_test",
        "mysql+pymysql://unit:do-not-log@192.0.2.1/spacecube_test",
        "mysql+pymysql://unit:do-not-log@localhost/spacecube",
        "mysql+pymysql://unit:do-not-log@localhost/spacecube_test?host=192.0.2.1",
        "mysql+pymysql://unit:do-not-log@localhost/spacecube_test?db=spacecube",
        "mysql+pymysql://unit:do-not-log@localhost/spacecube_test?unix_socket=/tmp/socket",
        "mysql+pymysql://unit:do-not-log@localhost/spacecube_test?read_default_file=local.ini",
    ],
)
def test_invalid_target_is_rejected_before_connecting(monkeypatch, raw):
    create = Mock(side_effect=AssertionError("잘못된 주소로 연결하면 안 됨"))
    monkeypatch.setattr(db_lock, "create_engine", create)
    with pytest.raises(DatabaseTestLockError) as captured:
        DatabaseTestLock(raw)
    assert "do-not-log" not in str(captured.value)
    create.assert_not_called()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]", "LOCALHOST"])
def test_local_host_aliases_use_same_database_lock(host):
    lock = DatabaseTestLock(f"mysql+pymysql://unit@{host}/spacecube_test?charset=utf8mb4")
    assert lock.name == db_lock.LOCK_NAME


@pytest.mark.parametrize("value", ["invalid", "nan", "inf", -1, 3601, object()])
def test_timeout_is_bounded_and_does_not_echo_input(value):
    with pytest.raises(DatabaseTestLockError, match="0~3600"):
        lock_timeout(value)


def test_timeout_can_be_configured_without_application_settings(monkeypatch):
    monkeypatch.setenv("TEST_DB_LOCK_TIMEOUT", "1.5")
    assert lock_timeout() == 1.5
    assert lock_timeout(0) == 0


def test_connection_error_does_not_expose_driver_message(monkeypatch):
    engine = Mock()
    engine.connect.side_effect = RuntimeError("sensitive-connection-value")
    monkeypatch.setattr(db_lock, "create_engine", Mock(return_value=engine))
    with (
        pytest.raises(DatabaseTestLockError) as captured,
        DatabaseTestLock("mysql+pymysql://unit@localhost/spacecube_test"),
    ):
        pytest.fail("접속 실패 뒤 검증을 실행하면 안 됨")
    assert "sensitive-connection-value" not in str(captured.value)
    engine.dispose.assert_called_once()


@pytest.mark.parametrize("mode", ["collect", "without-url", "invalid-target"])
def test_pytest_entrypoint_handles_no_database_and_invalid_target(mode):
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("CHECK_DB_URL", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_db_lock.py::test_timeout_can_be_configured_without_application_settings",
    ]
    if mode != "without-url":
        environment["CHECK_DB_URL"] = "mysql+pymysql://unit:never-echo-this@192.0.2.1/production"
    if mode == "collect":
        command.append("--collect-only")
    result = subprocess.run(  # noqa: S603 -- 고정 pytest 대상, 비밀값 없는 검증용 주소
        command,
        env=environment,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert "never-echo-this" not in result.stdout + result.stderr
    assert result.returncode == (2 if mode == "invalid-target" else 0)


@pytest.fixture
def database_url():
    value = os.environ.get("CHECK_DB_URL")
    if not value:
        pytest.skip("실제 잠금 검증용 로컬 CHECK_DB_URL이 없습니다.")
    return value


@pytest.fixture
def lock_name():
    # pytest 자체가 가진 suite 잠금과 회귀 검증용 잠금을 분리한다.
    return f"spacecube_test:regression:{uuid4().hex}"


@contextmanager
def worker(name, *, timeout=5, hold=0):
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(  # noqa: S603 -- 고정 테스트 모듈, 접속정보는 환경변수로만 상속
        [
            sys.executable,
            "-m",
            "tests.lock_worker",
            "--name",
            name,
            "--timeout",
            str(timeout),
            "--hold",
            str(hold),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    lines = Queue()

    def read_stdout():
        for line in process.stdout:
            lines.put(line.strip())

    reader = Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        yield process, lines
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=5)
        process.stdout.close()
        process.stderr.close()


def test_success_and_exception_both_release_the_lock(database_url, lock_name):
    with DatabaseTestLock(database_url, name=lock_name, timeout=0) as lock:
        lock.assert_held()
        with pytest.raises(DatabaseTestLockError, match="이미 획득"):
            lock.__enter__()
        lock.assert_held()
    with pytest.raises(RuntimeError), DatabaseTestLock(database_url, name=lock_name, timeout=0):
        raise RuntimeError("검증 중 실패")
    with DatabaseTestLock(database_url, name=lock_name, timeout=0) as lock:
        lock.assert_held()


def test_other_process_waits_then_acquires_after_release(database_url, lock_name):
    with (
        DatabaseTestLock(database_url, name=lock_name, timeout=0) as lock,
        worker(lock_name) as (process, lines),
    ):
        assert lines.get(timeout=10) == "waiting"
        assert process.poll() is None
        lock.assert_held()
        lock.release()
        assert lines.get(timeout=10) == "acquired"
        assert lines.get(timeout=10) == "released"
        assert process.wait(timeout=10) == 0


def test_wait_timeout_is_explicit_and_leaves_no_lock(database_url, lock_name):
    with DatabaseTestLock(database_url, name=lock_name, timeout=0) as lock:
        started = monotonic()
        with worker(lock_name, timeout=0.4) as (process, lines):
            assert lines.get(timeout=10) == "waiting"
            assert lines.get(timeout=10) == "lock-error"
            assert process.wait(timeout=10) == 2
        assert monotonic() - started < 10
        lock.assert_held()
    with DatabaseTestLock(database_url, name=lock_name, timeout=0):
        pass


def test_process_termination_releases_server_lock(database_url, lock_name):
    with worker(lock_name, hold=30) as (process, lines):
        assert lines.get(timeout=10) == "acquired"
        process.terminate()
        process.wait(timeout=5)
    with DatabaseTestLock(database_url, name=lock_name, timeout=5) as lock:
        lock.assert_held()


def test_lost_connection_is_detected_before_next_test(database_url, lock_name):
    with (
        pytest.raises(DatabaseTestLockError, match="연결"),
        DatabaseTestLock(database_url, name=lock_name, timeout=0) as lock,
    ):
        lock._connection.close()
        lock.assert_held()
    with DatabaseTestLock(database_url, name=lock_name, timeout=0):
        pass


def test_lost_ownership_is_detected_before_next_test(database_url, lock_name):
    from sqlalchemy import text

    with (
        pytest.raises(DatabaseTestLockError, match="소유권"),
        DatabaseTestLock(database_url, name=lock_name, timeout=0) as lock,
    ):
        lock._connection.scalar(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
        lock.assert_held()
    with DatabaseTestLock(database_url, name=lock_name, timeout=0):
        pass
