"""F-60: 새 이벤트 수집 계약과 Swagger 요청 예시."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.core.clock import as_korean_time
from app.schemas.auth import RequestModel


class EventUserContext(RequestModel):
    # 혹시 포함된 클라이언트 user_id 등은 Pydantic에서 버리고 인증 결과만 사용한다.
    model_config = ConfigDict(extra="ignore")

    anonymous_id: str | None = None
    session_id: str | None = None
    session_sequence: StrictInt | None = None


class EventSiteContext(RequestModel):
    site_id: str | None = None
    hostname: str | None = None
    platform: Literal["desktop_web", "mobile_web", "ios", "android"] | None = None


class EventAcquisitionContext(RequestModel):
    landing_url: str | None = None
    referrer_url: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


class EventPageContext(RequestModel):
    page_view_id: str | None = None
    page_type: str | None = None
    url: str | None = None
    path: str | None = None
    title: str | None = None


class EventNavigationPoint(RequestModel):
    page_view_id: str | None = None
    site_id: str | None = None
    url: str | None = None
    path: str | None = None


class EventNavigationContext(RequestModel):
    from_page: EventNavigationPoint | None = Field(default=None, alias="from")
    to: EventNavigationPoint | None = None
    navigation_type: Literal["external", "internal", "direct", "reload", "history"] | None = None


class EventProductReference(RequestModel):
    product_id: str | None = None


class EventCreate(RequestModel):
    event_id: UUID | None = None
    schema_version: Literal[1] = 1
    event_name: str = Field(min_length=1, max_length=100)
    user: EventUserContext | None = None
    site: EventSiteContext | None = None
    acquisition: EventAcquisitionContext | None = None
    page: EventPageContext | None = None
    navigation: EventNavigationContext | None = None
    products: list[EventProductReference] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_client_time(cls, value: datetime | None):
        return as_korean_time(value) if value is not None else None


EVENT_BATCH_EXAMPLES = {
    "search_submit": {
        "summary": "검색 제출 (개인정보 제거 확인)",
        "description": ("URL query·fragment와 자유 문자열 properties는 저장 전에 제거됩니다."),
        "value": {
            "session_id": "4b1c0000-0000-4000-8000-000000000001",
            "events": [
                {
                    "schema_version": 1,
                    "event_name": "search_submit",
                    "occurred_at": "2026-11-06T12:00:00+09:00",
                    "user": {
                        "anonymous_id": "anon-test-001",
                        "session_id": "4b1c0000-0000-4000-8000-000000000001",
                        "session_sequence": 1,
                    },
                    "site": {
                        "site_id": "main",
                        "hostname": "127.0.0.1",
                        "platform": "desktop_web",
                    },
                    "acquisition": {
                        "landing_url": "http://127.0.0.1:8001/search?q=private",
                        "referrer_url": None,
                        "utm_source": "private",
                        "utm_medium": None,
                        "utm_campaign": None,
                    },
                    "page": {
                        "page_view_id": "page-test-001",
                        "page_type": "search_results",
                        "url": "http://127.0.0.1:8001/search?q=private#secret",
                        "path": "/search",
                        "title": "개인정보가 든 제목",
                    },
                    "navigation": {
                        "from": None,
                        "to": {
                            "page_view_id": "page-test-001",
                            "site_id": "main",
                            "url": "http://127.0.0.1:8001/search?q=private",
                            "path": "/search",
                        },
                        "navigation_type": "direct",
                    },
                    "products": [],
                    "properties": {
                        "page": 1,
                        "region_id": 1,
                        "facility_ids": [1, 2],
                        "q": "private@example.com",
                    },
                }
            ],
        },
    }
}


class EventBatchCreate(RequestModel):
    session_id: UUID
    events: list[EventCreate] = Field(min_length=1, max_length=50)


class IgnoredEventRead(BaseModel):
    event_type: str
    count: int


class EventBatchRead(BaseModel):
    accepted: int
    ignored: list[IgnoredEventRead]
