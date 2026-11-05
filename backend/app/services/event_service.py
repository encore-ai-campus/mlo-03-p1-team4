"""F-60: 프론트 이벤트 검증과 B의 공간 유형 조회 연결부.

사용: 이벤트 라우터가 허용 목록·공간 유형과 저장 처리를 위임한다.
"""

import logging
from collections import Counter, OrderedDict
from collections.abc import Callable
from threading import Lock
from time import monotonic

from app.core.event_context import ClientEventContext, client_event_context
from app.core.events import FRONTEND_EVENTS, log_event, require_event_file
from app.schemas.events import EventBatchCreate

_category_reader: Callable[[list[int]], dict[int, str]] | None = None
_category_cache: OrderedDict[int, tuple[float, str]] = OrderedDict()
_cache_lock = Lock()
_categories = frozenset({"studyroom", "studio", "cafe", "lectureroom", "partyroom"})


def configure_category_reader(reader: Callable[[list[int]], dict[int, str]]) -> None:
    """A 내부 주입 지점. B 공용 조회 함수 합의 전에는 등록하지 않는다."""
    global _category_reader
    with _cache_lock:
        _category_reader = reader
        _category_cache.clear()


def _read_categories(venue_ids: list[int]) -> dict[int, str]:
    """이벤트의 공간 유형을 5분 캐시에서 찾고 필요한 값만 연결부에 요청한다."""
    found = {}
    missing = []
    now = monotonic()
    with _cache_lock:
        reader = _category_reader
        for venue_id in venue_ids:
            cached = _category_cache.get(venue_id)
            if cached is not None and cached[0] > now:
                found[venue_id] = cached[1]
                _category_cache.move_to_end(venue_id)
            else:
                _category_cache.pop(venue_id, None)
                missing.append(venue_id)

    if not missing or reader is None:
        return found
    try:
        fetched = reader(missing)
        resolved = {
            venue_id: fetched[venue_id]
            for venue_id in missing
            if fetched.get(venue_id) in _categories
        }
    except Exception:
        # 보조 정보 실패가 탐색 이벤트 수집 자체를 막지 않게 원천 ID를 보존한다.
        logging.getLogger("spacecube.app").warning(
            "이벤트 공간 유형 조회 실패, venue_id만 보존",
            extra={"count": len(missing)},
        )
        return found

    with _cache_lock:
        if reader is _category_reader:
            for venue_id, category in resolved.items():
                _category_cache[venue_id] = (monotonic() + 300, category)
                _category_cache.move_to_end(venue_id)
            while len(_category_cache) > 4096:
                _category_cache.popitem(last=False)
    found.update(resolved)
    return found


def accept_events(body: EventBatchCreate, user_id: int | None, is_synthetic: bool) -> dict:
    """이벤트 라우터가 호출하며 허용된 항목을 기록하고 제외 건수를 반환한다."""
    accepted = [item for item in body.events if item.event_type in FRONTEND_EVENTS]
    ignored = Counter(
        item.event_type for item in body.events if item.event_type not in FRONTEND_EVENTS
    )
    venue_ids = sorted({item.venue_id for item in accepted if item.venue_id is not None})
    categories = _read_categories(venue_ids)

    # B 조회 연결 전에는 category=null이다. payload의 공간 번호로 대체하지 않는다.
    for item in accepted:
        token = client_event_context.set(ClientEventContext(occurred_at=item.occurred_at))
        try:
            log_event(
                str(body.session_id),
                user_id,
                item.event_type,
                venue_id=item.venue_id,
                category=categories.get(item.venue_id),
                payload=item.payload,
                is_synthetic=is_synthetic,
            )
        finally:
            client_event_context.reset(token)

    if ignored:
        logging.getLogger("spacecube.app").warning(
            "허용 목록에 없는 프론트 이벤트 제외",
            extra={"count": sum(ignored.values())},
        )
    require_event_file()
    return {
        "accepted": len(accepted),
        "ignored": [{"event_type": name, "count": count} for name, count in ignored.items()],
    }
