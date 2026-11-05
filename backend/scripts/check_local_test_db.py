"""F-64: 애플리케이션 엔진의 테스트 DB 세션 설정을 확인한다.

사용: 로컬 MariaDB spacecube_test에 연결해 현재 연결의 시간대와 STRICT 모드를 출력한다.
"""

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.db import get_engine

EXPECTED_SQL_MODE = (
    "STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION"
)


def main() -> int:
    value = get_settings().db_write_url
    if value is None:
        print("DB_WRITE_URL이 설정되지 않았습니다.")
        return 1

    try:
        url = make_url(value.get_secret_value())
        if (
            url.drivername != "mysql+pymysql"
            or url.database != "spacecube_test"
            or url.host not in {"localhost", "127.0.0.1", "::1"}
        ):
            print("안전상 로컬 MariaDB spacecube_test만 확인할 수 있습니다.")
            return 1

        engine = get_engine("write")
        try:
            with engine.connect() as connection:
                database, timezone, sql_mode = connection.execute(
                    text("SELECT DATABASE(), @@SESSION.time_zone, @@SESSION.sql_mode")
                ).one()
        finally:
            engine.dispose()
    except Exception:
        print(
            "로컬 테스트 DB 연결 또는 세션 확인에 실패했습니다. 설정과 MariaDB 상태를 확인하세요."
        )
        return 1

    print(f"database={database}")
    print(f"time_zone={timezone}")
    print(f"sql_mode={sql_mode}")
    if database != "spacecube_test" or timezone != "+09:00" or sql_mode != EXPECTED_SQL_MODE:
        print("세션 값이 기준과 다릅니다.")
        return 1
    print("로컬 테스트 DB 세션 설정이 기준과 일치합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
