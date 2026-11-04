"""F-20~22 공간 상세·예약 가능 날짜·시간 칸과 F-14 공통 NEW 판정."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.clock import get_now, get_today
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import slot_repo, venue_repo
from app.schemas.catalog import CategoryRead, FacilityRead
from app.schemas.venues import (
    AvailableDateRead,
    AvailableDatesRead,
    SlotRead,
    VenueRead,
    VenueRegionRead,
)

_DEFAULT_IMAGE = "art:group-0"


def resolve_images(images: Sequence[str]) -> tuple[str, list[str]]:
    """정렬된 이미지가 없으면 대표 그림과 갤러리에 같은 RoomArt 기본값을 쓴다."""
    gallery = [image for image in images if image] or [_DEFAULT_IMAGE]
    return gallery[0], gallery


def is_new_venue(created_at: datetime) -> bool:
    """DB의 시간대 없는 한국 시각을 날짜로 비교한다. 오늘부터 13일 전까지 NEW다."""
    age_days = (get_today() - created_at.date()).days
    return 0 <= age_days < 14


def build_slots(
    open_hour: int,
    close_hour: int,
    slot_date: date,
    taken_hours: set[int],
    *,
    today: date,
    now: datetime,
) -> list[SlotRead]:
    """F-22에서도 사용할 시간 칸 조합. 이미 지난 칸도 응답에서 제외하지 않는다."""
    return [
        SlotRead(
            hour=hour,
            taken=hour in taken_hours,
            past=slot_date < today or (slot_date == today and hour <= now.hour),
        )
        for hour in range(open_hour, close_hour)
    ]


def get_venue(db: Session, venue_id: int) -> VenueRead:
    """상세 응답에 필요한 공개 값만 조합한다. 쓰기·캐시·후기 목록 조회는 하지 않는다."""
    venue = venue_repo.get_detail(db, venue_id)
    if venue is None:
        raise AppError("VENUE_NOT_FOUND", "공간을 찾을 수 없어요.", 404)

    image, images = resolve_images(venue_repo.list_images(db, venue_id))
    today = get_today()
    slots = build_slots(
        venue["open_hour"],
        venue["close_hour"],
        today,
        slot_repo.list_taken_hours(db, venue_id, today),
        today=today,
        now=get_now(),
    )
    return VenueRead(
        venue_id=venue["venue_id"],
        name=venue["name"],
        category=CategoryRead(code=venue["category_code"], name=venue["category_name"]),
        region=VenueRegionRead(sido=venue["sido"], sigungu=venue["sigungu"]),
        capacity_max=venue["capacity_max"],
        price_per_hour=venue["price_per_hour"],
        min_hours=venue["min_hours"],
        open_hour=venue["open_hour"],
        close_hour=venue["close_hour"],
        rating_avg=venue["rating_avg"],
        review_count=venue["review_count"],
        image=image,
        images=images,
        facilities=[
            FacilityRead.model_validate(facility)
            for facility in venue_repo.list_facilities(db, venue_id)
        ],
        is_new=is_new_venue(venue["created_at"]),
        description=venue["description"],
        notice=venue["notice"],
        slots=slots,
    )


def _booking_date_range(today: date, offset: int) -> tuple[date, date]:
    """F-21·22가 같은 날짜 범위·오류를 쓰고 큰 offset도 날짜 변환 전에 거절한다."""
    settings = get_settings()
    min_date = today - timedelta(days=settings.booking_past_days)
    max_date = today + timedelta(days=settings.booking_future_days)
    if not -settings.booking_past_days <= offset <= settings.booking_future_days:
        raise AppError(
            "OUT_OF_RANGE",
            "예약할 수 없는 날짜나 시간이에요.",
            400,
            detail={
                "reason": "date",
                "min_date": min_date.isoformat(),
                "max_date": max_date.isoformat(),
            },
        )
    return min_date, max_date


def get_slots(db: Session, venue_id: int, slot_date: date) -> list[SlotRead]:
    """지난 날짜도 허용하고 설정된 날짜 범위 안의 공간·일자별 칸을 반환한다."""
    today = get_today()
    _booking_date_range(today, (slot_date - today).days)

    venue = venue_repo.get_slot_context(db, venue_id)
    if venue is None:
        raise AppError("VENUE_NOT_FOUND", "공간을 찾을 수 없어요.", 404)
    return build_slots(
        venue["open_hour"],
        venue["close_hour"],
        slot_date,
        slot_repo.list_taken_hours(db, venue_id, slot_date),
        today=today,
        now=get_now(),
    )


def get_available_dates(db: Session, venue_id: int, offset: int, days: int) -> AvailableDatesRead:
    """영업시간의 빈 칸 총수와 연속 빈 칸을 날짜마다 집계한다. 지난 칸도 포함한다."""
    today = get_today()
    min_date, max_date = _booking_date_range(today, offset)
    start_date = today + timedelta(days=offset)
    day_count = min(days, (max_date - start_date).days + 1)
    end_date = start_date + timedelta(days=day_count - 1)
    venue = venue_repo.get_slot_context(db, venue_id)
    if venue is None:
        raise AppError("VENUE_NOT_FOUND", "공간을 찾을 수 없어요.", 404)

    taken_by_date = slot_repo.list_taken_hours_by_date(db, venue_id, start_date, end_date)
    dates = []
    for day_offset in range(day_count):
        slot_date = start_date + timedelta(days=day_offset)
        taken = taken_by_date.get(slot_date, set())
        free = run = longest_run = 0
        for hour in range(venue["open_hour"], venue["close_hour"]):
            if hour in taken:
                run = 0
            else:
                free += 1
                run += 1
                longest_run = max(longest_run, run)
        dates.append(
            AvailableDateRead(date=slot_date, free=free, bookable=longest_run >= venue["min_hours"])
        )
    return AvailableDatesRead(
        venue_id=venue_id,
        offset=offset,
        days=days,
        min_date=min_date,
        max_date=max_date,
        dates=dates,
    )
