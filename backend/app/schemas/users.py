"""F-03: 내 정보 응답에는 비밀번호 해시를 노출하지 않는다.

사용: 회원 라우터가 내 정보 변경과 응답의 공개 필드를 제한한다.
"""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.clock import as_korean_time
from app.schemas.auth import RequestModel, validate_password, validate_phone


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    email: str
    name: str
    phone: str | None
    birth: str
    gender_digit: str
    marketing_agreed: bool
    terms_agreed_at: datetime
    privacy_agreed_at: datetime
    created_at: datetime

    @field_serializer("created_at", "terms_agreed_at", "privacy_agreed_at")
    def serialize_time(self, value: datetime) -> str:
        return as_korean_time(value).isoformat()


class UserUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=20)
    marketing_agreed: StrictBool | None = None

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_phone(value)

    @model_validator(mode="after")
    def check_values(self):
        from app.core.errors import invalid_field

        if not self.model_fields_set:
            raise invalid_field("body", "변경할 값을 입력해 주세요.")
        for field in ("name", "marketing_agreed"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise invalid_field(field, "null은 사용할 수 없어요.")
        if self.name is not None and not self.name.strip():
            raise invalid_field("name", "이름을 입력해 주세요.")
        if self.name is not None:
            self.name = self.name.strip()
        return self


class PasswordUpdate(RequestModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str

    _password = field_validator("new_password")(validate_password)
