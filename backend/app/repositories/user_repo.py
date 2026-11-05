"""회원 테이블 접근. 인증·내 정보는 primary 세션을 전달받는다.

사용: 회원·인증 서비스와 인증 의존성이 회원 테이블을 조회하고 추가한다.
"""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))


def email_exists(db: Session, email: str) -> bool:
    # UNIQUE와 같은 범위를 확인한다. 정상 탈퇴는 이메일을 익명 주소로 바꾼다.
    return bool(db.scalar(select(exists().where(User.email == email))))


def get_active(db: Session, user_id: int, *, for_update: bool = False) -> User | None:
    query = select(User).where(User.user_id == user_id, User.deleted_at.is_(None))
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def create(db: Session, **values) -> User:
    user = User(**values)
    db.add(user)
    db.flush()
    return user
