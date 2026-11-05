"""A의 앱 구성. 업무 규칙·SQL·미들웨어 구현은 각각의 모듈에 둔다.

사용: Uvicorn이 불러오며, A·B 라우터와 공통 미들웨어를 하나의 앱에 연결한다.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.db import close_databases
from app.core.errors import ErrorResponse, register_error_handlers
from app.core.events import start_event_writer, stop_event_writer
from app.core.logging import setup_logging
from app.core.metrics import setup_metrics
from app.core.middleware import RequestContextMiddleware
from app.core.mongo import close_mongo, get_mongo_client
from app.routers import auth, catalog, events, health, reservations, reviews, users, venues
from app.services.health_service import stop_health_checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    get_mongo_client()  # connect=False. MongoDB 장애 때문에 기동을 중단하지 않는다.
    start_event_writer()
    try:
        yield
    finally:
        try:
            await run_in_threadpool(stop_event_writer)
        finally:
            try:
                await run_in_threadpool(stop_health_checks)
            finally:
                try:
                    close_mongo()
                finally:
                    close_databases()


def configure_openapi(app: FastAPI) -> None:
    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            for path in schema.get("paths", {}).values():
                for operation in path.values():
                    if isinstance(operation, dict):
                        # 실제 검증 응답은 400이다. 자동 생성된 422 안내를 남기지 않는다.
                        operation.get("responses", {}).pop("422", None)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="공간큐브 API",
        version="0.1.0",
        description="회원·후기·사용자 이벤트 API. B 기능은 통합 후 같은 앱에 등록합니다.",
        lifespan=lifespan,
        responses={
            status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 405, 409, 500, 503)
        },
    )
    register_error_handlers(app)
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(reviews.router, tags=["reviews"])
    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(catalog.router, tags=["catalog"])
    app.include_router(venues.router, prefix="/venues", tags=["venues"])
    app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
    # B의 internal은 해당 파트 구현 후 등록한다.
    setup_metrics(app)
    configure_openapi(app)
    app.add_middleware(RequestContextMiddleware)
    # CORS가 오류를 만드는 미들웨어 바깥에 있어 500 응답에도 허용 헤더를 붙인다.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Session-Id",
            "X-Synthetic",
            "X-Synthetic-Key",
            "X-Internal-Key",
        ],
        expose_headers=["X-Request-Id"],
    )
    return app


app = create_app()
