"""F-35: 종료 시각이 지난 확정 예약을 완료 처리하는 시간 배치."""

import logging

from app.core.db import close_databases, new_write_session
from app.core.logging import setup_logging
from app.services.reservation_service import complete_ended_reservations

logger = logging.getLogger("spacecube.app")


def main() -> int:
    """primary에서 배치를 실행하고 결과를 JSON 로그로 남긴다."""
    try:
        setup_logging()
        with new_write_session() as db:
            completed = complete_ended_reservations(db)
        logger.info(
            "이용 완료 배치 완료",
            extra={"count": completed, "completed": completed},
        )
        return 0
    except Exception as error:
        # 예외 메시지에는 SQL·연결 정보가 포함될 수 있어 종류만 남긴다.
        logger.error(
            "이용 완료 배치 실패",
            extra={"error_type": type(error).__name__},
        )
        return 1
    finally:
        close_databases()


if __name__ == "__main__":
    raise SystemExit(main())
