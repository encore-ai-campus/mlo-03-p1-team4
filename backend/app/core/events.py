"""F-60: 파일 우선 기록과 제한된 두 작업자·1,000건 대기열.

사용: 이벤트 서비스와 B 예약 서비스가 이벤트를 기록하고 MongoDB에 전달한다.
"""

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from threading import Event, Lock
from uuid import uuid4

import pymongo
from pymongo.errors import BulkWriteError

from app.core.clock import get_event_time
from app.core.config import get_settings
from app.core.errors import fail
from app.core.event_context import client_event_context
from app.core.logging import write_event
from app.core.metrics import mongo_event_write_failures_counter
from app.core.mongo import get_event_collection

FRONTEND_EVENTS = frozenset(
    {
        "search",
        "view_venue",
        "view_dates",
        "select_slot",
        "reserve_try",
        "reserve_cancel",
        "review_create",
        "login",
        "signup",
    }
)
SERVER_EVENTS = frozenset({"reserve_ok", "reserve_conflict", "reserve_cancel_ok"})
PAYLOAD_KEYS = frozenset(
    {
        "category",
        "sido",
        "sigungu",
        "date",
        "people",
        "headcount",
        "start_hour",
        "end_hour",
        "hours",
        "hour",
        "facilities",
        "facility_ids",
        "sort",
        "page",
        "size",
        "reservation_id",
        "rating",
        "slots",
        "reason",
        "result",
        "code",
    }
)
EVENT_DOCUMENT_FIELDS = frozenset(
    {
        "event_id",
        "ts",
        "client_ts",
        "session_id",
        "user_id",
        "event_type",
        "venue_id",
        "category",
        "payload",
        "is_synthetic",
        "server",
    }
)


@dataclass(slots=True)
class EventBuffer:
    documents: list[dict] = field(default_factory=list)
    file_failures: int = 0


event_buffer: ContextVar[EventBuffer | None] = ContextVar("event_buffer", default=None)


def sanitize_payload(payload: dict | None) -> dict:
    def clean(value, depth: int = 0):
        if depth > 3:
            return None
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, str):
            value = re.sub(r"[^\s@]+@[^\s@]+", "[가림]", value[:200])
            return re.sub(
                r"(?<!\d)(?:01[016789][- ]?\d{3,4}[- ]?\d{4}|\d{6})(?!\d)",
                "[가림]",
                value,
            )
        if isinstance(value, list):
            return [clean(item, depth + 1) for item in value[:50]]
        return None

    sanitized = {key: clean(value) for key, value in (payload or {}).items() if key in PAYLOAD_KEYS}
    if len(json.dumps(sanitized, ensure_ascii=True).encode("utf-8")) > 8192:
        # 대기열 1,000건이 큰 payload 때문에 메모리를 소진하지 않게 한다.
        return {}
    return sanitized


def insert_event_documents(documents: list[dict]) -> tuple[int, int]:
    """백그라운드·재적재가 공유한다. 중복 event_id만 정상적으로 건너뛴다."""
    try:
        with pymongo.timeout(1):
            result = get_event_collection().insert_many(documents, ordered=False)
        return len(result.inserted_ids), 0
    except BulkWriteError as error:
        details = error.details
        errors = details.get("writeErrors", [])
        if details.get("writeConcernErrors") or any(item.get("code") != 11000 for item in errors):
            raise
        if details.get("nInserted", 0) + len(errors) != len(documents):
            raise
        return details.get("nInserted", 0), len(errors)


class _EventWriter:
    def __init__(self):
        self.queue: Queue[dict] = Queue(maxsize=1000)
        self.stopping = Event()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mongo-events")
        self.workers = [self.executor.submit(self._consume) for _ in range(2)]

    def _consume(self) -> None:
        while not self.stopping.is_set() or not self.queue.empty():
            try:
                first = self.queue.get(timeout=0.1)
            except Empty:
                continue
            batch = [first]
            while len(batch) < 50:
                try:
                    batch.append(self.queue.get_nowait())
                except Empty:
                    break
            try:
                insert_event_documents(batch)
            except BulkWriteError as error:
                details = error.details
                duplicates = sum(
                    item.get("code") == 11000 for item in details.get("writeErrors", [])
                )
                failed = max(0, len(batch) - details.get("nInserted", 0) - duplicates)
                if details.get("writeConcernErrors"):
                    failed = len(batch)
                self._record_failure(failed)
            except Exception:
                self._record_failure(len(batch))
            finally:
                for _ in batch:
                    self.queue.task_done()

    @staticmethod
    def _record_failure(count: int) -> None:
        if count:
            mongo_event_write_failures_counter.inc(count)
            logging.getLogger("spacecube.app").warning(
                "MongoDB 이벤트 쓰기 실패, 파일에서 재처리 가능",
                extra={"count": count},
            )

    def stop(self) -> None:
        self.stopping.set()
        self.executor.shutdown(wait=True)


_writer: _EventWriter | None = None
_writer_lock = Lock()
_writer_closed = False


def start_event_writer() -> None:
    global _writer, _writer_closed
    with _writer_lock:
        if _writer is None:
            _writer = _EventWriter()
        _writer_closed = False


def submit_events(documents: list[dict]) -> None:
    global _writer
    if not documents:
        return
    dropped = 0
    with _writer_lock:
        if _writer_closed:
            dropped = len(documents)
        else:
            if _writer is None:
                _writer = _EventWriter()
            for document in documents:
                try:
                    _writer.queue.put_nowait(document)
                except Full:
                    dropped += 1
    if dropped:
        mongo_event_write_failures_counter.inc(dropped)
        logging.getLogger("spacecube.app").warning(
            "이벤트 대기열 포화 또는 종료, 파일에서 재처리 가능",
            extra={"count": dropped},
        )


def stop_event_writer() -> None:
    global _writer, _writer_closed
    with _writer_lock:
        _writer_closed = True
        writer, _writer = _writer, None
    if writer is not None:
        writer.stop()


def require_event_file() -> None:
    """이벤트 접수 API는 파일 기록 성공을 확인한 경우에만 202를 반환한다."""
    buffer = event_buffer.get()
    if buffer is not None and buffer.file_failures:
        raise fail("SERVICE_UNAVAILABLE", 503)


def _log_event(
    session_id,
    user_id,
    event_type,
    venue_id=None,
    category=None,
    payload=None,
    is_synthetic=False,
) -> None:
    if event_type not in FRONTEND_EVENTS | SERVER_EVENTS:
        logging.getLogger("spacecube.app").warning("명세에 없는 서버 이벤트 제외")
        return
    context = client_event_context.get()
    received_at = get_event_time()
    client_ts = (
        context.occurred_at.astimezone(received_at.tzinfo)
        if context is not None and context.occurred_at is not None
        else None
    )
    props = sanitize_payload(payload)
    document = {
        "event_id": str(uuid4()),
        "ts": received_at,
        "client_ts": client_ts,
        "session_id": session_id or "server",
        "user_id": user_id,
        "event_type": event_type,
        "venue_id": venue_id,
        "category": category,
        "payload": props,
        "is_synthetic": is_synthetic,
        "server": get_settings().server_name,
    }
    buffer = event_buffer.get()
    try:
        write_event(document)
    except Exception:
        if buffer is not None:
            buffer.file_failures += 1
        logging.getLogger("spacecube.app").error(
            "이벤트 파일 기록 실패. 디스크 공간·권한을 확인하세요.",
        )
    # 관측 실패가 이미 커밋한 예약을 사용자에게 실패로 보이게 해서는 안 된다.
    if buffer is None:
        submit_events([document])
    else:
        buffer.documents.append(document)


def log_event(
    session_id,
    user_id,
    event_type,
    venue_id=None,
    category=None,
    payload=None,
    is_synthetic=False,
) -> None:
    """A·B 공용 약속. 관측 계층의 오류가 업무 응답으로 전파되지 않게 한다."""
    try:
        _log_event(session_id, user_id, event_type, venue_id, category, payload, is_synthetic)
    except Exception:
        buffer = event_buffer.get()
        if buffer is not None:
            buffer.file_failures += 1
        logging.getLogger("spacecube.app").error("이벤트 처리 실패, 업무 결과는 유지")
