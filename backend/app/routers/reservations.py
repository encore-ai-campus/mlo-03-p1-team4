"""F-30~32 예약 생성과 모의 결제. /reservations 접두사는 앱에서 등록한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user, get_session_id
from app.core.synthetic import is_synthetic_request
from app.schemas.reservations import ReservationCreate, ReservationCreateRead
from app.services import reservation_service

router = APIRouter()


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
        is_synthetic=is_synthetic_request(request),
    )
    response.status_code = status_code
    return result
