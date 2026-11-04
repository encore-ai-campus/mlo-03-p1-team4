"""F-10 유형 목록과 프로세스별 5분 캐시."""

from threading import Lock
from time import monotonic

from sqlalchemy.orm import Session

from app.repositories import catalog_repo
from app.schemas.catalog import CategoryRead

_CACHE_TTL_SECONDS = 300
_cache_lock = Lock()
_categories_cache: tuple[CategoryRead, ...] | None = None
_cache_expires_at = 0.0


def list_categories(db: Session) -> list[CategoryRead]:
    """세션에 묶인 ORM 객체 대신 공개 응답 값만 캐시한다."""
    global _categories_cache, _cache_expires_at

    # 동기 엔드포인트의 여러 스레드가 동시에 캐시를 갱신하지 않도록 한다.
    with _cache_lock:
        if _categories_cache is None or monotonic() >= _cache_expires_at:
            categories = tuple(
                CategoryRead.model_validate(category)
                for category in catalog_repo.list_categories(db)
            )
            # 조회가 성공한 뒤에만 캐시를 바꾼다. DB 오류는 A의 공통 처리기로 전달한다.
            _categories_cache = categories
            _cache_expires_at = monotonic() + _CACHE_TTL_SECONDS

        return list(_categories_cache)
