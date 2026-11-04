"""F-10 기준 정보 조회. 읽기 세션은 호출하는 쪽이 넘긴다."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Category


def list_categories(db: Session) -> list[Category]:
    """유형을 기본키 순으로 읽어 응답 순서를 일정하게 유지한다."""
    return list(db.scalars(select(Category).order_by(Category.category_id)))
