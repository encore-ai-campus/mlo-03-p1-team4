# AGENTS.md — backend (FastAPI A·B)

루트 `AGENTS.md`에 더해 이 폴더에서 지킨다. 구현 기준은 `docs/백엔드_A_회원_후기_이벤트.md`(A)와 `docs/백엔드_B_공간_예약_결제_크롤링.md`(B)다. 이 폴더의 README는 요약이고, 다르면 두 문서가 맞다.

## 어느 파트 파일인지 먼저 확인

| 파트 | 파일 |
| --- | --- |
| A | `app/main.py`, `app/core/*`, `app/models/base.py`·`user.py`·`review.py`, 각 계층의 `auth`·`users`·`reviews`·`events`·`health` 파일, `scripts/*` |
| B | `app/models/catalog.py`·`venue.py`·`reservation.py`, 각 계층의 `catalog`·`venues`·`reservations`·`internal` 파일, `repositories/slot_repo.py`·`payment_repo.py`, `app/jobs/*` |

파일 목록 전체: `docs/백엔드_A` 2절, `docs/백엔드_B` 2절. 요청받은 파트가 아닌 파일은 고치지 않는다. `app/main.py`에 자기 라우터를 등록하는 한 줄 추가만 B도 할 수 있다.

## 계층 규칙

- `routers`는 입력 검증과 서비스 호출만. SQL을 쓰지 않는다.
- 트랜잭션은 `services`에서 연다. 예약 = `reservations` + `reservation_slots` + `payments` 한 트랜잭션, 취소도 한 트랜잭션.
- SQL은 `repositories`에만. 남의 파트 표는 그 파트의 repository 함수로만 읽는다.
- 오류는 `app/core/errors.py`의 `AppError(code, message, status, detail=None)`로 던진다. 오류 코드는 `app/core/README.md` 표에 있는 것만 쓰고, 새 코드가 필요하면 표와 A·B 문서에 먼저 추가한다.

## DB 세션 고르기 (가장 흔한 버그)

| 의존성 | 쓰는 곳 |
| --- | --- |
| `get_db_write()` (primary) | 모든 쓰기, 로그인·가입·이메일 확인, `get_current_user()`, `/users/me*`, `/reservations/me`, `/reservations/{id}`, 409 뒤 겹친 칸 다시 읽기, `/internal/venues` |
| `get_db_read()` (replica) | `/categories`, `/regions`, `/facilities`, `/venues…`(검색·상세·칸·가능 날짜), `/venues/{id}/reviews`, `/reviews` |

헷갈리면 primary. 틀린 primary는 느릴 뿐이지만, 틀린 replica는 '방금 한 예약이 안 보이는' 버그가 된다. B의 `test_read_routing.py`가 이 표를 검사한다.

## DB 접근 규칙 (11-03 결정: SQLAlchemy 2.1 동기 + PyMySQL, pymongo)

- **엔드포인트는 `def`로 만든다. `async def` 안에서 동기 DB 세션을 쓰지 않는다**(이벤트 루프가 멈춰 서버 전체가 느려짐). FastAPI가 `def`를 스레드 풀에서 돌린다.
- 엔진은 `core/db.py`에 primary·replica 두 개: `create_engine("mysql+pymysql://…", pool_pre_ping=True, pool_recycle=3600)`, 연결마다 `SET time_zone = '+09:00'`(RDS 기본이 UTC라 `CURRENT_TIMESTAMP`가 9시간 어긋남)과 `SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'`(11-04 검증: STRICT가 없으면 잘못된 결제수단이 빈 값, 빠진 동의 시각이 `0000-00-00`으로 오류 없이 저장됨). PyMySQL `connect_args={"init_command": …}`로 건다. 세션은 `sessionmaker(expire_on_commit=False)`.
- 모델은 `app/models/`에 SQLAlchemy 2.0 방식(`DeclarativeBase`, `Mapped`, `mapped_column`)으로, **`db/migrations/*.sql`(지금 `0001_init.sql`)과 표·컬럼 이름·타입·NULL 여부를 똑같이** 쓴다. 모델로 표를 만들지 않는다(`Base.metadata.create_all` 금지). 표는 `db/migrations/*.sql`만 만든다. `test_models_match_db.py`가 둘이 같은지 본다.
- 트랜잭션: 쓰는 서비스는 `try: … db.commit()` / `except: db.rollback(); raise`로 끝낸다. `with db.begin():`은 쓰지 않는다(같은 요청에서 `get_current_user`가 먼저 읽으면 이미 시작된 트랜잭션이라 오류).
- 중복 키는 `IntegrityError`이고 `e.orig.args[0] == 1062`일 때만 업무 오류(409)로 바꾼다. 1062가 나면 **먼저 `db.rollback()`** 하고 겹친 칸을 다시 읽는다(앞서 넣은 `reservations` 행을 되돌림). 같은 칸을 먼저 잡은 트랜잭션이 커밋할 때까지 뒤 요청은 기다렸다가 1062를 받는다(11-04 로컬 시험, `db/tests/check_ddl.py`). CHECK 위반은 4025로 오는데 409로 바꾸지 않는다(앞 단계 검증이 빠진 것). 다른 번호(외래키 1452 등)는 그대로 올려 500으로 둔다.
- 복잡한 조회(검색·칸 집계)는 리포지토리에서 `select()` 또는 `text()` SQL로 써도 된다. 문자열을 이어 붙이지 말고 바인드 변수(`:venue_id`)를 쓴다.
- **연결 수 한도:** RDS `db.t4g.micro` 기본 `max_connections`는 약 35~40이다. 엔진마다 `pool_size=3, max_overflow=2, pool_timeout=3`(프로세스당 최대 5), uvicorn `--workers 2`, 서버 2대 → primary 20개. 풀 대기가 3초를 넘으면 503 `SERVICE_UNAVAILABLE`. 서버·프로세스 수를 늘리면 이 곱을 다시 계산한다(`docs/인프라_트래픽_안정성_검토.md` 5절).
- 실행: `uvicorn app.main:app --workers 2 --limit-concurrency 100 --timeout-keep-alive 5`. DB 쿼리 시간 제한 5초. 유형·지역·시설 목록은 프로세스 메모리에 5분 캐시.
- `get_db_read()`는 replica 연결이 실패(`OperationalError`)하면 primary 세션을 주고 `db_read_fallback_total`을 올린다.
- MongoDB는 `MongoClient(MONGO_URL, serverSelectionTimeoutMS=1000)` 하나를 앱 시작 때 만들어 같이 쓴다. 이벤트 쓰기는 `log_event()` 안의 내부 스레드 풀(작업자 2개, 대기열 1,000건)이 한다. 라우터에서 `BackgroundTasks`를 넘기지 않는다.
- 시각: `get_now()`는 시간대 없는 한국 시각이다. `datetime.now(timezone.utc)` 같은 시간대 붙은 값과 섞지 않는다(비교하면 `TypeError`). UTC는 `log_event` 안에서만, 응답 JSON에는 `+09:00`을 붙인다.

## 예약 코드를 고칠 때 (B)

- 중복 차단은 `reservation_slots` 기본키에 맡긴다. 중복 키(1062) → ROLLBACK → primary에서 겹친 칸을 읽어 409 `SLOT_TAKEN`, `detail.slots`.
- 검증(기간·영업시간·`min_hours`~4칸·인원·결제수단)은 INSERT 전에, `venues`는 primary에서 읽는다.
- 고친 뒤에는 동시성 테스트(같은 칸 동시 50건 → 201 정확히 1건, 409 49건)를 돌린다.

## 이벤트·지표를 쓸 때

- `log_event()`는 응답을 막지 않는다. MongoDB 쓰기는 응답 뒤 백그라운드, 시간 제한 1초, 실패하면 `mongo_event_write_failures_total` +1.
- MongoDB 인덱스·TTL은 `docs/db/mongo_init.js`(DB 담당)가 만든다. 앱 시작 때 만들지 않는다.
- 이벤트 이름은 `docs/백엔드_A` 5-3의 목록만. 이벤트에 이름·이메일·휴대폰을 넣지 않는다(`user_id`만).

## 명령 (예정)

conda 환경 `pro_1`에서 `backend/`를 현재 폴더로 두고 실행한다(패키지를 더하면 `../environment.yml`에도 추가).

```bash
conda run -n pro_1 --no-capture-output uvicorn app.main:app --reload --port 8000
```

```bash
conda run -n pro_1 --no-capture-output pytest
```

- 설정은 `backend/.env`(값)와 `backend/.env.example`(이름만). `.env`는 커밋하지 않는다.
- 테스트 DB는 로컬 MariaDB의 `spacecube_test`(`infra/local`). SQLite로 대신하지 않는다.
- 패키지와 버전은 `../environment.yml`에 고정돼 있다. 새 패키지가 필요하면 묻고, 더하면 버전을 고정한다.
- 토큰은 액세스 토큰만(11-03 결정): JWT HS256 60분, `sub`는 `str(user_id)`, 리프레시·쿠키·로그아웃 API 없음. `get_current_user()`는 primary에서 탈퇴 여부까지 확인. 자세한 표는 `docs/백엔드_A` 5-1.
