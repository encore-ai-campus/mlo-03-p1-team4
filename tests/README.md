# 저장소 공통 테스트

루트 `conftest.py`와 `db_lock.py`는 같은 로컬 MariaDB `spacecube_test`를 사용하는 pytest 프로세스끼리 실행을 직렬화합니다. 별도 테이블·DDL·패키지를 만들지 않고 MariaDB의 연결 단위 명명 잠금만 사용합니다. 연결은 AUTOCOMMIT이며 잠금 외의 SQL·업무 트랜잭션·격리 수준은 변경하지 않습니다.

- 적용: 저장소 안에서 실행하는 직접 pytest, `verify.ps1`, CI의 pytest. 하위 폴더에서 실행해도 루트 conftest가 적용됩니다.
- 잠금은 테스트 전체 session 동안 유지하고, 각 테스트를 시작하기 전에 소유권을 확인합니다. suite 안에서 의도적으로 동시에 실행하는 예약 50요청은 그대로 동작합니다.
- 대기 기본값은 600초입니다. 실행 환경의 `TEST_DB_LOCK_TIMEOUT`으로 0~3600초를 지정할 수 있습니다. 0은 즉시 획득 시도 후 실패합니다. 시간 초과·연결 손실은 접속정보 없이 검증을 중단합니다.
- `CHECK_DB_URL`이 없으면 DB를 쓰지 않는 단위 테스트는 그대로 실행합니다. DB가 필요한 기존 fixture의 접속 설정 검사는 유지합니다.
- 접속 대상은 mysql+pymysql, localhost/127.0.0.1/::1, spacecube_test만 허용하며 URL query는 charset만 허용합니다. query로 host/db/unix_socket 등을 우회 지정할 수 없습니다.
- 실패·취소 시 연결을 닫고 잠금을 해제합니다. 프로세스가 강제로 종료되어도 DB 연결이 닫히면 MariaDB가 잠금을 해제합니다.

이 잠금은 협력 규약입니다. **잠금 코드가 없는 이전 checkout의 pytest나 별도의 DB 준비·DDL·수동 스크립트는 막지 못합니다.** 관련 작업 브랜치를 갱신한 뒤 병렬 검증하고, DB 초기화·DDL 검사는 pytest와 동시에 실행하지 않습니다. 전체 DB 작업을 모두 포함한 격리가 필요하면 테스트 DB 분리가 별도 필요합니다.

회귀 검증은 `python -m pytest tests -q`로 실행합니다. 실제 DB 검증은 기존 `CHECK_DB_URL`을 사용하며 업무 데이터를 변경하지 않습니다. 하위 프로세스에는 접속정보를 인자가 아닌 환경변수로 전달하고 출력하지 않습니다.
