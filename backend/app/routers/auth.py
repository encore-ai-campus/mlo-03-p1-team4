"""F-01~02: 회원가입·이메일 확인·로그인.

사용: 프론트·API 클라이언트의 가입·이메일 확인·로그인 요청을 받는다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.deps import CurrentUser, WriteDB, get_current_user
from app.core.synthetic import is_synthetic_request
from app.schemas.auth import EmailCheckRead, LoginCreate, LoginRead, SignupCreate, SignupRead
from app.services import auth_service

router = APIRouter()
Member = Annotated[CurrentUser, Depends(get_current_user)]


@router.get("/email-check")
def email_check(
    db: WriteDB, email: Annotated[str, Query(min_length=3, max_length=100)]
) -> EmailCheckRead:
    return auth_service.check_email(db, email)


@router.post("/signup", status_code=201)
def signup(body: SignupCreate, request: Request, db: WriteDB) -> SignupRead:
    return auth_service.signup(db, body, is_synthetic_request(request))


@router.post("/login")
def login(body: LoginCreate, db: WriteDB) -> LoginRead:
    return auth_service.login(db, body.email, body.password)


@router.post("/logout", status_code=204)
def logout(_user: Member) -> Response:
    """로그아웃 요청을 확인한다. 클라이언트가 보유한 Bearer 토큰도 지워야 한다."""
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
