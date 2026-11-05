"""F-70: 세 저장소를 동시에 확인하되 HTTP 대기는 0.5초로 제한한다.

사용: 헬스 라우터가 primary·replica·MongoDB 연결 상태를 확인한다.
"""

from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import Lock

from app.core.db import check_database
from app.core.errors import fail
from app.core.mongo import check_mongo

_lock = Lock()
_executor: ThreadPoolExecutor | None = None
_running: dict[str, Future[bool]] = {}


def get_health() -> dict[str, str]:
    global _executor
    checks = {
        "primary": lambda: check_database("write"),
        "replica": lambda: check_database("read"),
        "mongo": check_mongo,
    }
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="health")
        for name, check in checks.items():
            previous = _running.get(name)
            if previous is None or previous.done():
                _running[name] = _executor.submit(check)
        running = dict(_running)

    # 느린 확인은 다음 요청에서도 같은 작업을 공유한다. 작업이 무한히 쌓이지 않는다.
    completed, _ = wait(running.values(), timeout=0.5)
    results = {}
    for name, future in running.items():
        try:
            results[name] = future in completed and future.result()
        except Exception:
            results[name] = False

    if not results["primary"]:
        raise fail("SERVICE_UNAVAILABLE", 503)
    response = {"status": "ok"}
    for name in ("replica", "mongo"):
        if not results[name]:
            response["status"] = "degraded"
            response[name] = "down"
    return response


def stop_health_checks() -> None:
    global _executor
    with _lock:
        executor, _executor = _executor, None
        _running.clear()
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)
