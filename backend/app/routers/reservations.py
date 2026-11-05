"""F-30~32 예약 생성과 F-40 내역 조회. 접두사는 앱에서 등록한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.db import get_db_write
from app.core.deps import CurrentUser, get_current_user, get_session_id
from app.core.pagination import Page, Pagination, get_pagination
from app.core.synthetic import is_synthetic_request
from app.schemas.reservations import (
    ReservationCreate,
    ReservationCreateRead,
    ReservationRead,
    ReservationStatus,
)
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


@router.get(
    "/me",
    response_model_exclude_unset=True,
    summary="내 예약 목록",
)
def get_my_reservations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_write)],
    pagination: Annotated[Pagination, Depends(get_pagination)],
    status: Annotated[ReservationStatus | None, Query()] = None,
) -> Page[ReservationRead]:
    """본인 예약을 primary에서 상태별로 페이지 조회한다."""
    return reservation_service.get_my_reservations(
        db,
        user_id=current_user.user_id,
        status=status,
        pagination=pagination,
    )


@router.get(
    "/{reservation_id}",
    response_model_exclude_unset=True,
    summary="내 예약 상세",
)
def get_my_reservation(
    reservation_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_write)],
) -> ReservationRead:
    """본인 예약 한 건을 조회하고 타인·없는 예약은 같은 404로 감춘다."""
    return reservation_service.get_my_reservation(
        db,
        user_id=current_user.user_id,
        reservation_id=reservation_id,
    )
