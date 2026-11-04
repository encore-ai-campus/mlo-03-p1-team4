"""F-10 기준 정보의 공개 응답."""

from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    """유형의 코드와 표시 이름. 캐시된 응답 값은 변경하지 않는다."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    code: str
    name: str
