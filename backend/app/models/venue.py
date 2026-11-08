"""F-20 공간·시설 연결·이미지 모델. 표 생성은 기존 DB 마이그레이션이 담당한다."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Venue(Base):
    """예약 단위인 공간. 컬럼·제약·인덱스는 0001_init.sql과 맞춘다."""

    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint("source_site", "source_id", name="uq_venues_source"),
        Index("ix_venues_category", "category_id", "is_active"),
        Index("ix_venues_region", "region_id", "is_active"),
        Index("ix_venues_created", "created_at"),
        CheckConstraint("capacity_max >= 1", name="ck_venues_capacity"),
        CheckConstraint("price_per_hour > 0", name="ck_venues_price"),
        CheckConstraint(
            "open_hour BETWEEN 9 AND 22 AND close_hour BETWEEN 10 AND 23 AND close_hour > open_hour",
            name="ck_venues_hours",
        ),
        CheckConstraint("min_hours BETWEEN 1 AND 4", name="ck_venues_min"),
        {"mysql_engine": "InnoDB"},
    )

    venue_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.region_id", name="fk_venues_region")
    )
    category_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("categories.category_id", name="fk_venues_category")
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity_max: Mapped[int] = mapped_column(SmallInteger)
    price_per_hour: Mapped[int] = mapped_column(Integer)
    min_hours: Mapped[int] = mapped_column(TINYINT, server_default=text("1"))
    open_hour: Mapped[int] = mapped_column(TINYINT, server_default=text("9"))
    close_hour: Mapped[int] = mapped_column(TINYINT, server_default=text("23"))
    source_site: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class VenueFacility(Base):
    """공간과 시설의 복합 기본키."""

    __tablename__ = "venue_facilities"
    __table_args__ = (
        Index("ix_vf_facility", "facility_id", "venue_id"),
        {"mysql_engine": "InnoDB"},
    )

    venue_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("venues.venue_id", name="fk_vf_venue", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    facility_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("facilities.facility_id", name="fk_vf_facility"),
        primary_key=True,
        autoincrement=False,
    )


class VenueImage(Base):
    """공간 그림과 갤러리 순서. 사진 URL 대신 art 식별자를 저장한다."""

    __tablename__ = "venue_images"
    __table_args__ = (
        Index("ix_vi_venue", "venue_id", "sort_order"),
        {"mysql_engine": "InnoDB"},
    )

    image_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("venues.venue_id", name="fk_vi_venue", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(TINYINT, server_default=text("0"))
