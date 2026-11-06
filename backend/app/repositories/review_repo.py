"""후기 SQL. B 소유 테이블은 직접 조회하지 않는다.

사용: 후기 서비스가 후기 테이블 접근과 목록 조회를 위임한다.
"""

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.user import User
from app.repositories import reservation_repo


def get_by_reservation(db: Session, reservation_id: int):
    # 삭제된 후기까지 확인한다. 예약당 1개 UNIQUE는 소프트 삭제 뒤에도 유지된다.
    return db.scalar(select(Review).where(Review.reservation_id == reservation_id))


def get_active(db: Session, review_id: int, *, for_update: bool = False):
    query = select(Review).where(Review.review_id == review_id, Review.deleted_at.is_(None))
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def create(db: Session, **values) -> int:
    # B 모델 미등록 상태에서도 A 테이블 INSERT를 구성할 수 있게 Core DML을 쓴다.
    result = db.execute(insert(Review.__table__).values(**values))
    return result.lastrowid


def change(db: Session, review_id: int, values: dict) -> None:
    db.execute(update(Review).where(Review.review_id == review_id).values(**values))


def list_items(
    db: Session, pagination, *, sort="recent", user_id=None, venue_id=None, category=None
):
    """공개 목록은 활성 공간만, 내 후기는 비활성 공간도 포함한다."""
    context = reservation_repo.review_context_query(active_only=user_id is None).subquery()
    query = (
        select(
            Review.review_id,
            context.c.venue_id,
            context.c.venue_name,
            context.c.category,
            Review.rating,
            Review.content,
            Review.created_at,
            User.name.label("author_name"),
            User.deleted_at.label("author_deleted_at"),
        )
        .select_from(Review)
        .join(User, User.user_id == Review.user_id)
        .join(context, context.c.reservation_id == Review.reservation_id)
        .where(Review.deleted_at.is_(None))
    )
    if user_id is not None:
        query = query.where(Review.user_id == user_id)
    if venue_id is not None:
        query = query.where(context.c.venue_id == venue_id)
    if category is not None:
        query = query.where(context.c.category == category)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = {
        "recent": (Review.created_at.desc(), Review.review_id.desc()),
        "high": (Review.rating.desc(), Review.created_at.desc(), Review.review_id.desc()),
        "low": (Review.rating.asc(), Review.created_at.desc(), Review.review_id.desc()),
    }
    rows = db.execute(query.order_by(*order[sort]).offset(pagination.offset).limit(pagination.size))
    return [dict(row) for row in rows.mappings()], total
