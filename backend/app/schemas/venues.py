"""F-20~22 공간 상세·예약 가능 날짜·시간 칸의 공개 계약."""

import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

from app.schemas.catalog import CategoryRead, FacilityRead


def _require_iso_date(value: object) -> str:
    """날짜 타입의 유연한 변환 전에 API의 YYYY-MM-DD 형식을 엄격히 확인한다."""
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력해 주세요.")
    return value


type BookingDate = Annotated[date, BeforeValidator(_require_iso_date)]


class VenueRegionRead(BaseModel):
    """지역 선택 목록과 달리 상세는 시·도와 시·군·구 이름을 함께 표시한다."""

    sido: str
    sigungu: str


class SlotRead(BaseModel):
    """지난 시간은 표시 정보이며 점유 여부와 독립적이다."""

    hour: int
    taken: bool
    past: bool


class AvailableDateRead(BaseModel):
    """빈 칸 총수와 최소 이용시간을 연속으로 예약할 수 있는지를 구분한다."""

    date: date
    free: int
    bookable: bool


class AvailableDatesRead(BaseModel):
    """days는 요청한 일수이며 날짜 상한에 걸리면 dates 길이는 더 짧을 수 있다."""

    venue_id: int
    offset: int
    days: int
    min_date: date
    max_date: date
    dates: list[AvailableDateRead]


class VenueRead(BaseModel):
    """상세 화면용 응답. 내부 출처 ID·등록 시각은 노출하지 않는다."""

    venue_id: int
    name: str
    category: CategoryRead
    region: VenueRegionRead
    capacity_max: int
    price_per_hour: int
    min_hours: int
    open_hour: int
    close_hour: int
    rating_avg: float
    review_count: int
    image: str
    images: list[str]
    facilities: list[FacilityRead]
    is_new: bool
    description: str | None
    notice: str | None
    slots: list[SlotRead]
