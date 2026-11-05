"""F-01~02: 명세에 정의된 가입·로그인 필드만 받는다.

사용: 인증 라우터가 가입·로그인 입력과 응답 형식을 검증한다.
"""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from app.core.clock import get_today


class RequestModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
        hide_input_in_errors=True,
    )


def validate_email(value: str) -> str:
    if len(value) > 100 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("올바른 이메일 형식, 100자 이하")
    return value


def validate_password(value: str) -> str:
    if len(value) < 8 or len(value.encode("utf-8")) > 72:
        raise ValueError("8자 이상, UTF-8 72바이트 이하")
    return value


Email = Annotated[str, Field(min_length=3, max_length=100)]
Password = Annotated[str, Field(min_length=8)]


class SignupCreate(RequestModel):
    email: Email
    password: Password
    name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=1, max_length=20)
    birth: str = Field(pattern=r"^[0-9]{6}$")
    gender_digit: Literal["1", "2", "3", "4"]
    marketing_agreed: StrictBool
    terms_agreed: StrictBool
    privacy_agreed: StrictBool

    _email = field_validator("email")(validate_email)
    _password = field_validator("password")(validate_password)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("이름을 입력해 주세요.")
        return value.strip()

    @field_validator("terms_agreed", "privacy_agreed")
    @classmethod
    def required_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("필수 동의가 필요해요.")
        return value

    @model_validator(mode="after")
    def check_birth(self):
        from app.core.errors import invalid_field

        century = 1900 if self.gender_digit in {"1", "2"} else 2000
        try:
            born = date(century + int(self.birth[:2]), int(self.birth[2:4]), int(self.birth[4:]))
        except ValueError as error:
            raise invalid_field("birth", "실제 있는 날짜") from error
        today = get_today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        if born > today:
            raise invalid_field("birth", "미래 생년월일은 사용할 수 없어요.")
        if age < 14:
            raise invalid_field("birth", "under_14")
        return self


class LoginCreate(RequestModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)

    _email = field_validator("email")(validate_email)


class SignupRead(BaseModel):
    user_id: int


class EmailCheckRead(BaseModel):
    available: bool


class LoginRead(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 -- OAuth 인증 방식 이름이지 비밀번호가 아님
    expires_in: int
