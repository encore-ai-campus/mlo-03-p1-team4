"""F-30~32 예약 검증·단일 예약/결제 트랜잭션과 경쟁 처리."""

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import as_korean_time, get_now, get_today
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.events import log_event
from app.core.metrics import reservation_counter
from app.repositories import payment_repo, reservation_repo, slot_repo, venue_repo
from app.schemas.reservations import PaymentRead, ReservationCreate, ReservationCreateRead

_METHODS = frozenset({"transfer", "card", "phone"})
_DUPLICATE_WINDOW = timedelta(minutes=10)
_OUT_OF_RANGE_MESSAGE = "예약할 수 없는 날짜나 시간이에요."


def _range_dates() -> tuple[date, date]:
    today = get_today()
    settings = get_settings()
    return (
        today - timedelta(days=settings.booking_past_days),
        today + timedelta(days=settings.booking_future_days),
    )


def _out_of_range(reason: Literal["date", "hours", "min_hours", "max_hours"], min_hours: int):
    min_date, max_date = _range_dates()
    detail = {"reason": reason, "min_date": min_date.isoformat(), "max_date": max_date.isoformat()}
    if reason != "date":
        detail["min_hours"] = min_hours
    raise AppError("OUT_OF_RANGE", _OUT_OF_RANGE_MESSAGE, 400, detail)


def _validate(
    body: ReservationCreate,
    *,
    venue: dict,
) -> tuple[int, str, datetime, datetime]:
    """쓰기 전에 공간·날짜·시간·인원·수단을 검증한다."""
    if not venue["is_active"]:
        raise AppError("VENUE_NOT_FOUND", "공간을 찾을 수 없어요.", 404)

    min_date, max_date = _range_dates()
    if body.date < min_date or body.date > max_date:
        _out_of_range("date", venue["min_hours"])

    if body.hours < venue["min_hours"]:
        _out_of_range("min_hours", venue["min_hours"])
    if body.hours > 4:
        _out_of_range("max_hours", venue["min_hours"])
    end_hour = body.start_hour + body.hours
    if (
        body.start_hour < venue["open_hour"]
        or body.start_hour >= venue["close_hour"]
        or end_hour > venue["close_hour"]
    ):
        _out_of_range("hours", venue["min_hours"])

    if body.headcount > venue["capacity_max"]:
        maximum = venue["capacity_max"]
        raise AppError(
            "TOO_MANY_PEOPLE",
            f"이 공간은 최대 {maximum}명까지예요.",
            400,
            {"capacity_max": maximum},
        )
    if body.method not in _METHODS:
        raise AppError("INVALID_METHOD", "결제 수단을 다시 골라 주세요.", 400)

    now = get_now()
    ends_at = datetime.combine(body.date, time(end_hour))
    status = "completed" if ends_at <= now else "confirmed"
    return end_hour, status, now, ends_at


def _as_response(row: dict) -> ReservationCreateRead:
    return ReservationCreateRead(
        reservation_id=row["reservation_id"],
        status=row["status"],
        venue_id=row["venue_id"],
        date=row["reserve_date"],
        start_hour=row["start_hour"],
        end_hour=row["end_hour"],
        headcount=row["headcount"],
        total_price=row["total_price"],
        payment=PaymentRead(
            method=row["method"],
            status=row["payment_status"],
            paid_at=as_korean_time(row["paid_at"]),
        ),
    )


def _duplicate_key(error: IntegrityError) -> bool:
    arguments = getattr(error.orig, "args", ())
    return bool(arguments) and arguments[0] == 1062


def _slot_taken(detail: dict, *, mine: bool = False) -> AppError:
    message = (
        "이미 내 예약과 겹치는 시간이에요." if mine else "다른 분이 먼저 결제한 시간이 있어요."
    )
    return AppError("SLOT_TAKEN", message, 409, detail)


def _handle_slot_conflict(
    db: Session,
    *,
    user_id: int,
    venue: dict,
    body: ReservationCreate,
    end_hour: int,
    session_id: str | None,
    is_synthetic: bool,
) -> ReservationCreateRead:
    """롤백 후 primary에서 재시도 예약과 충돌 소유권을 판정한다."""
    now = get_now()
    duplicate = reservation_repo.find_recent_matching(
        db,
        user_id=user_id,
        venue_id=body.venue_id,
        reserve_date=body.date,
        start_hour=body.start_hour,
        end_hour=end_hour,
        created_after=now - _DUPLICATE_WINDOW,
        created_before=now,
    )
    if duplicate is not None:
        # headcount·수단은 최초 결제 내용을 보존하고 새 결제나 이벤트를 만들지 않는다.
        return _as_response(duplicate)

    conflicts = slot_repo.get_conflicts(
        db,
        venue_id=body.venue_id,
        slot_date=body.date,
        start_hour=body.start_hour,
        end_hour=end_hour,
    )
    detail = {"slots": [row["slot_hour"] for row in conflicts]}
    if conflicts and all(row["user_id"] == user_id for row in conflicts):
        detail.update(
            mine=True,
            reservation_id=min(row["reservation_id"] for row in conflicts),
        )
        raise _slot_taken(detail, mine=True)

    log_event_payload = {
        "date": body.date.isoformat(),
        "start_hour": body.start_hour,
        "hours": body.hours,
    }
    log_event(
        session_id,
        user_id,
        "reserve_conflict",
        venue_id=body.venue_id,
        category=venue["category_code"],
        payload=log_event_payload,
        is_synthetic=is_synthetic,
    )
    reservation_counter.labels(result="conflict").inc()
    raise _slot_taken(detail)


def create_reservation(
    db: Session,
    body: ReservationCreate,
    *,
    user_id: int,
    session_id: str | None,
    is_synthetic: bool,
) -> tuple[ReservationCreateRead, int]:
    """검증 후 예약·칸·모의 결제를 커밋하고, 슬롯 경쟁만 명세대로 409 처리한다."""
    venue_row = venue_repo.get_booking_info(db, body.venue_id)
    if venue_row is None:
        raise AppError("VENUE_NOT_FOUND", "공간을 찾을 수 없어요.", 404)
    venue = dict(venue_row)
    end_hour, status, now, _ = _validate(body, venue=venue)
    total_price = venue["price_per_hour"] * body.hours

    try:
        reservation = reservation_repo.create(
            db,
            user_id=user_id,
            venue_id=body.venue_id,
            reserve_date=body.date,
            start_hour=body.start_hour,
            end_hour=end_hour,
            headcount=body.headcount,
            total_price=total_price,
            status=status,
            is_synthetic=is_synthetic,
            created_at=now,
        )
        try:
            slot_repo.create_many(
                db,
                reservation_id=reservation.reservation_id,
                venue_id=body.venue_id,
                slot_date=body.date,
                start_hour=body.start_hour,
                end_hour=end_hour,
            )
        except IntegrityError as error:
            if not _duplicate_key(error):
                raise
            db.rollback()
            try:
                return (
                    _handle_slot_conflict(
                        db,
                        user_id=user_id,
                        venue=venue,
                        body=body,
                        end_hour=end_hour,
                        session_id=session_id,
                        is_synthetic=is_synthetic,
                    ),
                    200,
                )
            except AppError:
                raise

        payment = payment_repo.create(
            db,
            reservation_id=reservation.reservation_id,
            method=body.method,
            paid_at=now,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    log_event(
        session_id,
        user_id,
        "reserve_ok",
        venue_id=body.venue_id,
        category=venue["category_code"],
        payload={
            "date": body.date.isoformat(),
            "start_hour": body.start_hour,
            "hours": body.hours,
        },
        is_synthetic=is_synthetic,
    )
    reservation_counter.labels(result="ok").inc()
    return (
        ReservationCreateRead(
            reservation_id=reservation.reservation_id,
            status=reservation.status,
            venue_id=body.venue_id,
            date=body.date,
            start_hour=body.start_hour,
            end_hour=end_hour,
            headcount=body.headcount,
            total_price=total_price,
            payment=PaymentRead(
                method=payment.method,
                status=payment.status,
                paid_at=as_korean_time(payment.paid_at),
            ),
        ),
        201,
    )
