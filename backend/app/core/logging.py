"""F-64: 개인정보를 제외한 JSON 로그와 여러 프로세스의 파일 쓰기 보호.

사용: 요청 미들웨어와 이벤트 작성기가 개인정보를 제외한 로그 파일에 기록한다.
"""

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

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_file_lock = RLock()
FILE_LOCK_WAIT_SECONDS = 0.5
_fields = (
    "request_id",
    "path",
    "method",
    "status",
    "ms",
    "user_id",
    "error_type",
    "error_location",
    "count",
    "completed",
)


@contextmanager
def _process_lock(path: Path):
    # workers=2가 같은 파일을 쓸 때 JSON 줄이 서로 섞이지 않게 한다.
    if not _file_lock.acquire(timeout=FILE_LOCK_WAIT_SECONDS):
        raise OSError("로그 파일 잠금 대기 초과")
    locked = False
    try:
        with path.with_suffix(path.suffix + ".lock").open("a+b") as stream:
            if os.name == "nt":
                import msvcrt

                if os.fstat(stream.fileno()).st_size == 0:
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

            deadline = monotonic() + FILE_LOCK_WAIT_SECONDS
            while True:
                try:
                    acquire()
                    locked = True
                    break
                except OSError:
                    if monotonic() >= deadline:
                        raise
                    sleep(0.005)
            try:
                yield
            finally:
                if locked:
                    release()
    finally:
        _file_lock.release()


def append_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        default=lambda value: value.isoformat(),
    )
    with (
        _process_lock(path),
        path.open(
            "a",
            encoding="utf-8",
            errors="backslashreplace",
        ) as stream,
    ):
        stream.write(line + "\n")


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
