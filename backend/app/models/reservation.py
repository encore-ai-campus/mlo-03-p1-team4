"""F-30~35: 예약·시간 칸·결제 모델. 표 생성은 DB 마이그레이션이 담당한다."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import ENUM, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Reservation(Base):
    """예약 본체. 생성·취소의 트랜잭션과 상태 전이는 서비스가 담당한다."""

    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("reservation_id", "venue_id", "reserve_date", name="uq_resv_venue_date"),
        Index("ix_resv_user", "user_id", "status", "reserve_date"),
        Index("ix_resv_venue_date", "venue_id", "reserve_date"),
        Index("ix_resv_status_date", "status", "reserve_date"),
        Index("ix_resv_created", "created_at", "venue_id"),
        CheckConstraint(
            "start_hour BETWEEN 9 AND 22 AND end_hour <= 23 AND end_hour > start_hour "
            "AND end_hour - start_hour <= 4",
            name="ck_resv_hours",
        ),
        CheckConstraint("headcount >= 1", name="ck_resv_head"),
        CheckConstraint("total_price >= 0", name="ck_resv_price"),
        {"mysql_engine": "InnoDB"},
    )

    reservation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", name="fk_resv_user")
    )
    venue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("venues.venue_id", name="fk_resv_venue")
    )
    reserve_date: Mapped[date] = mapped_column(Date)
    start_hour: Mapped[int] = mapped_column(TINYINT)
    end_hour: Mapped[int] = mapped_column(TINYINT)
    headcount: Mapped[int] = mapped_column(SmallInteger)
    total_price: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        ENUM("confirmed", "completed", "cancelled"), server_default=text("'confirmed'")
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ReservationSlot(Base):
    """중복 예약은 공간·날짜·시간의 복합 기본키가 차단한다."""

    __tablename__ = "reservation_slots"
    __table_args__ = (
        UniqueConstraint("reservation_id", "slot_hour", name="uq_slot_resv"),
        CheckConstraint("slot_hour BETWEEN 9 AND 22", name="ck_slot_hour"),
        ForeignKeyConstraint(
            ["reservation_id", "venue_id", "slot_date"],
            ["reservations.reservation_id", "reservations.venue_id", "reservations.reserve_date"],
            name="fk_slot_resv",
            ondelete="CASCADE",
        ),
        {"mysql_engine": "InnoDB"},
    )

    venue_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    slot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    slot_hour: Mapped[int] = mapped_column(TINYINT, primary_key=True)
    reservation_id: Mapped[int] = mapped_column(BigInteger)


class Payment(Base):
    """예약당 모의 결제 한 건. 환불 상태와 환불 시각은 함께 바뀐다."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("reservation_id", name="uq_pay_resv"),
        CheckConstraint("(status = 'refunded') = (refunded_at IS NOT NULL)", name="ck_pay_refund"),
        {"mysql_engine": "InnoDB"},
    )

    payment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reservations.reservation_id", name="fk_pay_resv")
    )
    method: Mapped[str] = mapped_column(ENUM("transfer", "card", "phone"))
    status: Mapped[str] = mapped_column(ENUM("paid", "refunded"), server_default=text("'paid'"))
    paid_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
