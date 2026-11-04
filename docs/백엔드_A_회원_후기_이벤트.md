# 백엔드 파트 A — 회원·인증·후기·이벤트 (+ 공통 core)

2026-11-03 확정안 (DB 명세 반영) · 작성 노진산 · 기준: 변경 ERD → `산출물_04_DB명세서.md`(MariaDB 11.4), 11-03 회의, `공간대여_03_FastAPI_API분담.md`(10-30 분담), `산출물_01_요구사항명세서.md`

10-30 분담대로 A는 '사람과 글'과 **공통 core**를 맡습니다. 11-03 결정으로 **자유게시판·댓글이 빠져 글은 후기만** 남았고, 이벤트는 **로그 파일(→ Loki)과 MongoDB** 두 곳에 남깁니다. 대신 core에 일이 늘었습니다. MariaDB primary·replica 두 연결, MongoDB 연결, 헬스체크 3단계, Prometheus `/metrics`, Alloy 설정을 맡습니다. B가 회원 전용 API를 만들려면 `get_current_user()`가 먼저 필요하므로 1일차에 core부터 만듭니다.

## 1. 맡는 범위

| 영역 | 기능 ID | 쓰는 곳 | 읽기만 |
| --- | --- | --- | --- |
| core 공통·관측 | F-64, F-65, F-70 | 로그 파일, `/metrics` | — |
| 회원·인증 | F-01~F-04 | MariaDB `users` | — |
| 후기 | F-41, F-50, F-51 | MariaDB `reviews` | reservations(B 함수로), venues, categories, `v_venue_rating` |
| 이벤트 | F-60 | `events.log`(→ Loki) + MongoDB `user_events` | — |
| 오늘 날짜 | F-63 | — | — |

### 10-30·11-02에서 바뀐 것

| 항목 | 이전 | 지금 | 이유 |
| --- | --- | --- | --- |
| 게시판·댓글 | API 7개, posts·comments 표 | **삭제** | 11-03 결정 3 |
| 관리자·공지 | role, 공지는 관리자만 | **없음** | `users.role` 삭제 |
| 이벤트 저장 | `user_events` 표(10-30) → 로그 파일(11-02) | **로그 파일 + MongoDB `user_events`** (`event_id`로 중복 없이 다시 넣기 가능) | 11-03 결정 1, DB 명세 9-1 |
| 서버 로그·지표 | — | 로그 파일 → Alloy → Loki, `/metrics` → Prometheus | 관측 스택 (F-64, F-65) |
| DB 연결 | 하나 | **primary(쓰기·내 것·인증) + replica(공개 조회)** | master–slave (11-03 팀원 의견) |
| `get_current_user()` | `{user_id, role}` | **`{user_id}`**, primary에서 확인 | role 삭제, 복제 지연 |
| `log_event()` | `(db, session_id, user_id, event_type, room_id, payload)` | **`(session_id, user_id, event_type, venue_id=None, category=None, payload=None, is_synthetic=False)`**: `events.log`에 바로 한 줄 + MongoDB에 백그라운드 쓰기 | 저장소 변경 |
| 오늘 | 서버 날짜 / `get_sim_today()`(11-02) | **`get_today()`**. 기본은 실제 날짜 | 11-03 제안 2의 ③ |
| 공간별 후기 경로 | `/rooms/{room_id}/reviews` | `/venues/{venue_id}/reviews` | rooms 삭제 |
| 평점 뷰 | `v_room_rating` | `v_venue_rating` | DB 담당에게 요청 |
| `/health` | DB 확인 | **primary·replica·MongoDB 3단계** | DB 3대 |

`get_current_user`, `log_event`, 후기 경로, 뷰 이름은 여러 파트가 같이 쓰는 약속이라 회의에서 확인한 뒤 확정합니다.

## 2. 파일

```
backend/app/
  main.py                    # [A] 라우터 등록, CORS, 예외 처리기, 요청 로그 미들웨어, 시작·종료 시 연결 관리
  core/                      # [A]
    config.py                # .env 읽기
    db.py                    # SQLAlchemy primary·replica 엔진(PyMySQL, 세션 시간대 +09:00), get_db_write(), get_db_read()
    mongo.py                 # pymongo 클라이언트(시간 제한 1초), user_events 컬렉션 (인덱스는 mongo_init.js가 만듦)
    security.py              # bcrypt, JWT
    deps.py                  # get_current_user(), get_optional_user()
    errors.py                # AppError + 처리기
    pagination.py            # {"items","page","size","total"}
    events.py                # log_event(): events.log 한 줄 + MongoDB는 내부 스레드 풀(2개, 대기열 1,000건)
    metrics.py               # /metrics (prometheus-fastapi-instrumentator), 앱 지표 정의
    logging.py               # 서버 로그 app.log·이벤트 로그 events.log (JSON 한 줄)
    clock.py                 # get_today(), get_now()
  models/    base.py user.py review.py   # SQLAlchemy 모델 (DDL과 같게)
  routers/   auth.py users.py reviews.py events.py health.py
  schemas/   auth.py users.py reviews.py events.py
  services/  auth_service.py user_service.py review_service.py
  repositories/  user_repo.py review_repo.py
backend/tests/   test_auth.py test_users.py test_reviews.py test_events.py test_health.py test_db_routing.py test_models_match_db.py
backend/scripts/replay_events.py                # [A] events.log → MongoDB 다시 넣기 (event_id로 중복 무시)
infra/monitoring/  alloy.config                # [A] 로그 파일 → Loki, 로컬 exporter → Prometheus
                   docker-compose.yml          # [A] Prometheus · Loki · Grafana (모니터링 EC2)
                   grafana/dashboards/*.json   # [A] 서비스 상태 · 예약 경쟁 · 사용자 흐름
```

### `.env` 키 (값은 `.env.example`에 이름만)

| 키 | 쓰임 |
| --- | --- |
| `DB_WRITE_URL` | RDS primary 엔드포인트 |
| `DB_READ_URL` | RDS replica 엔드포인트. 비우면 primary를 씀(로컬 개발) |
| `MONGO_URL`, `MONGO_DB` | MongoDB (인증 포함) |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | 토큰 (초안 60분) |
| `LOG_DIR`, `SERVER_NAME` | `app.log`·`events.log` 위치, `api-1` / `api-2` |
| `CORS_ORIGINS` | 개발 서버 주소 |
| `TODAY_OVERRIDE` | 비우면 실제 날짜. 시연·테스트에서만 날짜 고정 |

## 3. 다른 파트에 주는 것 (약속)

| 이름 | 형태 | 쓰는 곳 |
| --- | --- | --- |
| `get_db_write()` | primary 세션. 쓰기, '내 것' 조회, 인증 | A·B |
| `get_db_read()` | replica 세션. 공개 조회만. replica 연결이 안 되면 primary로 대체하고 서버 로그에 경고 | A·B |
| `get_current_user()` | → `CurrentUser(user_id)`. 토큰 없음·틀림·탈퇴 회원이면 401. **primary**에서 확인 | B 예약 API |
| `get_optional_user()` | 토큰 없으면 `None` | 이벤트 |
| `AppError(code, message, status, detail=None)` | `{"code","message","detail"}`로 바뀌는 예외 | A·B |
| `paginate()` | `{"items","page","size","total"}` | A·B |
| `log_event(session_id, user_id, event_type, venue_id=None, category=None, payload=None, is_synthetic=False)` | ① `event_id`(UUID)를 붙여 `events.log`에 **바로** 한 줄(→ Loki) ② MongoDB 쓰기는 `core/events.py` 안의 **내부 스레드 풀**(작업자 2개, 대기열 1,000건)에 넘기고 바로 돌아옴. 시간 제한 1초, 실패·대기열 넘침이면 `mongo_event_write_failures_total` +1(그 이벤트는 `events.log`에 있어 replay 가능). `category`는 공간 유형 코드(B는 읽은 공간 값, 프론트 이벤트는 A가 `venue_id`로 채움, 5분 캐시). 라우터·서비스·배치 어디서나 같은 호출(11-03 A1 확정) | B 예약 서비스, 배치 |
| `reservation_counter` | Prometheus 카운터 `reservation_total{result="ok"\|"conflict"\|"cancel"}` | B 예약 서비스 |
| `get_today() -> date`, `get_now() -> datetime` | Asia/Seoul 오늘·지금. **`get_now()`는 시간대 없는(naive) 한국 시각**이라 MariaDB `DATETIME`과 그대로 비교·저장. UTC는 `log_event` 안에서만(MongoDB `ts`), 응답 JSON에는 `+09:00`을 붙여 냄. `TODAY_OVERRIDE`가 있으면 그 날짜 + 실제 시각(테스트 전용) (11-03 A1 확정) | A·B 전체 |
| `is_synthetic_request(request) -> bool` | 헤더 `X-Synthetic: 1` | A 가입, B 예약 |
| `get_session_id(request) -> str \| None` | 헤더 `X-Session-Id`(프론트가 모든 요청에 붙이는 UUID). 없거나 형식이 틀리면 `None` | B 예약 서비스가 `log_event`에 넘김 → 서버 이벤트와 프론트 이벤트를 같은 세션으로 묶음(이탈 계산에 필요) |

어느 의존성을 쓸지는 **경로 규칙표**(`산출물_02` §2)를 따릅니다. 헷갈리면 primary를 씁니다. 틀린 primary는 느릴 뿐이지만, 틀린 replica는 '방금 한 예약이 안 보이는' 버그가 됩니다.

## 4. 다른 파트에서 받는 것

| 이름 | 제공 | 쓰임 |
| --- | --- | --- |
| `reservation_repo.get_owned(db, user_id, reservation_id)` → `(reservation_id, venue_id, reserve_date, start_hour, end_hour, status, created_at)` 또는 `None` | B | 후기 작성 자격 (primary 세션으로 호출). `created_at`은 후기 기한 `max(이용일, 예약한 날)` 계산에 씀 |
| 뷰 `v_venue_rating(venue_id, rating_avg, review_count)` | DB | 후기 모아보기 요약 |
| MariaDB 표·기초 데이터, MongoDB 사용자·권한 | DB | 테스트·배포 |

## 5. API

경로 앞 `/api`는 Nginx가 붙입니다. 인증: `-` 누구나, `회원` 토큰 필요. DB 열: W primary, R replica.

### 5-1. 회원·인증

| 메서드 | 경로 | 인증 | DB | 기능 | 성공 | 주요 오류 |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /auth/email-check?email= | - | W | F-01 | 200 `{"available": true}` | 400 |
| POST | /auth/signup | - | W | F-01 | 201 `{"user_id": 42}` | 409 `EMAIL_TAKEN`, 400 `VALIDATION` |
| POST | /auth/login | - | W | F-02 | 200 `{"access_token","token_type":"bearer","expires_in":3600}` | 401 `INVALID_CREDENTIALS` |
| GET | /users/me | 회원 | W | F-03 | 200 내 정보 | 401 |
| PATCH | /users/me | 회원 | W | F-03 | 200 | 400 |
| PATCH | /users/me/password | 회원 | W | F-03 | 204 | 400 `WRONG_PASSWORD` |
| DELETE | /users/me | 회원 | W | F-04 | 204 | 401 |

이메일 중복 확인도 primary입니다. replica에서 읽으면 방금 가입한 이메일이 '사용 가능'으로 나올 수 있습니다. 그래도 최종 판정은 UNIQUE 제약이 합니다.

회원가입 요청:

```json
{"email": "kim@example.com", "password": "8자 이상", "name": "김공간", "phone": "010-1234-5678",
 "birth": "990315", "gender_digit": "1", "marketing_agreed": false,
 "terms_agreed": true, "privacy_agreed": true}
```

| 칸 | 검증 |
| --- | --- |
| email | 형식, 100자 이내, 중복 불가(탈퇴하면 이메일을 바꿔 두므로 같은 이메일로 다시 가입 가능) |
| password | 8자 이상·72바이트 이하(bcrypt 5는 넘으면 오류), bcrypt 해시로만 저장 |
| birth | 숫자 6자리, 실제 있는 날짜(YYMMDD) |
| gender_digit | `1`~`4` (DB CHECK와 같게, DB 담당과 확인) |
| marketing_agreed | 필수 boolean(값은 선택) |
| terms_agreed, privacy_agreed | 둘 다 `true`여야 함. 서버가 받은 시각(`get_now()`)을 `terms_agreed_at`·`privacy_agreed_at`에 저장 (11-03 A2) |
| 나이 | birth + gender_digit(1·2 → 1900년대, 3·4 → 2000년대)로 만 나이 계산, **만 14세 미만이면 400 `VALIDATION`**(`reason: "under_14"`) |
| is_synthetic | 본문으로 받지 않음. `X-Synthetic: 1` 헤더일 때만 true |

탈퇴(`DELETE /users/me`, 11-03 A4 확정)는 한 트랜잭션에서 개인정보를 바로 지웁니다: `deleted_at = get_now()`, `name = '탈퇴회원'`, `phone = NULL`, `birth = '000000'`, `email = 'deleted+{user_id}@invalid'`, `password_hash`는 무작위 값의 해시로 바꿈, `marketing_agreed = false`. 예약·결제·후기는 `user_id`로 남아 통계·정산이 유지됩니다. 이용 예정(`confirmed`) 예약이 있으면 먼저 취소하라고 409 대신 안내만 하고 탈퇴는 진행합니다(예약은 남음, 초안). 탈퇴 후 옛 이메일로 로그인하면 `INVALID_CREDENTIALS`.

`GET /users/me` 응답에 `password_hash`는 넣지 않습니다. 생년월일·성별 숫자는 이 응답에만 나옵니다.

토큰 (11-03 결정: **액세스 토큰만, Bearer**):

| 항목 | 정한 것 |
| --- | --- |
| 형식 | JWT HS256, `JWT_SECRET`(32바이트 이상). 클레임은 `sub`(user_id를 **문자열**로, PyJWT 2.10부터 숫자면 오류), `iat`, `exp` 세 개만. 이름·이메일·role은 넣지 않음 |
| 수명 | `JWT_EXPIRE_MINUTES` 60분. 리프레시 토큰 없음, 연장 없음 |
| 전달 | 로그인 응답 본문 → 프론트가 `Authorization: Bearer <토큰>`. 쿠키 안 씀(CORS·CSRF 설정 불필요) |
| 확인 | `get_current_user()`: `jwt.decode(…, algorithms=["HS256"])` → primary에서 `users` 행이 있고 `deleted_at IS NULL`인지 → 아니면 401 `UNAUTHORIZED`. 만료·서명 오류도 401 |
| 로그아웃 | 서버 API 없음. 프론트가 토큰을 지움. 서버 쪽 폐기 목록 없음 |
| 알고 넘어가는 것 | 비밀번호를 바꿔도 이미 발급된 토큰은 만료까지 유효(1차 범위 밖). 탈퇴는 `deleted_at` 확인으로 바로 막힘 |
| 프론트 | 회원 API가 401이면 로그아웃 후 `/login?next=<지금 주소>`로, 고르던 칸은 유지(`프론트_변경목록_11-03.md`) |

### 5-2. 후기 (회원이 쓰는 유일한 글)

| 메서드 | 경로 | 인증 | DB | 기능 | 설명 |
| --- | --- | --- | --- | --- | --- |
| POST | /reservations/{reservation_id}/review | 회원 | W | F-50 | 내 예약 + completed + 기한 안 + 아직 안 씀 |
| PATCH | /reviews/{review_id} | 회원 | W | F-50 | 작성자만 |
| DELETE | /reviews/{review_id} | 회원 | W | F-50 | 작성자만, `deleted_at` |
| GET | /venues/{venue_id}/reviews?page= | - | R | F-51 | 공간 상세 하단, 최신순 |
| GET | /reviews?category=&sort=&page=&size= | - | R | F-51 | 후기 모아보기. sort: `recent`(기본)·`high`·`low` |
| GET | /users/me/reviews | 회원 | W | F-41 | 내 후기 (방금 쓴 후기가 바로 보여야 함) |

작성 자격 판정 순서:

1. `get_owned()`가 `None` → 404 `RESERVATION_NOT_FOUND` (남의 예약도 404)
2. status ≠ completed → 403 `NOT_COMPLETED`
3. `max(이용일, 예약한 날) + 7일 < get_today()` → 403 `REVIEW_PERIOD_OVER` (11-03 날짜 결정: 지난 날짜로 예약해도 예약한 날부터 7일은 후기를 쓸 수 있음)
4. 같은 예약 후기 있음 → 409 `REVIEW_EXISTS` (DB UNIQUE가 최종 판정)

목록 항목:

```json
{"review_id": 3, "venue_id": 7, "venue_name": "서대문구 스터디룸 3호", "category": "studyroom",
 "rating": 5, "content": "…", "author": "김**", "created_at": "2026-11-03T13:10:00+09:00"}
```

작성자 이름은 첫 글자만 보이게 가립니다. 삭제된 후기는 숨기고, 탈퇴 회원 후기는 내용·별점을 남기고 작성자만 '탈퇴한 회원'으로 표시합니다(11-03 A4 확정). 평점 통계에도 그대로 들어갑니다.

### 5-3. 이벤트

| 메서드 | 경로 | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | /events | - (토큰 있으면 user_id 붙임) | 묶음 최대 50건. 검증 → `events.log`에 쓰기 → **202** → MongoDB `insert_many(ordered=False)` |
| GET | /metrics | 내부(sg-mon만) | Prometheus 수집용. Nginx로 밖에 내보내지 않음 |

```json
{"session_id": "4b1c…", "events": [
  {"event_type": "select_slot", "venue_id": 7, "payload": {"hour": 14}, "occurred_at": "2026-11-03T14:03:11.204+09:00"}
]}
```

- 받는 `event_type`(프론트): `search`, `view_venue`, `view_dates`, `select_slot`, `reserve_try`, `reserve_cancel`, `review_create`, `login`, `signup`. (`view_room` → `view_venue`, 프론트 수정)
- 서버가 남기는 것: `reserve_ok`, `reserve_conflict`, `reserve_cancel_ok`.
- **허용 목록에 없는 `event_type`은 그 건만 버립니다**(11-03 결정). 나머지는 저장하고 202 `{"accepted": n, "ignored": [{"event_type": "…", "count": k}]}`, 서버 로그에 경고 한 줄. 형식이 깨진 묶음(51건 이상, `session_id` 없음 등)만 400입니다.
- `unselect_slot`·`abandon`은 받지 않습니다(11-03 결정). 이탈은 분석에서 계산합니다: 같은 세션에 `select_slot`은 있고 `reserve_ok`가 없으면 이탈(`산출물_04` 8절).
- `venue_id`는 이벤트의 맨 위 칸으로 받습니다. `payload` 안의 `venue_id`·`room_id`는 공간 값으로 쓰지 않습니다.
- 11-02에 있던 `pay_try`·`pay_done`은 홀딩이 없어져 `reserve_try`와 같은 시점이라 뺍니다. `post_view`·`post_create`는 게시판 삭제로 뺍니다. 프론트도 같이 고칩니다.
- 서버가 붙이는 칸: `event_id`(UUID), `ts`(받은 실제 시각, UTC로 저장), `client_ts`(브라우저 `occurred_at`), `server`, `user_id`, `category`, `is_synthetic`. 문서 형식과 검증 규칙은 `산출물_04` 8절, `docs/db/mongo_init.js`.
- 이벤트에는 이름·이메일·휴대폰을 넣지 않습니다(`user_id`만).

MongoDB 인덱스·TTL(1년)은 DB 담당의 `mongo_init.js`가 만듭니다. A는 앱 시작 때 만들지 않습니다(두 서버가 동시에 만들지 않게).

로그 파일 두 개:

| 파일 | 내용 | Loki 라벨 |
| --- | --- | --- |
| `app.log` | 요청(경로·상태·ms·user_id)·오류 | `job=api, server, level` |
| `events.log` | 이벤트 JSON (MongoDB 문서와 같은 모양) | `job=events, server, event_type` |

user_id·venue_id·session_id는 라벨이 아니라 본문에 둡니다. MongoDB가 멈췄던 시간의 이벤트는 `backend/scripts/replay_events.py`로 `events.log`에서 다시 넣습니다(`event_id` 중복은 무시).

### 5-5. 지표 (`/metrics`)

| 지표 | 종류 | 쓰임 |
| --- | --- | --- |
| `http_requests_total{handler,method,status}` | 카운터 | 서버별 요청 수 (라운드로빈 확인) |
| `http_request_duration_seconds` | 히스토그램 | p50·p95 (replica 있음·없음 비교) |
| `reservation_total{result}` | 카운터 | 예약 성공·충돌·취소 (B가 올림) |
| `mongo_event_write_failures_total` | 카운터 | 이벤트 유실 감시 |
| `db_read_fallback_total` | 카운터 | replica → primary 대체 횟수 |

그 밖의 exporter(mysqld·mongodb·node·nginx)는 Alloy가 각 서버에서 긁어 Prometheus로 보냅니다(`infra/monitoring/alloy.config`).

### 5-6. 헬스체크

| 상태 | 응답 | Nginx |
| --- | --- | --- |
| primary `SELECT 1` 실패 | 503 | 이 서버를 뺌 |
| replica 실패 | 200 `{"status":"degraded","replica":"down"}` | 유지 (읽기는 primary로 대체) |
| MongoDB 실패 | 200 `{"status":"degraded","mongo":"down"}` | 유지 (이벤트만 유실) |
| 전부 정상 | 200 `{"status":"ok"}` | 유지 |

각 확인에 0.5초 시간 제한을 둡니다. 느린 replica 때문에 헬스체크가 실패하지 않게 하려는 것입니다.

## 6. 공통 규칙 (A가 먼저 만들고 B가 따름)

- 오류 `{"code","message","detail"}`. 400 검증, 401 인증, 403 권한, 404 없음, 409 충돌. Pydantic 검증 오류도 이 형식(`VALIDATION`)으로 바꿉니다.
- 오류 코드는 [`오류코드.md`](오류코드.md)에 있는 것만 씁니다(공통 8개 + A 8개 + B 10개, 사용자 문구·`detail` 모양·프론트 동작 포함). 만료 토큰은 `TOKEN_EXPIRED`, 처리 못 한 예외는 `INTERNAL_ERROR` + `request_id`, primary 끊김은 `SERVICE_UNAVAILABLE`.
- 목록 `{"items","page","size","total"}`, size 최대 50.
- 시각: MariaDB는 Asia/Seoul, MongoDB는 UTC로 저장하고 응답할 때 `+09:00`으로 바꿉니다. 날짜는 `YYYY-MM-DD`.
- 소프트 삭제된 행은 모든 조회에서 기본으로 뺍니다.
- 가상 데이터: 헤더 `X-Synthetic: 1` → MariaDB `is_synthetic = true`, 이벤트에도 같은 값.

## 7. 테스트

| 파일 | 확인할 것 |
| --- | --- |
| test_auth.py | 가입 성공, 이메일 중복 409, birth·gender_digit 형식 오류 400, **가입 직후 로그인 성공**, 탈퇴 회원 로그인 401, 만료 토큰 401 |
| test_users.py | 내 정보에 password_hash 없음, 수정, 비밀번호 변경, **탈퇴 후 이름·휴대폰·이메일이 지워지고 예약·후기는 남음, 같은 이메일로 다시 가입 201, 탈퇴 회원 후기 작성자 '탈퇴한 회원'** |
| test_reviews.py | 자격 4단계 각각(404·403·403·409), 남의 후기 수정 403, 공간별·전체 정렬, 이름 가림, **작성 직후 내 후기에 보임** |
| test_events.py | 51건 400, 허용 안 된 event_type은 그 건만 빠지고 202 + `ignored`, 202를 먼저 받음, MongoDB 문서 형식, X-Synthetic 반영, **MongoDB가 꺼져도 202이고 events.log에는 남음**, replay로 다시 넣어도 중복 없음 |
| test_metrics.py | `/metrics`에 요청·예약 카운터가 나옴 |
| test_health.py | primary 끊김 503, replica 끊김 200 degraded, MongoDB 끊김 200 degraded |
| test_db_routing.py | `DB_READ_URL`이 틀려도 공개 조회가 primary로 대체되어 성공 |

MariaDB 테스트는 `spacecube_test` 스키마, MongoDB 테스트는 `spacecube_test` DB에서 돌리고 끝나면 비웁니다. 복제 지연은 로컬에서 재현하기 어려우니, '내 것' 경로가 `get_db_write`를 쓰는지 코드 검사(라우터 의존성 목록)로 확인합니다.

## 8. 작업 순서 (1차 일정: 1일 구현 · 2일 배포 · 3일 자동화·발표)

| 일차 | 할 일 | 끝났다는 기준 |
| --- | --- | --- |
| 1일 오전 | core 전부(설정·두 DB 연결·MongoDB·JWT·오류·페이지·로그·`get_today`), /health | B가 `get_current_user()`·`get_db_*`를 붙여 씀 |
| 1일 오후 | 회원가입·로그인·내 정보·탈퇴, 후기, /events | test_auth·test_reviews·test_events 통과 |
| 2일 | 배포: `.env` 두 DB·MongoDB 주소, 모니터링 EC2(Docker Compose), Alloy → Loki·Prometheus | 서버 2대에서 /health ok, Grafana에 로그·지표, MongoDB에 이벤트 |
| 3일 | 설치 스크립트화, Grafana 대시보드 3개, 발표용 이벤트 집계(점유율·전환율) | 새 인스턴스에서 스크립트 한 번으로 기동 |

일정이 3일이면 리프레시 토큰, 후기 수정 기한 같은 것은 1차에서 뺍니다.

## 9. 확인 필요

| # | 질문 | 이 문서의 가정 |
| --- | --- | --- |
| 1 | `get_current_user()` 반환에서 role 제거 | **확정(11-03 A1)**: `CurrentUser(user_id)` |
| 2 | `log_event()` 인자·저장소 변경 | **확정(11-03 A1)**: 3절 형태(`category` 추가), 로그 파일 + MongoDB(내부 스레드 풀) |
| 3 | 오늘 날짜 방식 | **결정(11-03)**: 실제 날짜(`get_today()`·`get_now()`), 가상 날짜 없음 |
| 4 | 후기 작성 기한 | **결정(11-03)**: `max(이용일, 예약한 날)`부터 7일 |
| 5 | gender_digit 허용 값 | 1~4 |
| 6 | MongoDB 드라이버 | **결정(11-03)**: pymongo 4 (동기), `log_event` 안의 내부 스레드 풀로 쓰기(FastAPI `BackgroundTasks` 안 씀) |
| 7 | ORM·드라이버 | **결정(11-03)**: SQLAlchemy 2.1 동기 + PyMySQL, 마이그레이션은 SQL 파일. 규칙은 `backend/AGENTS.md` 'DB 접근 규칙' |
