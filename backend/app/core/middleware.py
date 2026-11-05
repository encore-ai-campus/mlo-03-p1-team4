"""요청 식별·안전한 접근 로그·응답 뒤 이벤트 적재를 맡는 ASGI 계층.

사용: 앱이 모든 HTTP 요청의 식별·접근 기록과 응답 뒤 이벤트 전달을 처리한다.
"""

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import unexpected_response
from app.core.events import EventBuffer, event_buffer, submit_events
from app.core.logging import request_id_context
from app.core.metrics import mongo_event_write_failures_counter


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        pending = EventBuffer()
        event_token = event_buffer.set(pending)
        request_token = request_id_context.set(request_id)
        started = perf_counter()
        status, response_started, completed = 500, False, False

        async def send_response(message: Message) -> None:
            nonlocal status, response_started, completed
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"x-request-id", request_id.encode("ascii")),
                    ],
                }
                if scope["state"].get("user_id") is not None:
                    message["headers"] = [
                        (key, value)
                        for key, value in message["headers"]
                        if key.lower() != b"cache-control"
                    ]
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        try:
            try:
                await self.app(scope, receive, send_response)
            except Exception as error:
                # HTTP 헤더를 전송한 스트림에는 두 번째 응답을 보내지 않는다.
                if response_started:
                    raise
                response = await run_in_threadpool(unexpected_response, Request(scope), error)
                await response(scope, receive, send_response)
        finally:
            try:
                try:
                    await run_in_threadpool(submit_events, pending.documents)
                except Exception:
                    mongo_event_write_failures_counter.inc(len(pending.documents))
                    logging.getLogger("spacecube.app").error("이벤트 작업 전달 실패")
                route = scope.get("route")
                await run_in_threadpool(
                    logging.getLogger("spacecube.app").info,
                    "요청 처리",
                    extra={
                        "request_id": request_id,
                        "path": getattr(route, "path", "<unmatched>"),
                        "method": scope["method"],
                        "status": status,
                        "ms": round((perf_counter() - started) * 1000, 2),
                        "user_id": scope["state"].get("user_id"),
                        "completed": completed,
                    },
                )
            finally:
                event_buffer.reset(event_token)
                request_id_context.reset(request_token)
