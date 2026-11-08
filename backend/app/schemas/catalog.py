"""F-10·11 기준 정보의 공개 응답."""

from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    """유형의 코드와 표시 이름. 캐시된 응답 값은 변경하지 않는다."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    code: str
    name: str


class RegionRead(BaseModel):
    """선택한 시·도의 시·군·구 응답."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    region_id: int
    sigungu: str


class FacilityRead(BaseModel):
    """시설 필터의 식별자와 표시 이름."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    facility_id: int
    name: str
