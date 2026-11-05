"""F-03~04: 내 정보 변경과 개인정보 익명화.

사용: 회원 라우터가 사용자 정보와 비밀번호 변경 트랜잭션을 위임한다.
"""

from sqlalchemy.orm import Session

from app.core.errors import fail
from app.core.security import hash_password, verify_password
from app.repositories import user_repo
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
    """예약·환불 확인을 B와 연결하기 전까지 모든 탈퇴 요청을 보류한다."""
    # B의 예약·환불 상태 확인과 동시 예약 방지 계약이 마련되기 전에는
    # 예약이 없다고 추측하거나 개인정보를 지우지 않는다.
    raise fail("SERVICE_UNAVAILABLE", 503)
