"""F-63: 오늘·지금은 이 모듈에서만 읽는다.

사용: A·B 서비스가 한국 기준 오늘·현재 시각과 실제 이벤트 수신 시각을 얻는다.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime, timedelta, timezone

from app.core.config import get_settings

KST = timezone(timedelta(hours=9), name="Asia/Seoul")
_BUSINESS_TIME_OVERRIDE: ContextVar[datetime | None] = ContextVar(
    "spacecube_business_time_override",
    default=None,
)


@contextmanager
def override_business_time(value: datetime) -> Iterator[None]:
    """백필 중 서비스의 업무 시각만 잠시 바꾼다.

    시간대가 없는 입력은 Asia/Seoul 시각으로 보고, 시간대가 있으면 KST로
    변환한다. ContextVar를 사용하므로 이 모듈 함수를 이미 import한 서비스와
    스키마 검증기도 같은 값을 읽으며, 중첩 사용 후에는 이전 값으로 복원된다.
    이벤트의 실제 적재 시각은 get_event_time()으로 별도 유지한다.
    """
    if not isinstance(value, datetime):
        raise TypeError("업무 시각은 datetime이어야 합니다.")
    local_value = value.astimezone(KST).replace(tzinfo=None) if value.tzinfo else value
    token = _BUSINESS_TIME_OVERRIDE.set(local_value)
    try:
        yield
    finally:
        _BUSINESS_TIME_OVERRIDE.reset(token)


def get_now() -> datetime:
    """A·B에 MariaDB DATETIME과 비교 가능한 시간대 없는 한국 시각을 제공한다."""
    override = _BUSINESS_TIME_OVERRIDE.get()
    if override is not None:
        return override
    current = datetime.now(KST)
    override = get_settings().today_override
    if override:
        current = datetime.combine(date.fromisoformat(override), current.timetz())
    return current.replace(tzinfo=None)


def get_today() -> date:
    """예약 범위와 후기 기한 계산에 사용할 한국 날짜를 제공한다."""
    return get_now().date()


def as_korean_time(value: datetime) -> datetime:
    return value.replace(tzinfo=KST) if value.tzinfo is None else value.astimezone(KST)


def get_event_time() -> datetime:
    # 백필의 과거 업무 시각·TODAY_OVERRIDE와 무관한 실제 수신 시각이다.
    return datetime.now(UTC)
