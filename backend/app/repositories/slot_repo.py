"""F-12·20~22 점유 조회와 F-30~32 예약 칸 쓰기. 세션은 호출자가 전달한다."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reservation import Reservation, ReservationSlot


def create_many(
    db: Session,
    *,
    reservation_id: int,
    venue_id: int,
    slot_date: date,
    start_hour: int,
    end_hour: int,
) -> None:
    """연속 칸을 오름차순으로 INSERT·flush한다. DB 기본키가 경쟁의 승자를 정한다."""
    db.add_all(
        ReservationSlot(
            venue_id=venue_id,
            slot_date=slot_date,
            slot_hour=hour,
            reservation_id=reservation_id,
        )
        for hour in range(start_hour, end_hour)
    )
    db.flush()


def get_conflicts(
    db: Session,
    *,
    venue_id: int,
    slot_date: date,
    start_hour: int,
    end_hour: int,
) -> list[dict]:
    """경쟁 뒤 primary에서 겹친 칸과 소유자만 읽는다."""
    rows = db.execute(
        select(
            ReservationSlot.slot_hour,
            ReservationSlot.reservation_id,
            Reservation.user_id,
        )
        .join(Reservation, Reservation.reservation_id == ReservationSlot.reservation_id)
        .where(
            ReservationSlot.venue_id == venue_id,
            ReservationSlot.slot_date == slot_date,
            ReservationSlot.slot_hour >= start_hour,
            ReservationSlot.slot_hour < end_hour,
        )
        .order_by(ReservationSlot.slot_hour.asc())
    ).mappings()
    return [dict(row) for row in rows]


def list_taken_hours(db: Session, venue_id: int, slot_date: date) -> set[int]:
    """예약 상태를 추측하지 않고 실제 점유 칸을 읽는다. 완료 예약의 칸도 유지된다."""
    query = select(ReservationSlot.slot_hour).where(
        ReservationSlot.venue_id == venue_id, ReservationSlot.slot_date == slot_date
    )
    return set(db.scalars(query))


def list_taken_hours_by_date(
    db: Session, venue_id: int, start_date: date, end_date: date
) -> dict[date, set[int]]:
    """기간의 점유 칸을 한 번에 조회한다. 점유 없는 날짜는 서비스에서 빈 집합으로 다룬다."""
    query = select(ReservationSlot.slot_date, ReservationSlot.slot_hour).where(
        ReservationSlot.venue_id == venue_id,
        ReservationSlot.slot_date.between(start_date, end_date),
    )
    taken: dict[date, set[int]] = {}
    for slot_date, slot_hour in db.execute(query):
        taken.setdefault(slot_date, set()).add(slot_hour)
    return taken


def list_taken_hours_by_venues(
    db: Session, venue_ids: list[int], slot_date: date
) -> dict[int, set[int]]:
    """검색 결과 공간의 한 날짜 점유 칸을 공간별로 한 번에 읽는다."""
    if not venue_ids:
        return {}
    query = select(ReservationSlot.venue_id, ReservationSlot.slot_hour).where(
        ReservationSlot.venue_id.in_(venue_ids), ReservationSlot.slot_date == slot_date
    )
    taken: dict[int, set[int]] = {}
    for venue_id, slot_hour in db.execute(query):
        taken.setdefault(venue_id, set()).add(slot_hour)
    return taken
