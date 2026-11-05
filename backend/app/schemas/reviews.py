"""후기 요청과 공개 목록 항목.

사용: 후기 라우터가 별점·내용·정렬 조건과 목록 응답을 검증한다.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, StrictInt, field_serializer, field_validator, model_validator

from app.core.clock import as_korean_time
from app.schemas.auth import RequestModel

Category = Literal["studyroom", "studio", "cafe", "lectureroom", "partyroom"]
ReviewSort = Literal["recent", "high", "low"]


def clean_content(value: str) -> str:
    if not value.strip():
        raise ValueError("후기 내용을 입력해 주세요.")
    if len(value.encode("utf-8")) > 65535:
        raise ValueError("후기는 UTF-8 65,535바이트 이하여야 해요.")
    return value.strip()


class ReviewCreate(RequestModel):
    rating: StrictInt = Field(ge=1, le=5)
    content: str = Field(min_length=1)

    _content = field_validator("content")(clean_content)


class ReviewUpdate(RequestModel):
    rating: StrictInt | None = Field(default=None, ge=1, le=5)
    content: str | None = None

    @model_validator(mode="after")
    def check_values(self):
        from app.core.errors import invalid_field

        if not self.model_fields_set:
            raise invalid_field("body", "변경할 값을 입력해 주세요.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise invalid_field(field, "null은 사용할 수 없어요.")
        if self.content is not None:
            try:
                self.content = clean_content(self.content)
            except ValueError as error:
                raise invalid_field("content", str(error)) from error
        return self


class ReviewRead(BaseModel):
    review_id: int


class ReviewListItem(BaseModel):
    review_id: int
    venue_id: int
    venue_name: str
    category: Category
    rating: int
    content: str
    author: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_time(self, value: datetime) -> str:
        return as_korean_time(value).isoformat()
