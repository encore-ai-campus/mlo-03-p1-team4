"""F-30·31 모의 결제 저장."""

from datetime import datetime

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
