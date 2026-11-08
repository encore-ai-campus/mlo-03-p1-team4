"""B도 사용하는 인증·내부 키·세션 ID 의존성.

사용: 회원 전용 라우터와 B의 예약 라우터가 현재 사용자와 세션 ID를 얻는다.
"""

import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db_write, new_write_session
from app.core.errors import fail
from app.core.security import decode_access_token
from app.repositories import user_repo

bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description="로그인 응답의 access_token을 입력하세요. Bearer 접두사는 입력하지 않습니다.",
)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
WriteDB = Annotated[Session, Depends(get_db_write)]


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: int


def _authenticate(request: Request, user_id: int, db: Session) -> CurrentUser:
    if user_repo.get_active(db, user_id) is None:
        raise fail("UNAUTHORIZED", 401)
    request.state.user_id = user_id
    return CurrentUser(user_id)


def _read_access_token(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    if request.headers.get("Authorization"):
        if credentials is None:
            raise fail("UNAUTHORIZED", 401)
        return credentials.credentials
    return None


def _token_subject(request: Request, credentials: Credentials) -> int:
    token = _read_access_token(request, credentials)
    if token is None:
        raise fail("UNAUTHORIZED", 401)
    return decode_access_token(token)


def get_current_user(
    request: Request,
    user_id: Annotated[int, Depends(_token_subject)],
    db: WriteDB,
) -> CurrentUser:
    """A·B 회원 전용 API가 사용하는 의존성으로 primary에서 탈퇴 여부를 확인한다."""
    # 토큰을 먼저 확인한다. 인증되지 않은 요청은 DB 연결을 점유하지 않는다.
    return _authenticate(request, user_id, db)


def get_optional_user(request: Request, credentials: Credentials) -> CurrentUser | None:
    """이벤트 API에 인증된 회원을 제공하고 인증 정보가 없으면 비회원으로 처리한다."""
    token = _read_access_token(request, credentials)
    if token is None:
        return None
    # 비회원 이벤트는 MariaDB 연결 없이도 받을 수 있다.
    user_id = decode_access_token(token)
    with new_write_session() as db:
        return _authenticate(request, user_id, db)


def require_internal_key(request: Request) -> None:
    configured = get_settings().internal_api_key
    supplied = request.headers.get("X-Internal-Key", "")
    if (
        configured is None
        or not supplied
        or not secrets.compare_digest(
            supplied.encode("utf-8"),
            configured.get_secret_value().encode("utf-8"),
        )
    ):
        raise fail("UNAUTHORIZED", 401)


def get_session_id(request: Request) -> str | None:
    """B 예약 서비스가 프론트 이벤트와 묶을 수 있는 UUID 세션을 읽는다."""
    value = request.headers.get("X-Session-Id")
    if value is None:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None
