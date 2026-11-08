"""F-61: 내부 키를 확인하고 전처리한 공간의 등록·갱신을 위임한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db_write
from app.core.deps import require_internal_key
from app.schemas.internal import InternalVenueRead, InternalVenueUpsert
from app.services import internal_service

router = APIRouter(dependencies=[Depends(require_internal_key)])


@router.post(
    "/venues",
    status_code=201,
    responses={200: {"model": InternalVenueRead, "description": "기존 출처 공간 갱신"}},
    summary="크롤링·생성 공간 등록 또는 갱신",
    openapi_extra={
        "parameters": [
            {
                "name": "X-Internal-Key",
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": "INTERNAL_API_KEY와 같은 내부 전용 키",
            }
        ]
    },
)
def upsert_venue(
    body: InternalVenueUpsert,
    response: Response,
    db: Annotated[Session, Depends(get_db_write)],
) -> InternalVenueRead:
    result, status_code = internal_service.upsert_venue(db, body)
    response.status_code = status_code
    return result
