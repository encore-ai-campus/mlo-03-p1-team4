"""F-03~04: 내 정보 변경과 개인정보 익명화.

사용: 회원 라우터가 사용자 정보와 비밀번호 변경 트랜잭션을 위임한다.
"""

from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.errors import fail
from app.core.security import hash_password, unusable_password_hash, verify_password
from app.repositories import reservation_repo, user_repo
from app.schemas.users import PasswordUpdate, UserUpdate


def get_me(db: Session, user_id: int):
    """내 정보 라우터가 현재 로그인한 회원을 primary에서 읽는다."""
    user = user_repo.get_active(db, user_id)
    if user is None:
        raise fail("UNAUTHORIZED", 401)
    return user


def update_me(db: Session, user_id: int, body: UserUpdate):
    """내 정보 변경 시 회원 행을 잠그고 성공하면 커밋한다."""
    try:
        user = user_repo.get_active(db, user_id, for_update=True)
        if user is None:
            raise fail("UNAUTHORIZED", 401)
        for name, value in body.model_dump(exclude_unset=True).items():
            setattr(user, name, value)
        db.commit()
        return user
    except Exception:
        db.rollback()
        raise


def change_password(db: Session, user_id: int, body: PasswordUpdate) -> None:
    """현재 비밀번호를 확인한 뒤 새 해시를 저장한다."""
    try:
        user = user_repo.get_active(db, user_id, for_update=True)
        if user is None:
            raise fail("UNAUTHORIZED", 401)
        if not verify_password(body.current_password, user.password_hash):
            raise fail("WRONG_PASSWORD", 400)
        user.password_hash = hash_password(body.new_password)
        db.commit()
    except Exception:
        db.rollback()
        raise


def withdraw(db: Session, user_id: int) -> None:
    """취소할 수 있는 예약이 없을 때 개인정보를 익명화하고 탈퇴 처리한다."""
    try:
        user = user_repo.get_active(db, user_id, for_update=True)
        if user is None:
            raise fail("UNAUTHORIZED", 401)

        cancellable_count = reservation_repo.count_cancellable(db, user_id)
        if cancellable_count > 0:
            raise fail("HAS_UPCOMING_RESERVATION", 409, {"count": cancellable_count})

        user.deleted_at = get_now()
        user.name = "탈퇴회원"
        user.phone = None
        user.birth = "000000"
        user.email = f"deleted+{user_id}@invalid"
        user.password_hash = unusable_password_hash()
        user.marketing_agreed = False
        db.commit()
    except Exception:
        db.rollback()
        raise
