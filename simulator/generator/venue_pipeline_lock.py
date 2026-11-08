"""크롤링과 공간 보충이 공유하는 MariaDB 실행 잠금."""

from contextlib import contextmanager

from sqlalchemy import text

from app.core.db import get_engine

from .plan import GeneratorError

LOCK_NAME = "spacecube_venue_pipeline"


@contextmanager
def venue_pipeline_lock():
    """크롤링부터 보충 종료까지 단일 DB 연결의 이름 잠금을 유지한다."""
    try:
        connection = get_engine("write").connect()
    except Exception:
        raise GeneratorError("primary DB 연결을 초기화하지 못했습니다.") from None

    with connection:
        try:
            acquired = connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": LOCK_NAME})
        except Exception:
            raise GeneratorError("통합 실행 잠금을 얻지 못했습니다.") from None
        if acquired != 1:
            raise GeneratorError("크롤링 또는 공간 보충이 이미 실행 중입니다.")
        try:
            yield
        finally:
            try:
                released = connection.scalar(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": LOCK_NAME}
                )
            except Exception:
                raise GeneratorError("통합 실행 잠금을 정상 해제하지 못했습니다.") from None
            if released != 1:
                raise GeneratorError("통합 실행 잠금이 유지되지 않았습니다.")
