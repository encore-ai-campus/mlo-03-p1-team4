"""F-01~04: users DDL 대응 모델.

사용: 회원 리포지토리가 users 행을 읽고 갱신한다.
"""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("birth REGEXP '^[0-9]{6}$'", name="ck_users_birth"),
        CheckConstraint("gender_digit IN ('1','2','3','4')", name="ck_users_gender"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birth: Mapped[str] = mapped_column(CHAR(6))
    gender_digit: Mapped[str] = mapped_column(CHAR(1))
    marketing_agreed: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    terms_agreed_at: Mapped[datetime] = mapped_column(DateTime)
    privacy_agreed_at: Mapped[datetime] = mapped_column(DateTime)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
