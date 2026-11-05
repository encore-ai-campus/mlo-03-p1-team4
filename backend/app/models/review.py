"""F-50: reviews DDL 대응 모델. 예약 모델은 B가 제공한다.

사용: 후기 리포지토리가 reviews 행을 읽고 갱신한다.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("reservation_id", name="uq_review_resv"),
        Index("ix_review_user", "user_id", "created_at"),
        Index("ix_review_created", "created_at"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
    )

    review_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.reservation_id", name="fk_review_resv"),
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", name="fk_review_user")
    )
    rating: Mapped[int] = mapped_column(TINYINT)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
