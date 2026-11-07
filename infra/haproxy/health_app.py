"""F-70 · #66: 업무 Uvicorn과 독립된 루프백 헬스 확인 프로세스.

backend를 PYTHONPATH에 넣고 이 디렉터리에서 Uvicorn으로 실행한다.
기존 저장소 상태 판정은 그대로 재사용하며 업무 API는 등록하지 않는다.
"""

from contextlib import asynccontextmanager
from http.client import HTTPConnection, HTTPException

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from app.core.db import close_databases
from app.core.errors import AppError, error_response, fail
from app.core.mongo import close_mongo
from app.services.health_service import get_health, stop_health_checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        try:
            await run_in_threadpool(stop_health_checks)
        finally:
            try:
                close_mongo()
            finally:
                close_databases()


app = FastAPI(lifespan=lifespan, openapi_url=None, docs_url=None, redoc_url=None)


@app.exception_handler(AppError)
def handle_error(request: Request, error: AppError):
    return error_response(error)


@app.get("/health")
def health() -> dict[str, str]:
    # TCP accept만 하는 멈춘 업무 프로세스를 정상으로 판정하지 않는다.
    # 기존 비동기 문서 경로의 헤더만 확인해 업무 스레드 풀과 DB를 사용하지 않는다.
    # Uvicorn 동시성 제한의 503은 HTTP 응답 가능으로 취급한다.
    # primary 장애는 아래 독립 get_health()가 판정하므로 503을 숨기지 않는다.
    connection = HTTPConnection("127.0.0.1", 8000, timeout=0.2)
    try:
        connection.connect()
        connection.sock.settimeout(0.3)
        connection.request("HEAD", "/openapi.json", headers={"Connection": "close"})
        response = connection.getresponse()
        if response.status not in (200, 503):
            raise fail("SERVICE_UNAVAILABLE", 503)
    except (OSError, HTTPException):
        raise fail("SERVICE_UNAVAILABLE", 503) from None
    finally:
        connection.close()
    return get_health()
