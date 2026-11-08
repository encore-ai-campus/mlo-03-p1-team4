"""오류코드.md의 응답 형식과 사용자 문구.

사용: 서비스가 AppError를 발생시키고 앱 예외 처리기가 공통 JSON으로 변환한다.
"""

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException

MESSAGES = {
    "VALIDATION": "입력한 내용을 다시 확인해 주세요.",
    "UNAUTHORIZED": "로그인이 필요해요.",
    "TOKEN_EXPIRED": "로그인 시간이 끝났어요. 다시 로그인해 주세요.",
    "FORBIDDEN": "이 작업은 할 수 없어요.",
    "NOT_FOUND": "찾는 내용이 없어요.",
    "METHOD_NOT_ALLOWED": "요청을 처리하지 못했어요.",
    "INTERNAL_ERROR": "잠시 후 다시 시도해 주세요.",
    "SERVICE_UNAVAILABLE": "서비스 점검 중이에요. 잠시 후 다시 시도해 주세요.",
    "EMAIL_TAKEN": "이미 가입된 이메일이에요.",
    "INVALID_CREDENTIALS": "이메일 또는 비밀번호가 맞지 않아요.",
    "HAS_UPCOMING_RESERVATION": "이용 예정 예약이 있어요. 예약 내역에서 먼저 취소해 주세요.",
    "WRONG_PASSWORD": "현재 비밀번호가 맞지 않아요.",
    "RESERVATION_NOT_FOUND": "예약을 찾을 수 없어요.",
    "NOT_COMPLETED": "이용이 끝난 뒤에 후기를 쓸 수 있어요.",
    "REVIEW_PERIOD_OVER": "후기를 쓸 수 있는 기간이 지났어요.",
    "REVIEW_EXISTS": "이미 후기를 썼어요.",
    "REVIEW_NOT_FOUND": "후기를 찾을 수 없어요.",
}


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int, detail=None):
        super().__init__(code)
        self.code = code
        self.message = message
        self.status = status
        self.detail = detail


def fail(code: str, status: int, detail=None) -> AppError:
    return AppError(code, MESSAGES[code], status, detail)


def invalid_field(field: str, reason: str) -> AppError:
    return fail("VALIDATION", 400, {"fields": [{"field": field, "reason": reason}]})


def error_response(error: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else None
    return JSONResponse(
        status_code=error.status,
        content={"code": error.code, "message": error.message, "detail": error.detail},
        headers=headers,
    )


def is_connection_error(error: OperationalError) -> bool:
    arguments = getattr(error.orig, "args", ())
    number = arguments[0] if arguments else None
    return error.connection_invalidated or number in {
        1040,
        1044,
        1045,
        1049,
        2002,
        2003,
        2006,
        2013,
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def app_error_handler(request: Request, error: AppError):
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    def validation_handler(request: Request, error: RequestValidationError):
        # input·ctx에는 비밀번호 등이 들어갈 수 있어 위치와 이유만 응답한다.
        fields = [
            {
                "field": ".".join(str(part) for part in item["loc"][1:]),
                "reason": item["msg"].removeprefix("Value error, "),
            }
            for item in error.errors()
        ]
        return error_response(fail("VALIDATION", 400, {"fields": fields}))

    @app.exception_handler(HTTPException)
    def http_handler(request: Request, error: HTTPException):
        codes = {
            400: "VALIDATION",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            503: "SERVICE_UNAVAILABLE",
        }
        code = codes.get(error.status_code, "INTERNAL_ERROR")
        detail = {"request_id": request.state.request_id} if code == "INTERNAL_ERROR" else None
        return error_response(
            fail(code, error.status_code if code != "INTERNAL_ERROR" else 500, detail)
        )

    @app.exception_handler(PoolTimeoutError)
    def pool_handler(request: Request, error: PoolTimeoutError):
        return error_response(fail("SERVICE_UNAVAILABLE", 503))

    @app.exception_handler(OperationalError)
    def database_handler(request: Request, error: OperationalError):
        if is_connection_error(error):
            return error_response(fail("SERVICE_UNAVAILABLE", 503))
        return unexpected_response(request, error)

    @app.exception_handler(Exception)
    def unexpected_handler(request: Request, error: Exception):
        return unexpected_response(request, error)


def unexpected_response(request: Request, error: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    route = request.scope.get("route")
    # DB 오류 원문・바인드 값・트레이스백에는 개인정보가 있어 기록하지 않는다.
    frame = error.__traceback__
    while frame is not None and frame.tb_next is not None:
        frame = frame.tb_next
    location = None
    if frame is not None:
        location = f"{Path(frame.tb_frame.f_code.co_filename).name}:{frame.tb_lineno}"
    logging.getLogger("spacecube.app").error(
        "처리하지 못한 오류",
        extra={
            "request_id": request_id,
            "path": getattr(route, "path", "<unmatched>"),
            "error_type": type(error).__name__,
            "error_location": location,
        },
    )
    return error_response(fail("INTERNAL_ERROR", 500, {"request_id": request_id}))
