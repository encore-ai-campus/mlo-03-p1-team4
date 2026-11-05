"""F-12~13 검색·정렬과 F-20~22 공개 공간 조회. /venues 접두사는 앱에서 등록한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_read
from app.core.pagination import Page
from app.schemas.venues import (
    AvailableDatesRead,
    BookingDate,
    SlotRead,
    VenueListItem,
    VenueRead,
    VenueSort,
)
from app.services import venue_service

router = APIRouter()


@router.get("", summary="공간 검색·정렬")
def search_venues(
    db: Annotated[Session, Depends(get_db_read)],
    q: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    sido: Annotated[str | None, Query()] = None,
    sigungu: Annotated[str | None, Query()] = None,
    requested_date: Annotated[BookingDate | None, Query(alias="date")] = None,
    start_hour: Annotated[int | None, Query()] = None,
    hours: Annotated[int | None, Query()] = None,
    people: Annotated[int | None, Query(ge=1)] = None,
    facilities: Annotated[str | None, Query()] = None,
    now_only: Annotated[bool, Query(alias="now")] = False,
    sort: Annotated[VenueSort, Query()] = "default",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> Page[VenueListItem]:
    """검색 조건을 적용한 공간 목록과 검색 조건 이후 전체 결과 수를 반환한다."""
    return venue_service.search_venues(
        db,
        q=q,
        category=category,
        sido=sido,
        sigungu=sigungu,
        requested_date=requested_date,
        start_hour=start_hour,
        hours=hours,
        people=people,
        facilities=facilities,
        now_only=now_only,
        sort=sort,
        page=page,
        size=size,
    )


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
