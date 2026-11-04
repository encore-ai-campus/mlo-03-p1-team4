"""F-20·22 공간·날짜별 점유 시간 조회. 공개 조회 세션은 호출자가 전달한다."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reservation import ReservationSlot


def list_taken_hours(db: Session, venue_id: int, slot_date: date) -> set[int]:
    """예약 상태를 추측하지 않고 실제 점유 칸을 읽는다. 완료 예약의 칸도 유지된다."""
    query = select(ReservationSlot.slot_hour).where(
        ReservationSlot.venue_id == venue_id, ReservationSlot.slot_date == slot_date
    )
    return set(db.scalars(query))
