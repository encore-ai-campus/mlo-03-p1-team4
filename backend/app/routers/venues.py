"""F-20 공개 공간 상세. /venues 접두사는 앱에서 등록한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.db import get_db_read
from app.schemas.venues import VenueRead
from app.services import venue_service

router = APIRouter()


@router.get("/{venue_id}", summary="공간 상세 조회")
def get_venue(
    venue_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    db: Annotated[Session, Depends(get_db_read)],
) -> VenueRead:
    """인증 없이 활성 공간의 정보와 오늘 시간 칸을 반환한다."""
    return venue_service.get_venue(db, venue_id)
