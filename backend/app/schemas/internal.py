"""F-61: 크롤러·생성기가 보내는 전처리 공간과 등록 결과."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

ArtCode = Annotated[str, Field(pattern=r"^art:[a-z]+-[01]$", max_length=500)]


class InternalVenueUpsert(BaseModel):
    """업체 원문 대신 생성한 이름·설명과 일러스트 코드만 받는다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_site: Literal["spacecloud", "shareit", "synthetic"]
    source_id: Annotated[str, Field(min_length=1, max_length=50)]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    category_code: Annotated[str, Field(min_length=1, max_length=20)]
    sido: Annotated[str, Field(min_length=1, max_length=20)]
    sigungu: Annotated[str, Field(min_length=1, max_length=30)]
    capacity_max: Annotated[StrictInt, Field(ge=1, le=32767)]
    price_per_hour: Annotated[StrictInt, Field(gt=0, le=2147483647)]
    min_hours: Annotated[StrictInt, Field(ge=1, le=4)] = 1
    open_hour: Annotated[StrictInt, Field(ge=9, le=22)] = 9
    close_hour: Annotated[StrictInt, Field(ge=10, le=23)] = 23
    description: str | None = None
    notice: str | None = None
    facilities: list[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)
    # sort_order는 기존 DDL의 signed TINYINT(0~127)에 맞춘다.
    images: Annotated[list[ArtCode], Field(max_length=128)] = Field(default_factory=list)

    @field_validator("description", "notice")
    @classmethod
    def validate_text_storage(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 65535:
            raise ValueError("설명·안내는 UTF-8 기준 65,535바이트 이내여야 합니다.")
        return value

    @model_validator(mode="after")
    def validate_business_hours(self):
        if self.close_hour <= self.open_hour:
            raise ValueError("종료 시각은 시작 시각보다 뒤여야 합니다.")
        return self


class InternalVenueRead(BaseModel):
    venue_id: int
    ignored_facilities: list[str]
