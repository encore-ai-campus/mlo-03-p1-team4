"""F-62: 가상 데이터 요청 표시.

사용: 회원가입·이벤트와 B 예약 코드가 가상 데이터 헤더를 판별한다.
"""

import secrets

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import fail


def is_synthetic_request(request: Request) -> bool:
    """가상 데이터 헤더가 있으면 전용 키를 확인하고 1일 때만 참을 반환한다."""
    value = request.headers.get("X-Synthetic")
    if value is None:
        return False

    configured = get_settings().synthetic_api_key
    supplied = request.headers.get("X-Synthetic-Key", "")
    expected = configured.get_secret_value() if configured is not None else ""
    if (
        not expected
        or not supplied
        or not secrets.compare_digest(
            supplied.encode("utf-8"),
            expected.encode("utf-8"),
        )
    ):
        raise fail("UNAUTHORIZED", 401)
    return value == "1"
