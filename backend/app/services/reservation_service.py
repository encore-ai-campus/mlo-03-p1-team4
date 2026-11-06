"""F-30~35 예약·취소·완료 배치와 F-40 내 예약 조회."""

import logging
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import as_korean_time, get_now, get_today
from app.core.config import get_settings
from app.core.errors import AppError, fail
from app.core.event_context import ClientEventContext, client_event_context
from app.core.events import log_event
from app.core.metrics import reservation_counter
from app.core.pagination import Pagination, paginate
from app.repositories import (
    payment_repo,
    reservation_repo,
    review_repo,
    slot_repo,
    user_repo,
    venue_repo,
)
from app.schemas.reservations import (
    PaymentRead,
    ReservationCancelPaymentRead,
    ReservationCancelRead,
    ReservationCreate,
    ReservationCreateRead,
    ReservationEventContext,
    ReservationPaymentRead,
    ReservationRead,
    ReservationStatus,
    ReservationVenueRead,
)

_METHODS = frozenset({"transfer", "card", "phone"})
_DUPLICATE_WINDOW = timedelta(minutes=10)
_OUT_OF_RANGE_MESSAGE = "예약할 수 없는 날짜나 시간이에요."


def _event_product(*, venue, day, start_hour, end_hour, headcount, price_per_hour):
    """primary 공간 정보와 검증·저장된 이용 조건으로 상품 한 건을 만든다."""
    return [
        {
            "product_id": str(venue["venue_id"]),
            "product_name": venue["name"],
            "price": {
                "currency": "KRW",
                "displayed_amount_minor": price_per_hour,
                "displayed_text": f"{price_per_hour:,}원 / 시간",
                "billing_unit": "hour",
            },
            "rental_conditions": {
                "start_at": as_korean_time(datetime.combine(day, time(start_hour))),
                "end_at": as_korean_time(datetime.combine(day, time(end_hour))),
                "timezone": "Asia/Seoul",
                "guest_count": headcount,
                "option_ids": [],
            },
        }
    ]


def _log_reservation_event(*args, event_context=None, **kwargs):
    """문맥을 복원하고, 문맥 조립·기록 실패가 예약 결과로 전파되지 않게 한다."""
    try:
        context = None
        if event_context is not None:
            user = event_context.user or {}
            context = ClientEventContext(
                occurred_at=None,
                anonymous_id=user.get("anonymous_id"),
                session_sequence=user.get("session_sequence"),
                browser_context=event_context.model_dump(exclude={"user"}),
            )
        token = client_event_context.set(context)
        try:
            log_event(*args, **kwargs)
        finally:
            client_event_context.reset(token)
    except Exception:
        logging.getLogger("spacecube.app").error("예약 이벤트 처리 실패, 업무 결과는 유지")


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


def _lock_active_user(db: Session, user_id: int) -> None:
    """탈퇴와 예약을 같은 회원 행 잠금으로 직렬화한다."""
    if user_repo.get_active(db, user_id, for_update=True) is None:
        raise fail("UNAUTHORIZED", 401)


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
        "reason": "SLOT_TAKEN",
        "date": body.date.isoformat(),
        "start_hour": body.start_hour,
        "hours": body.hours,
    }
    _log_reservation_event(
        session_id,
        user_id,
        "reservation_conflict",
        venue_id=body.venue_id,
        category=venue["category_code"],
        payload=log_event_payload,
        is_synthetic=is_synthetic,
        products=_event_product(
            venue=venue,
            day=body.date,
            start_hour=body.start_hour,
            end_hour=end_hour,
            headcount=body.headcount,
            price_per_hour=venue["price_per_hour"],
        ),
        event_context=body.event_context,
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
    try:
        # 인증 조회 뒤 탈퇴가 끝났거나 동시에 진행 중일 수 있으므로 primary에서 다시 잠근다.
        _lock_active_user(db, user_id)
        venue_row = venue_repo.get_booking_info(db, body.venue_id)
        if venue_row is None:
            raise AppError("VENUE_NOT_FOUND", "공간을 찾을 수 없어요.", 404)
        venue = dict(venue_row)
        end_hour, status, now, _ = _validate(body, venue=venue)
        total_price = venue["price_per_hour"] * body.hours

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
                # rollback이 회원 잠금도 해제하므로 재시도 응답 전에 다시 확인한다.
                _lock_active_user(db, user_id)
                duplicate = _handle_slot_conflict(
                    db,
                    user_id=user_id,
                    venue=venue,
                    body=body,
                    end_hour=end_hour,
                    session_id=session_id,
                    is_synthetic=is_synthetic,
                )
                db.commit()
                return duplicate, 200
            except Exception:
                db.rollback()
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

    _log_reservation_event(
        session_id,
        user_id,
        "reservation_complete",
        venue_id=body.venue_id,
        category=venue["category_code"],
        payload={
            "date": body.date.isoformat(),
            "start_hour": body.start_hour,
            "hours": body.hours,
        },
        is_synthetic=is_synthetic,
        products=_event_product(
            venue=venue,
            day=reservation.reserve_date,
            start_hour=reservation.start_hour,
            end_hour=reservation.end_hour,
            headcount=reservation.headcount,
            price_per_hour=total_price // (reservation.end_hour - reservation.start_hour),
        ),
        event_context=body.event_context,
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


def _as_owned_read(
    row: dict, *, image: str, now: datetime, review_id: int | None
) -> ReservationRead:
    """예약 당시 금액과 전달받은 후기 ID(삭제 포함)를 그대로 응답한다."""
    starts_at = datetime.combine(row["reserve_date"], time(row["start_hour"]))
    return ReservationRead(
        reservation_id=row["reservation_id"],
        status=row["status"],
        venue_id=row["venue_id"],
        date=row["reserve_date"],
        start_hour=row["start_hour"],
        end_hour=row["end_hour"],
        headcount=row["headcount"],
        total_price=row["total_price"],
        created_at=as_korean_time(row["created_at"]),
        payment=ReservationPaymentRead(
            method=row["payment_method"],
            status=row["payment_status"],
            paid_at=as_korean_time(row["paid_at"]),
            refunded_at=(
                as_korean_time(row["refunded_at"]) if row["refunded_at"] is not None else None
            ),
        ),
        venue=ReservationVenueRead(
            venue_id=row["venue_id"],
            name=row["venue_name"],
            category={"code": row["category_code"], "name": row["category_name"]},
            region={"sido": row["region_sido"], "sigungu": row["region_sigungu"]},
            image=image,
        ),
        can_cancel=row["status"] == "confirmed" and starts_at > now,
        review_id=review_id,
    )


def get_my_reservations(
    db: Session,
    *,
    user_id: int,
    status: ReservationStatus | None,
    pagination: Pagination,
) -> dict:
    """본인 예약을 primary에서 필터·페이지 조회하고 페이지 그림만 묶어 읽는다."""
    total = reservation_repo.count_owned(db, user_id=user_id, status=status)
    rows = reservation_repo.list_owned(
        db,
        user_id=user_id,
        status=status,
        offset=pagination.offset,
        limit=pagination.size,
    )
    images = venue_repo.list_images_by_venues(db, [row["venue_id"] for row in rows])
    review_ids = review_repo.get_review_ids(db, [row["reservation_id"] for row in rows])
    now = get_now()
    items = [
        _as_owned_read(
            row,
            image=(images.get(row["venue_id"]) or ["art:group-0"])[0],
            now=now,
            review_id=review_ids.get(row["reservation_id"]),
        )
        for row in rows
    ]
    return paginate(items, pagination.page, pagination.size, total)


def get_my_reservation(
    db: Session,
    *,
    user_id: int,
    reservation_id: int,
) -> ReservationRead:
    """본인 예약 상세를 조회한다. 읽기 시 상태는 변경하지 않는다."""
    row = reservation_repo.get_owned_detail(
        db,
        user_id=user_id,
        reservation_id=reservation_id,
    )
    if row is None:
        raise fail("RESERVATION_NOT_FOUND", 404)
    images = venue_repo.list_images_by_venues(db, [row["venue_id"]])
    review_ids = review_repo.get_review_ids(db, [row["reservation_id"]])
    return _as_owned_read(
        row,
        image=(images.get(row["venue_id"]) or ["art:group-0"])[0],
        now=get_now(),
        review_id=review_ids.get(row["reservation_id"]),
    )


def cancel_reservation(
    db: Session,
    *,
    user_id: int,
    reservation_id: int,
    session_id: str | None,
    event_context: ReservationEventContext | None = None,
) -> ReservationCancelRead:
    """시작 전 본인 예약을 잠그고 칸 반납·전액 모의 환불을 한 번에 커밋한다."""
    try:
        reservation = reservation_repo.get_owned_for_update(
            db, user_id=user_id, reservation_id=reservation_id
        )
        if reservation is None:
            raise AppError("RESERVATION_NOT_FOUND", "예약을 찾을 수 없어요.", 404)
        if reservation.status == "cancelled":
            raise AppError("ALREADY_CANCELLED", "이미 취소된 예약이에요.", 409)

        now = get_now()
        starts_at = datetime.combine(reservation.reserve_date, time(reservation.start_hour))
        if reservation.status != "confirmed" or starts_at <= now:
            raise AppError("NOT_CANCELLABLE", "이용이 시작된 예약은 취소할 수 없어요.", 409)

        # 비활성 공간도 취소할 수 있으므로 활성 여부로 거르지 않고 유형을 읽는다.
        venue = venue_repo.get_booking_info(db, reservation.venue_id)
        if venue is None:
            raise RuntimeError("예약에 연결된 공간 정보가 없습니다.")

        reservation.status = "cancelled"
        if reservation_repo.delete_slots(db, reservation_id=reservation_id) <= 0:
            raise RuntimeError("확정 예약에 연결된 시간 칸이 없습니다.")
        payment = payment_repo.refund(db, reservation_id=reservation_id, refunded_at=now)
        if payment is None:
            raise RuntimeError("예약에 연결된 결제 정보가 없습니다.")
        db.commit()
    except Exception:
        db.rollback()
        raise

    _log_reservation_event(
        session_id,
        user_id,
        "reservation_cancel_complete",
        venue_id=reservation.venue_id,
        category=venue["category_code"],
        payload={"reservation_id": reservation_id},
        is_synthetic=reservation.is_synthetic,
        products=_event_product(
            venue=venue,
            day=reservation.reserve_date,
            start_hour=reservation.start_hour,
            end_hour=reservation.end_hour,
            headcount=reservation.headcount,
            price_per_hour=reservation.total_price
            // (reservation.end_hour - reservation.start_hour),
        ),
        event_context=event_context,
    )
    reservation_counter.labels(result="cancel").inc()
    return ReservationCancelRead(
        reservation_id=reservation_id,
        status="cancelled",
        total_price=reservation.total_price,
        payment=ReservationCancelPaymentRead(
            method=payment.method,
            status="refunded",
            paid_at=as_korean_time(payment.paid_at),
            refunded_at=as_korean_time(payment.refunded_at),
        ),
        can_cancel=False,
    )


def complete_ended_reservations(db: Session) -> int:
    """현재 한국 시각을 한 번 읽고 종료된 예약을 완료 처리해 커밋한다."""
    now = get_now()
    try:
        completed = reservation_repo.complete_ended(db, today=now.date(), now_hour=now.hour)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return completed


def complete_generator_reservation(db: Session, *, user_id: int, reservation_id: int) -> None:
    """#75의 해당 가상 예약만 완료한다. 다른 회원·운영 예약은 갱신하지 않는다."""
    try:
        reservation = reservation_repo.get_owned_for_update(
            db, user_id=user_id, reservation_id=reservation_id
        )
        if reservation is None or not reservation.is_synthetic:
            raise ValueError("생성기 소유의 가상 예약이 아닙니다.")
        ends_at = datetime.combine(reservation.reserve_date, time(reservation.end_hour))
        if ends_at > get_now() or reservation.status == "cancelled":
            raise ValueError("완료 처리할 수 없는 예약입니다.")
        reservation.status = "completed"
        db.commit()
    except Exception:
        db.rollback()
        raise
