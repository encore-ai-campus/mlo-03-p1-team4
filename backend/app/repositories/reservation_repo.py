"""F-04·30·40·50·51 예약 생성·내역·탈퇴·후기 조회 지원. 트랜잭션은 서비스가 관리한다."""

from datetime import date, datetime

from sqlalchemy import Select, and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.models.catalog import Category, Region
from app.models.reservation import Payment, Reservation, ReservationSlot
from app.models.venue import Venue


def find_generator_booking(db: Session, *, user_id: int, body, created_at: datetime) -> dict | None:
    """#75 커밋 직후 중단된 작업을 취소·완료 상태까지 포함해 찾는다."""
    row = (
        db.execute(
            select(
                Reservation.reservation_id,
                Reservation.total_price,
                Payment.method,
                Payment.paid_at,
            )
            .join(Payment, Payment.reservation_id == Reservation.reservation_id)
            .where(
                Reservation.user_id == user_id,
                Reservation.is_synthetic.is_(True),
                Reservation.venue_id == body.venue_id,
                Reservation.reserve_date == body.date,
                Reservation.start_hour == body.start_hour,
                Reservation.end_hour == body.start_hour + body.hours,
                Reservation.headcount == body.headcount,
                Reservation.created_at == created_at,
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def review_context_query(*, active_only: bool = True) -> Select:
    """A가 후기·회원과 결합할 예약당 한 행의 조회식만 만든다(#43).

    공개 후기는 기본값, 내 후기는 False로 비활성 공간 기록도 포함한다.
    세션 선택·실행·트랜잭션과 후기 필터·정렬·페이지 처리는 A가 담당한다.
    """
    query = (
        select(
            Reservation.reservation_id.label("reservation_id"),
            Venue.venue_id.label("venue_id"),
            Venue.name.label("venue_name"),
            Category.code.label("category"),
        )
        .select_from(Reservation)
        .join(Venue, Venue.venue_id == Reservation.venue_id)
        .join(Category, Category.category_id == Venue.category_id)
    )
    if active_only:
        query = query.where(Venue.is_active.is_(True))
    return query


def create(
    db: Session,
    *,
    user_id: int,
    venue_id: int,
    reserve_date: date,
    start_hour: int,
    end_hour: int,
    headcount: int,
    total_price: int,
    status: str,
    is_synthetic: bool,
    created_at: datetime,
) -> Reservation:
    """예약 행을 INSERT·flush해 복합 외래키에 쓸 ID를 확보한다."""
    reservation = Reservation(
        user_id=user_id,
        venue_id=venue_id,
        reserve_date=reserve_date,
        start_hour=start_hour,
        end_hour=end_hour,
        headcount=headcount,
        total_price=total_price,
        status=status,
        is_synthetic=is_synthetic,
        created_at=created_at,
    )
    db.add(reservation)
    db.flush()
    return reservation


def find_recent_matching(
    db: Session,
    *,
    user_id: int,
    venue_id: int,
    reserve_date: date,
    start_hour: int,
    end_hour: int,
    created_after: datetime,
    created_before: datetime,
) -> dict | None:
    """10분 안에 같은 이용 시간으로 만든 본인의 유효한 예약과 결제를 찾는다."""
    row = (
        db.execute(
            select(
                Reservation.reservation_id,
                Reservation.status,
                Reservation.venue_id,
                Reservation.reserve_date,
                Reservation.start_hour,
                Reservation.end_hour,
                Reservation.headcount,
                Reservation.total_price,
                Payment.method,
                Payment.status.label("payment_status"),
                Payment.paid_at,
            )
            .join(Payment, Payment.reservation_id == Reservation.reservation_id)
            .where(
                Reservation.user_id == user_id,
                Reservation.status.in_(("confirmed", "completed")),
                Payment.status == "paid",
                Reservation.venue_id == venue_id,
                Reservation.reserve_date == reserve_date,
                Reservation.start_hour == start_hour,
                Reservation.end_hour == end_hour,
                Reservation.created_at >= created_after,
                Reservation.created_at <= created_before,
            )
            .order_by(Reservation.reservation_id.asc())
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def count_cancellable(db: Session, user_id: int) -> int:
    """primary에서 최신 행을 잠가 시작 전 confirmed 예약 수를 센다."""
    now = get_now()
    query = (
        select(Reservation.reservation_id)
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
        .with_for_update()
    )
    return len(db.scalars(query).all())


def count_owned(db: Session, *, user_id: int, status: str | None = None) -> int:
    """본인 예약의 전체 건수를 선택 상태와 함께 센다."""
    conditions = [Reservation.user_id == user_id]
    if status is not None:
        conditions.append(Reservation.status == status)
    return int(db.scalar(select(func.count()).select_from(Reservation).where(*conditions)) or 0)


def _owned_read_query():
    """목록·상세 응답에 필요한 예약·결제·공간 기준 정보를 예약당 한 행으로 읽는다."""
    return (
        select(
            Reservation.reservation_id.label("reservation_id"),
            Reservation.venue_id.label("venue_id"),
            Reservation.reserve_date.label("reserve_date"),
            Reservation.start_hour.label("start_hour"),
            Reservation.end_hour.label("end_hour"),
            Reservation.headcount.label("headcount"),
            Reservation.total_price.label("total_price"),
            Reservation.status.label("status"),
            Reservation.created_at.label("created_at"),
            Payment.method.label("payment_method"),
            Payment.status.label("payment_status"),
            Payment.paid_at.label("paid_at"),
            Payment.refunded_at.label("refunded_at"),
            Venue.name.label("venue_name"),
            Category.code.label("category_code"),
            Category.name.label("category_name"),
            Region.sido.label("region_sido"),
            Region.sigungu.label("region_sigungu"),
        )
        .select_from(Reservation)
        .join(Payment, Payment.reservation_id == Reservation.reservation_id)
        .join(Venue, Venue.venue_id == Reservation.venue_id)
        .join(Category, Category.category_id == Venue.category_id)
        .join(Region, Region.region_id == Venue.region_id)
    )


def list_owned(
    db: Session,
    *,
    user_id: int,
    status: str | None,
    offset: int,
    limit: int,
) -> list[dict]:
    """본인 예약을 최신 생성순으로 페이지 조회한다. 비활성 공간의 이력도 포함한다."""
    conditions = [Reservation.user_id == user_id]
    if status is not None:
        conditions.append(Reservation.status == status)
    rows = db.execute(
        _owned_read_query()
        .where(*conditions)
        .order_by(Reservation.created_at.desc(), Reservation.reservation_id.desc())
        .offset(offset)
        .limit(limit)
    ).mappings()
    return [dict(row) for row in rows]


def get_owned_detail(db: Session, *, user_id: int, reservation_id: int) -> dict | None:
    """본인 예약 한 건을 읽는다. 타인·없는 예약은 같은 404 처리를 위해 None이다."""
    row = (
        db.execute(
            _owned_read_query().where(
                Reservation.user_id == user_id,
                Reservation.reservation_id == reservation_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


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


def get_owned_for_update(db: Session, *, user_id: int, reservation_id: int) -> Reservation | None:
    """취소 직렬화를 위해 본인 예약 행을 primary 트랜잭션에서 잠근다."""
    return db.scalar(
        select(Reservation)
        .where(Reservation.reservation_id == reservation_id, Reservation.user_id == user_id)
        .with_for_update()
    )


def delete_slots(db: Session, *, reservation_id: int) -> int:
    """취소된 예약의 시간 칸만 지우고 삭제한 행 수를 반환한다."""
    return db.execute(
        delete(ReservationSlot).where(ReservationSlot.reservation_id == reservation_id)
    ).rowcount


def complete_ended(db: Session, *, today: date, now_hour: int) -> int:
    """종료 시각이 지난 확정 예약을 한 번에 완료 처리한다.

    상태 조건을 UPDATE에 포함해 취소와 경합해도 취소된 예약을 되살리지 않는다.
    완료된 예약의 시간 칸은 점유율 분석을 위해 유지한다.
    """
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.status == "confirmed",
            or_(
                Reservation.reserve_date < today,
                and_(Reservation.reserve_date == today, Reservation.end_hour <= now_hour),
            ),
        )
        .values(status="completed")
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)
