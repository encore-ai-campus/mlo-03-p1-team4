"""F-03~04: 인증 및 내 정보 접근은 모두 primary.

사용: 로그인한 사용자의 내 정보·비밀번호·탈퇴 요청을 받는다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import CurrentUser, WriteDB, get_current_user
from app.schemas.users import PasswordUpdate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter()
Member = Annotated[CurrentUser, Depends(get_current_user)]


@router.get("/me")
def get_me(user: Member, db: WriteDB) -> UserRead:
    return user_service.get_me(db, user.user_id)


@router.patch("/me")
def update_me(body: UserUpdate, user: Member, db: WriteDB) -> UserRead:
    return user_service.update_me(db, user.user_id, body)


@router.patch("/me/password", status_code=204)
def change_password(body: PasswordUpdate, user: Member, db: WriteDB) -> Response:
    user_service.change_password(db, user.user_id, body)
    return Response(status_code=204)


@router.delete("/me", status_code=204)
def withdraw(user: Member, db: WriteDB) -> Response:
    user_service.withdraw(db, user.user_id)
    return Response(status_code=204)
