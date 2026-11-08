"""F-64: 개인정보를 제외한 JSON 로그와 여러 프로세스의 파일 쓰기 보호.

사용: 요청 미들웨어와 이벤트 작성기가 개인정보를 제외한 로그 파일에 기록한다.
"""

import errno
import json
import logging
import os
import sys
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from pathlib import Path
from threading import RLock
from time import monotonic, sleep

from app.core.clock import get_event_time
from app.core.config import get_settings
from app.core.metrics import event_file_lock_wait_seconds, event_file_write_duration_seconds

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_file_lock = RLock()


class EventFileWriteError(OSError):
    """이벤트 파일 실패의 안전한 단계·원인 코드. OS 예외 원문은 보존하지 않는다."""

    def __init__(self, stage: str, reason: str, error_type: str):
        self.stage = stage
        self.reason = reason
        self.error_type = error_type
        super().__init__(f"이벤트 파일 오류: {stage}/{reason}")


class EventFileLockTimeout(EventFileWriteError):
    """스레드 또는 OS 파일 잠금 대기 제한을 넘긴 경우."""

    def __init__(self, scope: str):
        self.scope = scope
        stage = "thread_lock" if scope == "thread" else "process_lock"
        super().__init__(stage, "lock_timeout", "EventFileLockTimeout")


def event_file_failure_reason(error: Exception) -> str:
    if isinstance(error, EventFileWriteError):
        return error.reason
    if isinstance(error, PermissionError) or getattr(error, "errno", None) in {
        errno.EACCES,
        errno.EPERM,
    }:
        return "permission"
    if getattr(error, "errno", None) in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}:
        return "disk_full"
    if isinstance(error, (TypeError, ValueError)):
        return "serialization_error"
    return "io_error"


_fields = (
    "request_id",
    "path",
    "method",
    "status",
    "ms",
    "user_id",
    "error_type",
    "error_location",
    "failure_reason",
    "count",
    "completed",
)


@contextmanager
def _process_lock(path: Path):
    # workers=2가 같은 파일을 쓸 때 JSON 줄이 서로 섞이지 않게 한다.
    thread_wait_started = monotonic()
    if not _file_lock.acquire(timeout=0.1):
        event_file_lock_wait_seconds.labels(scope="thread").observe(
            monotonic() - thread_wait_started
        )
        raise EventFileLockTimeout("thread")
    event_file_lock_wait_seconds.labels(scope="thread").observe(monotonic() - thread_wait_started)
    locked = False
    try:
        lock_path = path.with_suffix(path.suffix + ".lock")
        try:
            stream = lock_path.open("a+b")
        except OSError as error:
            raise EventFileWriteError(
                "lock_file_open", event_file_failure_reason(error), type(error).__name__
            ) from error
        with stream:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    if not stream.read(1):
                        stream.write(b"0")
                        stream.flush()

                    def acquire():
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

                    def release():
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    def acquire():
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                    def release():
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError as error:
                raise EventFileWriteError(
                    "lock_file_init", event_file_failure_reason(error), type(error).__name__
                ) from error

            process_wait_started = monotonic()
            process_wait_recorded = False

            def record_process_wait():
                nonlocal process_wait_recorded
                if not process_wait_recorded:
                    event_file_lock_wait_seconds.labels(scope="process").observe(
                        monotonic() - process_wait_started
                    )
                    process_wait_recorded = True

            deadline = monotonic() + 0.1
            while True:
                try:
                    acquire()
                    locked = True
                    break
                except OSError as error:
                    if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        record_process_wait()
                        raise EventFileWriteError(
                            "process_lock", event_file_failure_reason(error), type(error).__name__
                        ) from error
                    if monotonic() >= deadline:
                        record_process_wait()
                        raise EventFileLockTimeout("process") from error
                    sleep(0.005)
            record_process_wait()
            try:
                yield
            finally:
                if locked:
                    try:
                        release()
                    except OSError as error:
                        raise EventFileWriteError(
                            "process_unlock", event_file_failure_reason(error), type(error).__name__
                        ) from error
    finally:
        _file_lock.release()


def append_json(path: Path, document: dict) -> None:
    started = monotonic()
    try:
        try:
            line = json.dumps(
                document,
                ensure_ascii=False,
                allow_nan=False,
                default=lambda value: value.isoformat(),
            )
        except Exception as error:
            raise EventFileWriteError(
                "serialize", "serialization_error", type(error).__name__
            ) from error

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise EventFileWriteError(
                "directory_prepare", event_file_failure_reason(error), type(error).__name__
            ) from error

        with _process_lock(path):
            try:
                stream = path.open(
                    "a",
                    encoding="utf-8",
                    errors="backslashreplace",
                )
            except OSError as error:
                raise EventFileWriteError(
                    "event_file_open", event_file_failure_reason(error), type(error).__name__
                ) from error
            try:
                with stream:
                    stream.write(line + "\n")
            except OSError as error:
                raise EventFileWriteError(
                    "append", event_file_failure_reason(error), type(error).__name__
                ) from error
    finally:
        event_file_write_duration_seconds.observe(monotonic() - started)


def console_warning(message: str) -> None:
    # 파일 장치 장애 때도 예외 원문이나 비밀값을 stderr에 출력하지 않는다.
    with suppress(OSError, ValueError):
        sys.stderr.write(message + "\n")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value = {
            "ts": get_event_time().isoformat(),
            "server": get_settings().server_name,
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            value["request_id"] = request_id
        value.update({key: getattr(record, key) for key in _fields if hasattr(record, key)})
        return json.dumps(value, ensure_ascii=False, allow_nan=False)


class SafeJsonHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            document = json.loads(self.format(record))
            append_json(get_settings().log_path / "app.log", document)
        except Exception:
            console_warning("공간큐브 app.log 기록 실패. 디스크 공간·권한을 확인하세요.")


def setup_logging() -> None:
    logger = logging.getLogger("spacecube.app")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    handler = SafeJsonHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logging.getLogger("uvicorn.access").disabled = True


def write_event(document: dict) -> None:
    append_json(get_settings().log_path / "events.log", document)
