"""F-63: 오늘·지금은 이 모듈에서만 읽는다.

사용: A·B 서비스가 한국 기준 오늘·현재 시각과 이벤트 수신 시각을 얻는다.
"""

from datetime import UTC, date, datetime, timedelta, timezone

from app.core.config import get_settings

KST = timezone(timedelta(hours=9), name="Asia/Seoul")


def get_now() -> datetime:
    """A·B에 MariaDB DATETIME과 비교 가능한 시간대 없는 한국 시각을 제공한다."""
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
    # 이벤트 TTL은 TODAY_OVERRIDE와 무관한 실제 수신 시각으로 계산한다.
    return datetime.now(UTC)
