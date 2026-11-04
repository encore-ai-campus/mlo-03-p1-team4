"""F-10·11 기준 정보와 프로세스별 5분 캐시."""

from threading import Lock
from time import monotonic

from sqlalchemy.orm import Session

from app.repositories import catalog_repo
from app.schemas.catalog import CategoryRead, FacilityRead, RegionRead

_CACHE_TTL_SECONDS = 300
_cache_lock = Lock()
_categories_cache: tuple[CategoryRead, ...] | None = None
_cache_expires_at = 0.0
_regions_cache_lock = Lock()
_regions_cache: tuple[tuple[str, RegionRead], ...] | None = None
_regions_cache_expires_at = 0.0
_facilities_cache_lock = Lock()
_facilities_cache: tuple[FacilityRead, ...] | None = None
_facilities_cache_expires_at = 0.0


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


def _list_active_regions(db: Session) -> tuple[tuple[str, RegionRead], ...]:
    """전체 활성 지역을 불변 값으로 저장해 시·도별 요청이 캐시를 공유한다."""
    global _regions_cache, _regions_cache_expires_at

    with _regions_cache_lock:
        if _regions_cache is None or monotonic() >= _regions_cache_expires_at:
            regions = tuple(
                (region.sido, RegionRead.model_validate(region))
                for region in catalog_repo.list_active_regions(db)
            )
            _regions_cache = regions
            _regions_cache_expires_at = monotonic() + _CACHE_TTL_SECONDS

        return _regions_cache


def list_sidos(db: Session) -> list[str]:
    """지역 기본키 순서를 유지하면서 시·도를 중복 없이 반환한다."""
    return list(dict.fromkeys(sido for sido, _ in _list_active_regions(db)))


def list_regions(db: Session, sido: str) -> list[RegionRead]:
    """캐시된 활성 지역 중 선택한 시·도의 시·군·구만 반환한다."""
    return [region for region_sido, region in _list_active_regions(db) if region_sido == sido]


def list_facilities(db: Session) -> list[FacilityRead]:
    """지역·유형과 독립된 캐시에 전체 시설의 공개 응답 값만 저장한다."""
    global _facilities_cache, _facilities_cache_expires_at

    with _facilities_cache_lock:
        if _facilities_cache is None or monotonic() >= _facilities_cache_expires_at:
            facilities = tuple(
                FacilityRead.model_validate(facility)
                for facility in catalog_repo.list_facilities(db)
            )
            _facilities_cache = facilities
            _facilities_cache_expires_at = monotonic() + _CACHE_TTL_SECONDS

        return list(_facilities_cache)
