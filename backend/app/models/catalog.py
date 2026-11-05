"""F-10·11 기준 정보 모델. 표 생성은 DB 마이그레이션이 담당한다."""

from sqlalchemy import Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Region(Base):
    """시·도와 시·군·구의 기준 목록. 공개 조회는 활성 공간이 있는 곳만 반환한다."""

    __tablename__ = "regions"
    __table_args__ = (
        UniqueConstraint("sido", "sigungu", name="uq_regions"),
        {"mysql_engine": "InnoDB"},
    )

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sido: Mapped[str] = mapped_column(String(20), nullable=False)
    sigungu: Mapped[str] = mapped_column(String(30), nullable=False)


class Category(Base):
    """0001_init.sql의 categories 표와 같은 매핑."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_categories_code"),
        {"mysql_engine": "InnoDB"},
    )

    category_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)


class Facility(Base):
    """검색 필터에 사용하는 전체 시설 목록."""

    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("name", name="uq_facilities_name"),
        {"mysql_engine": "InnoDB"},
    )

    facility_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
