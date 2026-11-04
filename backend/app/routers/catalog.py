"""F-10 공개 유형 목록. /api 접두사는 프록시에서 처리한다."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db_read
from app.schemas.catalog import CategoryRead
from app.services import catalog_service

router = APIRouter()


@router.get("/categories", summary="공간 유형 목록 조회")
def get_categories(db: Annotated[Session, Depends(get_db_read)]) -> list[CategoryRead]:
    """로그인 없이 유형의 code·name 목록을 반환한다."""
    return catalog_service.list_categories(db)
