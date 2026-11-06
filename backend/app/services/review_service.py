"""F-41·50·51: 작성 자격·작성자 권한·후기 목록.

사용: 후기 라우터가 예약 자격·작성자 권한·후기 목록 처리를 위임한다.
"""

from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import get_now, get_today
from app.core.errors import fail
from app.core.pagination import paginate
from app.repositories import reservation_repo, review_repo, user_repo


def _owned_reservation(db: Session, user_id: int, reservation_id: int):
    """후기 작성이 B의 약속된 함수로 본인 예약을 확인하도록 연결한다."""
    # B가 제공하기로 확정한 함수만 호출한다. A에서 예약 SQL을 대신 쓰지 않는다.
    return reservation_repo.get_owned(db, user_id, reservation_id)


def create_review(db: Session, user_id: int, reservation_id: int, body) -> dict:
    """예약 소유·완료·기한·중복을 순서대로 확인하고 후기를 저장한다."""
    try:
        reservation = _owned_reservation(db, user_id, reservation_id)
        if reservation is None:
            raise fail("RESERVATION_NOT_FOUND", 404)
        _, _, reserve_date, _, _, status, created_at = reservation
        if status != "completed":
            raise fail("NOT_COMPLETED", 403)
        deadline = max(reserve_date, created_at.date()) + timedelta(days=7)
        if get_today() > deadline:
            raise fail("REVIEW_PERIOD_OVER", 403, {"deadline": deadline.isoformat()})
        existing = review_repo.get_by_reservation(db, reservation_id)
        if existing is not None:
            raise fail("REVIEW_EXISTS", 409, {"review_id": existing.review_id})
        if user_repo.get_active(db, user_id, for_update=True) is None:
            raise fail("UNAUTHORIZED", 401)
        review_id = review_repo.create(
            db,
            reservation_id=reservation_id,
            user_id=user_id,
            rating=body.rating,
            content=body.content,
            created_at=get_now(),
        )
        db.commit()
        return {"review_id": review_id}
    except IntegrityError as error:
        db.rollback()
        if error.orig.args[0] != 1062:
            raise
        existing = review_repo.get_by_reservation(db, reservation_id)
        if existing is None:
            raise
        raise fail("REVIEW_EXISTS", 409, {"review_id": existing.review_id}) from error
    except Exception:
        db.rollback()
        raise


def _owned_review(db: Session, user_id: int, review_id: int):
    """후기 수정·삭제 전에 회원과 후기의 잠금 및 작성자 권한을 확인한다."""
    # 회원 → 후기 순서로 잠금을 잡아 탈퇴·다른 후기 쓰기와의 순서를 일정하게 한다.
    if user_repo.get_active(db, user_id, for_update=True) is None:
        raise fail("UNAUTHORIZED", 401)
    review = review_repo.get_active(db, review_id, for_update=True)
    if review is None:
        raise fail("REVIEW_NOT_FOUND", 404)
    if review.user_id != user_id:
        raise fail("FORBIDDEN", 403)
    return review


def update_review(db: Session, user_id: int, review_id: int, body) -> dict:
    """작성자의 후기 내용과 별점을 갱신하고 커밋한다."""
    try:
        _owned_review(db, user_id, review_id)
        review_repo.change(db, review_id, body.model_dump(exclude_unset=True))
        db.commit()
        return {"review_id": review_id}
    except Exception:
        db.rollback()
        raise


def delete_review(db: Session, user_id: int, review_id: int) -> None:
    """작성자의 후기에 삭제 시각을 기록해 공개 목록에서 숨긴다."""
    try:
        _owned_review(db, user_id, review_id)
        review_repo.change(db, review_id, {"deleted_at": get_now()})
        db.commit()
    except Exception:
        db.rollback()
        raise


def list_reviews(db: Session, pagination, **filters) -> dict:
    """목록 화면에 필요한 후기를 가져와 작성자의 이름을 가린다."""
    items, total = review_repo.list_items(db, pagination, **filters)
    for item in items:
        deleted = item.pop("author_deleted_at")
        name = item.pop("author_name")
        item["author"] = "탈퇴한 회원" if deleted is not None else (name[:1] + "**")
    return paginate(items, pagination.page, pagination.size, total)
