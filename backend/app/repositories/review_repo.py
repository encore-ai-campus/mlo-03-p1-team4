"""후기 SQL. B 소유 테이블은 직접 조회하지 않는다.

사용: 후기 서비스가 후기 테이블 접근과 목록 조회를 위임한다.
"""

from collections.abc import Callable

from sqlalchemy import Select, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.errors import fail
from app.models.review import Review
from app.models.user import User

# A 내부 연결부. B 조회 함수가 합의되면 그 결과를 연결한다.
# 현재는 공급자가 없으므로 공간 정보가 필요한 목록에 503을 반환한다.
_context_query_factory: Callable[[], Select] | None = None


def configure_context_query(factory: Callable[[], Select]) -> None:
    """통합 시 예약 ID와 공간 목록 응답 필드를 가진 조회식을 주입한다.

    B의 함수명·인자·반환값을 확정하는 약속이 아니다. 합의 후 이 연결부를 조정한다.
    필요한 열은 기존 응답의 reservation_id, venue_id, venue_name, category다.
    """
    global _context_query_factory
    _context_query_factory = factory


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
    """후기 서비스가 쓰는 목록을 조회한다. B 공간 조회 연결 전에는 503이다."""
    if _context_query_factory is None:
        raise fail("SERVICE_UNAVAILABLE", 503)
    context = _context_query_factory().subquery()
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
