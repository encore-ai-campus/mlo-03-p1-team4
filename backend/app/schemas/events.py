"""문서에 정의된 프론트 이벤트를 50건 이하 묶음으로 검증한다.

사용: 이벤트 라우터가 사용자 행동과 세션·페이지 정보 묶음을 검증한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, StrictInt, field_validator

from app.core.clock import as_korean_time
from app.schemas.auth import RequestModel


class EventCreate(RequestModel):
    event_type: str = Field(min_length=1, max_length=100)
    venue_id: StrictInt | None = Field(default=None, ge=1, le=9223372036854775807)
    payload: dict = Field(default_factory=dict)
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_client_time(cls, value: datetime | None):
        return as_korean_time(value) if value is not None else None


class EventBatchCreate(RequestModel):
    session_id: UUID
    events: list[EventCreate] = Field(min_length=1, max_length=50)


class IgnoredEventRead(BaseModel):
    event_type: str
    count: int


class EventBatchRead(BaseModel):
    accepted: int
    ignored: list[IgnoredEventRead]
