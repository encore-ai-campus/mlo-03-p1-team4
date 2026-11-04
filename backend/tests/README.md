# tests — pytest (담당: A·B 각자)

자기가 만든 라우터 파일과 같은 이름으로 테스트를 둡니다. 파일별 확인 항목은 [백엔드_A 7절](../../docs/백엔드_A_회원_후기_이벤트.md), [백엔드_B 8절](../../docs/백엔드_B_공간_예약_결제_크롤링.md).

| 파일 | 담당 | 꼭 확인할 것 |
| --- | --- | --- |
| `test_auth.py` | A | 이메일 중복 409 `EMAIL_TAKEN`, 가입 직후 로그인 성공, 토큰 없이 회원 전용 API 401 |
| `test_users.py`, `test_reviews.py` | A | `password_hash` 없음, 후기 자격 404·403·403·409, 작성 직후 내 후기에 보임 |
| `test_events.py` | A | 51건 400, MongoDB가 꺼져도 202이고 `events.log`에는 남음, replay해도 중복 없음 |
| `test_models_match_db.py` | A | `app/models`의 표·컬럼 이름·NULL 여부가 `spacecube_test`의 실제 표와 같은지 (SQLAlchemy `inspect`) |
| `test_health.py`, `test_db_routing.py`, `test_metrics.py` | A | primary 끊김 503 / replica·MongoDB 끊김 200 degraded, replica 주소가 틀려도 공개 조회 성공 |
| `test_catalog.py`, `test_venues.py` | B | 필터·정렬, 칸 상태(taken·past), 예약 가능 날짜(`min_hours`) |
| `test_reservations.py` | B | 성공 201(표 3개 모두 생김), 범위 밖 400, 취소 후 칸 반납·환불, 예약 직후 `/reservations/me`에 보임 |
| `test_concurrency.py` | B | **같은 칸 동시 50건 → 201 정확히 1건, 409 49건** (MVP 통과 조건), `detail.slots` 정확 |
| `test_jobs.py`, `test_internal.py`, `test_read_routing.py` | B | 완료 배치 멱등, upsert 201·200·400, 공개 조회만 `get_db_read` |

- 테스트 DB는 로컬 MariaDB(`infra/local`)의 `spacecube_test`. SQLite는 제약 동작이 달라 쓰지 않습니다.
- 동시성 테스트는 스레드 50개로 요청을 한꺼번에 보냅니다.

## F-50 지원: 예약 소유권·A 후기 작성 연결

`test_reservation_dependencies.py`는 이전 프로젝트에서 가져온 B 코드의 검증 테스트입니다.
예약·칸·결제 모델의 컬럼·타입·기본값·키·인덱스·CHECK·외래키를 현재
`db/migrations/0001_init.sql`과 대조하고, A 모델과 함께 매퍼가 구성되는지 확인합니다.
실제 MariaDB에서는 예약 상태 3개의 본인·타인·없는 예약 조회와 A 후기 작성 API의
성공·타인 예약·미완료·기한 초과·중복·7일 경계·과거 이용일의 최근 예약을 검증합니다.

- A의 실제 `app.main`·공통 모듈·후기 코드가 필요합니다. 인증 의존성만 테스트 사용자로 바꿉니다.
- `CHECK_DB_URL`에 `mysql+pymysql` 형식의 로컬 `spacecube_test` 접속 정보를 지정해야 합니다.
- 테스트 DB에는 기존 `0001_init.sql`과 `seed.sql`이 적용돼 있어야 합니다. 테스트가 DDL을 자동 실행하지 않습니다.
- 테스트 행은 외부 트랜잭션에서 롤백하고, A 서비스의 commit은 SAVEPOINT로 격리합니다.
- 로그인·후기 목록·예약 생성 API·동시 예약은 이 테스트의 검증 범위가 아닙니다.

저장소 루트의 `pro_1` 환경에서 실행합니다.

```bash
python -m pytest backend/tests/test_reservation_dependencies.py -q
```

11-05 현재 프로젝트의 `localhost:3306/spacecube_test`에서 **14건 통과**했습니다.
`test_catalog.py`까지 포함한 전체 pytest는 **19건 통과**, Starlette TestClient 사용 중단 예정
경고 1건입니다. 비밀번호는 테스트 프로세스에만 전달했고 파일이나 영구 환경변수에 저장하지 않았습니다.
