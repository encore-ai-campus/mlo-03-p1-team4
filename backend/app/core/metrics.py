"""F-65: A·B 공통 지표와 HTTP 관측.

사용: 앱이 HTTP 지표를 노출하고 B 예약 서비스가 예약 결과 카운터를 올린다.
"""

from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

reservation_counter = Counter("reservation_total", "예약 처리 결과", ["result"])
mongo_event_write_failures_counter = Counter(
    "mongo_event_write_failures_total",
    "MongoDB에 쓰지 못한 이벤트 수",
)
event_file_write_failures_counter = Counter(
    "event_file_write_failures_total",
    "events.log에 기록하지 못한 이벤트 수",
    ["stage", "reason"],
)
event_file_lock_wait_seconds = Histogram(
    "event_file_lock_wait_seconds",
    "events.log 파일 잠금 획득 대기 시간(초)",
    ["scope"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.5, 1.0),
)
event_file_write_duration_seconds = Histogram(
    "event_file_write_duration_seconds",
    "이벤트 파일 직렬화·기록 시도 전체 소요 시간(초)",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0),
)
db_read_fallback_counter = Counter("db_read_fallback_total", "replica 대신 primary를 사용한 횟수")


def setup_metrics(app) -> None:
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics"],
        should_ignore_untemplated=False,
    ).instrument(app).expose(app, include_in_schema=False)
