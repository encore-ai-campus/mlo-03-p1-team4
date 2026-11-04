"""F-10 유형 모델. 표 생성은 DB 마이그레이션이 담당한다."""

from sqlalchemy import SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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
