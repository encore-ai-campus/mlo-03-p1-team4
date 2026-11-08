"""F-02: bcrypt와 HS256 액세스 토큰.

사용: 인증·회원 서비스가 비밀번호를 검증하고 JWT를 발급·해석한다.
"""

import secrets
from datetime import timedelta

import bcrypt
import jwt

from app.core.clock import KST, get_now
from app.core.config import get_settings
from app.core.errors import fail


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


def _jwt_key() -> str:
    value = get_settings().jwt_secret
    if value is None or len(value.get_secret_value().encode("utf-8")) < 32:
        raise fail("SERVICE_UNAVAILABLE", 503)
    return value.get_secret_value()


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    issued = get_now().replace(tzinfo=KST)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": issued,
            "exp": issued + timedelta(minutes=settings.jwt_expire_minutes),
        },
        _jwt_key(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> int:
    try:
        claims = jwt.decode(
            token, _jwt_key(), algorithms=["HS256"], options={"require": ["sub", "iat", "exp"]}
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
            raise fail("UNAUTHORIZED", 401)
        user_id = int(subject)
        if user_id < 1 or user_id > 9223372036854775807:
            raise fail("UNAUTHORIZED", 401)
        return user_id
    except jwt.ExpiredSignatureError as error:
        raise fail("TOKEN_EXPIRED", 401) from error
    except jwt.InvalidTokenError as error:
        raise fail("UNAUTHORIZED", 401) from error


def unusable_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))
