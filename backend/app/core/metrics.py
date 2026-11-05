"""F-65: A·B 공통 지표와 HTTP 관측.

사용: 앱이 HTTP 지표를 노출하고 B 예약 서비스가 예약 결과 카운터를 올린다.
"""

from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

reservation_counter = Counter("reservation_total", "예약 처리 결과", ["result"])
mongo_event_write_failures_counter = Counter(
    "mongo_event_write_failures_total",
    "MongoDB에 쓰지 못한 이벤트 수",
)
db_read_fallback_counter = Counter("db_read_fallback_total", "replica 대신 primary를 사용한 횟수")


def setup_metrics(app) -> None:
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics"],
        should_ignore_untemplated=False,
    ).instrument(app).expose(app, include_in_schema=False)
