"""F-30~32 예약 생성과 모의 결제. /reservations 접두사는 앱에서 등록한다."""

import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user, get_session_id
from app.core.errors import AppError
from app.core.synthetic import is_synthetic_request
from app.schemas.reservations import ReservationCreate, ReservationCreateRead
from app.services import reservation_service

router = APIRouter()


class _SyntheticSettings(BaseSettings):
    """B API가 A의 공통 설정 변경 전에도 F-62의 별도 키를 확인한다."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    synthetic_api_key: SecretStr | None = None


@lru_cache
def _get_synthetic_api_key() -> SecretStr | None:
    return _SyntheticSettings().synthetic_api_key


def _is_synthetic_booking(request: Request) -> bool:
    if not is_synthetic_request(request):
        return False
    configured = _get_synthetic_api_key()
    supplied = request.headers.get("X-Synthetic-Key", "")
    if (
        configured is None
        or not supplied
        or not secrets.compare_digest(
            supplied.encode("utf-8"), configured.get_secret_value().encode("utf-8")
        )
    ):
        raise AppError("UNAUTHORIZED", "로그인이 필요해요.", 401)
    return True


@router.post(
    "",
    status_code=201,
    responses={
        200: {"model": ReservationCreateRead, "description": "10분 안에 재시도한 기존 예약"}
    },
    summary="예약·모의 결제",
)
def create_reservation(
    body: ReservationCreate,
    request: Request,
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_write)],
) -> ReservationCreateRead:
    """예약·시간 칸·모의 결제를 한 트랜잭션으로 확정한다."""
    result, status_code = reservation_service.create_reservation(
        db,
        body,
        user_id=current_user.user_id,
        session_id=get_session_id(request),
        is_synthetic=_is_synthetic_booking(request),
    )
    response.status_code = status_code
    return result
