"""F-20~22 공개 공간 상세·날짜·시간 칸. /venues 접두사는 앱에서 등록한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_read
from app.schemas.venues import AvailableDatesRead, BookingDate, SlotRead, VenueRead
from app.services import venue_service

router = APIRouter()


@router.get("/{venue_id}", summary="공간 상세 조회")
def get_venue(
    venue_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    db: Annotated[Session, Depends(get_db_read)],
) -> VenueRead:
    """인증 없이 활성 공간의 정보와 오늘 시간 칸을 반환한다."""
    return venue_service.get_venue(db, venue_id)


@router.get("/{venue_id}/slots", summary="날짜별 시간 칸 조회")
def get_slots(
    venue_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    requested_date: Annotated[BookingDate, Query(alias="date")],
    db: Annotated[Session, Depends(get_db_read)],
) -> list[SlotRead]:
    """고른 날짜의 영업시간 칸마다 점유·지난 시간 표시를 반환한다."""
    return venue_service.get_slots(db, venue_id, requested_date)


@router.get("/{venue_id}/available-dates", summary="예약 가능 날짜 조회")
def get_available_dates(
    venue_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    db: Annotated[Session, Depends(get_db_read)],
    offset: Annotated[int, Query()] = 0,
    days: Annotated[int, Query(ge=1, le=31)] = 14,
) -> AvailableDatesRead:
    """예약 불가능한 날도 포함해 날짜별 빈 칸 수·예약 가능 여부를 반환한다."""
    return venue_service.get_available_dates(db, venue_id, offset, days)
