"""F-70: primary 장애만 503, replica·MongoDB 장애는 degraded.

사용: Nginx·운영자가 앱과 저장소의 상태를 확인한다.
"""

from fastapi import APIRouter

from app.services.health_service import get_health

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return get_health()
