"""F-30·31 모의 결제 저장."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reservation import Payment


def create(db: Session, *, reservation_id: int, method: str, paid_at: datetime) -> Payment:
    """예약 트랜잭션 안에 완료된 모의 결제를 만든다."""
    payment = Payment(
        reservation_id=reservation_id,
        method=method,
        status="paid",
        paid_at=paid_at,
    )
    db.add(payment)
    db.flush()
    return payment


def refund(db: Session, *, reservation_id: int, refunded_at: datetime) -> Payment | None:
    """예약 결제를 잠그고 전액 모의 환불 상태로 바꾼다."""
    payment = db.scalar(
        select(Payment).where(Payment.reservation_id == reservation_id).with_for_update()
    )
    if payment is None:
        return None
    payment.status = "refunded"
    payment.refunded_at = refunded_at
    db.flush()
    return payment
