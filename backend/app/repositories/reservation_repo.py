"""F-04·50: A에 제공하는 탈퇴 전 예약 수·소유권 조회. 트랜잭션은 호출자가 관리한다."""

from datetime import date, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.models.reservation import Reservation


def count_cancellable(db: Session, user_id: int) -> int:
    """primary 세션에서 시작 전 confirmed 예약 수를 센다. 시작 정각은 제외한다."""
    now = get_now()
    query = (
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.user_id == user_id,
            Reservation.status == "confirmed",
            or_(
                Reservation.reserve_date > now.date(),
                and_(
                    Reservation.reserve_date == now.date(),
                    Reservation.start_hour > now.hour,
                ),
            ),
        )
    )
    return int(db.scalar(query) or 0)


def get_owned(
    db: Session, user_id: int, reservation_id: int
) -> tuple[int, int, date, int, int, str, datetime] | None:
    """본인 예약의 합의된 7개 값을 반환한다. 호출자는 primary 세션을 넘긴다.

    상태·후기 기한·중복 후기 판정은 A 서비스가 담당하므로 여기서 걸러내지 않는다.
    없는 예약과 타인 예약은 모두 None이다.
    """
    row = db.execute(
        select(
            Reservation.reservation_id,
            Reservation.venue_id,
            Reservation.reserve_date,
            Reservation.start_hour,
            Reservation.end_hour,
            Reservation.status,
            Reservation.created_at,
        ).where(Reservation.reservation_id == reservation_id, Reservation.user_id == user_id)
    ).one_or_none()
    return tuple(row) if row is not None else None
