"""F-10·11 공개 기준 정보. /api 접두사는 프록시에서 처리한다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_read
from app.schemas.catalog import CategoryRead, FacilityRead, RegionRead
from app.services import catalog_service

router = APIRouter()


@router.get("/categories", summary="공간 유형 목록 조회")
def get_categories(db: Annotated[Session, Depends(get_db_read)]) -> list[CategoryRead]:
    """로그인 없이 유형의 code·name 목록을 반환한다."""
    return catalog_service.list_categories(db)


@router.get("/regions", summary="공간이 있는 지역 목록 조회")
def get_regions(
    db: Annotated[Session, Depends(get_db_read)],
    sido: Annotated[str | None, Query(max_length=20)] = None,
) -> list[str] | list[RegionRead]:
    """시·도가 없으면 시·도 목록, 있으면 해당 시·군·구 목록을 반환한다."""
    if sido is None:
        return catalog_service.list_sidos(db)
    return catalog_service.list_regions(db, sido)


@router.get("/facilities", summary="시설 목록 조회")
def get_facilities(db: Annotated[Session, Depends(get_db_read)]) -> list[FacilityRead]:
    """로그인 없이 검색 필터에 사용할 전체 시설을 반환한다."""
    return catalog_service.list_facilities(db)
