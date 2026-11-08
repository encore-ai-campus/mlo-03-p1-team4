"""프론트 이벤트의 선택적 클라이언트 시각을 공용 기록 함수에 전달한다."""

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ClientEventContext:
    occurred_at: datetime | None
    anonymous_id: str | None = None
    session_sequence: int | None = None
    browser_context: dict | None = None


client_event_context: ContextVar[ClientEventContext | None] = ContextVar(
    "client_event_context",
    default=None,
)
