"""F-01~02: 가입·로그인. primary에서 확인한다.

사용: 인증 라우터가 이메일 중복·가입·로그인 처리를 위임한다.
"""

import secrets
from functools import lru_cache

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.config import get_settings
from app.core.errors import fail
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories import user_repo
from app.schemas.auth import SignupCreate, validate_email


def check_email(db: Session, email: str) -> dict:
    """가입 화면이 이메일 중복을 primary에서 확인한다."""
    from app.core.errors import invalid_field

    try:
        validate_email(email)
    except ValueError as error:
        raise invalid_field("email", str(error)) from error
    return {"available": not user_repo.email_exists(db, email)}


def signup(db: Session, body: SignupCreate, is_synthetic: bool) -> dict:
    """가입 라우터가 호출하며 비밀번호 해시와 동의 시각을 한 번에 저장한다."""
    now = get_now()
    values = body.model_dump(exclude={"password", "terms_agreed", "privacy_agreed"})
    try:
        user = user_repo.create(
            db,
            **values,
            password_hash=hash_password(body.password),
            terms_agreed_at=now,
            privacy_agreed_at=now,
            created_at=now,
            is_synthetic=is_synthetic,
        )
        db.commit()
        return {"user_id": user.user_id}
    except IntegrityError as error:
        db.rollback()
        if error.orig.args[0] == 1062 and user_repo.email_exists(db, body.email):
            raise fail("EMAIL_TAKEN", 409) from error
        raise
    except Exception:
        db.rollback()
        raise


@lru_cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(24))


def login(db: Session, email: str, password: str) -> dict:
    """로그인 라우터에 토큰을 제공하고, 존재하지 않는 회원도 같은 오류로 처리한다."""
    user = user_repo.get_by_email(db, email)
    valid = verify_password(password, user.password_hash if user else _dummy_hash())
    if user is None or not valid:
        raise fail("INVALID_CREDENTIALS", 401)
    return {
        "access_token": create_access_token(user.user_id),
        "token_type": "bearer",
        "expires_in": get_settings().jwt_expire_minutes * 60,
    }
