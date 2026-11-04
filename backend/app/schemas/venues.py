"""F-20 공간 상세의 공개 응답 계약."""

from pydantic import BaseModel

from app.schemas.catalog import CategoryRead, FacilityRead


class VenueRegionRead(BaseModel):
    """지역 선택 목록과 달리 상세는 시·도와 시·군·구 이름을 함께 표시한다."""

    sido: str
    sigungu: str


class SlotRead(BaseModel):
    """지난 시간은 표시 정보이며 점유 여부와 독립적이다."""

    hour: int
    taken: bool
    past: bool


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
