"""F-60: 응답 뒤 MongoDB 쓰기는 공통 미들웨어가 처리한다.

사용: 프론트·시뮬레이터가 사용자 행동 이벤트 묶음을 제출한다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import CurrentUser, get_optional_user
from app.core.synthetic import is_synthetic_request
from app.schemas.events import EventBatchCreate, EventBatchRead
from app.services import event_service

router = APIRouter()


@router.post("", status_code=202)
def events(
    body: EventBatchCreate,
    request: Request,
    user: Annotated[CurrentUser | None, Depends(get_optional_user)],
) -> EventBatchRead:
    return event_service.accept_events(
        body,
        user.user_id if user else None,
        is_synthetic_request(request),
    )
