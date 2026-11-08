# 백엔드 파트 A — 회원·인증·후기·이벤트 (+ 공통 core)

2026-11-03 확정안 (DB 명세 반영) · 작성 노진산 · 기준: 변경 ERD → `산출물_04_DB명세서.md`(MariaDB 11.4), 11-03 회의, `공간대여_03_FastAPI_API분담.md`(10-30 분담), `산출물_01_요구사항명세서.md`

10-30 분담대로 A는 '사람과 글'과 **공통 core**를 맡습니다. 11-03 결정으로 **자유게시판·댓글이 빠져 글은 후기만** 남았고, 이벤트는 **로그 파일(→ Loki)과 MongoDB** 두 곳에 남깁니다. 대신 core에 일이 늘었습니다. MariaDB primary·replica 두 연결, MongoDB 연결, 헬스체크 3단계, Prometheus `/metrics`, Alloy 설정을 맡습니다. B가 회원 전용 API를 만들려면 `get_current_user()`가 먼저 필요하므로 1일차에 core부터 만듭니다.

## 1. 맡는 범위

| 영역 | 기능 ID | 쓰는 곳 | 읽기만 |
| --- | --- | --- | --- |
| core 공통·관측 | F-64, F-65, F-70 | 로그 파일, `/metrics` | — |
| 회원·인증 | F-01~F-04 | MariaDB `users` | — |
| 후기 | F-41, F-50, F-51 | MariaDB `reviews` | reservations(B 함수로), venues, categories, `v_venue_rating` |
| 이벤트 | F-60 | `events.log`(→ Loki) + MongoDB `space_rental_analytics.events` | — |
| 오늘 날짜 | F-63 | — | — |

### 10-30·11-02에서 바뀐 것

| 항목 | 이전 | 지금 | 이유 |
| --- | --- | --- | --- |
| 게시판·댓글 | API 7개, posts·comments 표 | **삭제** | 11-03 결정 3 |
| 관리자·공지 | role, 공지는 관리자만 | **없음** | `users.role` 삭제 |
| 이벤트 저장 | `user_events` 표(10-30) → 로그 파일(11-02) | **로그 파일 + MongoDB `space_rental_analytics.events`** (`event_id`로 중복 없이 다시 넣기 가능) | PR #58·#60 PM 결정 |
| 서버 로그·지표 | — | 로그 파일 → Alloy → Loki, `/metrics` → Prometheus | 관측 스택 (F-64, F-65) |
| DB 연결 | 하나 | **primary(쓰기·내 것·인증) + replica(공개 조회)** | master–slave (11-03 팀원 의견) |
| `get_current_user()` | `{user_id, role}` | **`{user_id}`**, primary에서 확인 | role 삭제, 복제 지연 |
| `log_event()` | `(db, session_id, user_id, event_type, room_id, payload)` | **`(session_id, user_id, event_type, venue_id=None, category=None, payload=None, is_synthetic=False, *, products=None)`**: 앞 7개 인자 유지, 상품 스냅샷 선택 인자 추가 | PR #60 PM 승인 |
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
    mongo.py                 # pymongo 클라이언트(시간 제한 1초), space_rental_analytics.events 컬렉션 (인덱스는 mongo_init.js가 만듦)
    event_document.py        # 새 15종 문서 조립·필수 구조·상품 조건·개인정보 제거
    security.py              # bcrypt, JWT
    deps.py                  # get_current_user(), get_optional_user()
    errors.py                # AppError + 처리기
    pagination.py            # {"items","page","size","total"}
    events.py                # log_event(): events.log 한 줄 + MongoDB는 내부 스레드 풀(2개, 대기열 1,000건)
    metrics.py               # /metrics (prometheus-fastapi-instrumentator), 앱 지표 정의
    logging.py               # 서버 로그 app.log·이벤트 로그 events.log (JSON 한 줄)
    clock.py                 # get_today(), get_now(), override_business_time(), get_event_time()
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
| `LOG_DIR`, `SERVER_NAME` | `app.log`·`events.log` 위치, API 프로세스는 `api-1` / `api-2`. 백필 생성기는 생성기 프로세스 실행 때만 `SERVER_NAME=generator`를 지정 |
| `CORS_ORIGINS` | 개발 서버 주소 |
| `TODAY_OVERRIDE` | 비우면 실제 날짜. 시연·테스트에서만 날짜 고정 |

## 3. 다른 파트에 주는 것 (약속)

| 이름 | 형태 | 쓰는 곳 |
| --- | --- | --- |
| `get_db_write()` | primary 세션. 쓰기, '내 것' 조회, 인증 | A·B |
| `get_db_read()` | replica 세션. 공개 조회만. replica 연결이 안 되면 primary로 대체하고 서버 로그에 경고 | A·B |
| `get_current_user()` | → `CurrentUser(user_id)`. 토큰 없음·틀림·탈퇴 회원이면 401. **primary**에서 확인 | B 예약 API |
| `review_repo.get_review_ids(db, reservation_ids) -> dict[int, int]` | B가 본인 소유로 확인한 현재 페이지의 예약 ID 목록과 primary 세션을 전달. A가 삭제된 후기를 포함해 `reviews`에서 SQL 한 번으로 `{reservation_id: review_id}`를 반환. 후기가 없으면 매핑에서 제외, 빈 입력은 SQL 없이 `{}`. commit·rollback 없음 (#45) | B 내 예약 목록·상세의 `review_id` |
| `get_optional_user()` | 토큰 없으면 `None` | 이벤트 |
| `AppError(code, message, status, detail=None)` | `{"code","message","detail"}`로 바뀌는 예외 | A·B |
| `paginate()` | `{"items","page","size","total"}` | A·B |
| `log_event(session_id, user_id, event_type, venue_id=None, category=None, payload=None, is_synthetic=False, *, products=None)` | 앞의 7개 인자는 변경하지 않는다. #60 PM 승인에 따라 B는 확정 예약에서 만든 상품 스냅샷을 `products=`로 전달한다. A는 새 15종 구조를 조립해 `events.log`에 먼저 기록하고 MongoDB `space_rental_analytics.events`에는 내부 2작업자·1,000건 대기열로 보낸다. 파일 실패는 이벤트 API 503, MongoDB 실패는 202 및 재적재 대상이다. 현재 B 구형 이벤트 호출은 변경 전까지 새 이벤트로 저장되지 않는다. | B 예약 서비스, 배치 |
| `reservation_counter` | Prometheus 카운터 `reservation_total{result="ok"\|"conflict"\|"cancel"}` | B 예약 서비스 |
| `get_today() -> date`, `get_now() -> datetime` | Asia/Seoul 오늘·지금. **`get_now()`는 시간대 없는(naive) 한국 시각**이라 MariaDB `DATETIME`과 그대로 비교·저장. `override_business_time(value)`는 생성기 백필에서 회원·후기 서비스와 가입 스키마 검증이 참조하는 업무 시각만 `with` 블록 안에서 임시 고정하며, 블록을 나가면 복원한다. 이벤트 빌더의 과거 행동 시각은 `occurred_at` 인자로 전달한다. `get_event_time()`은 이 업무 시각 재정의와 무관하게 실제 UTC 적재 시각(`received_at`)을 반환한다. `TODAY_OVERRIDE`는 테스트 전용 (11-03 A1 확정, #75) | A·B 전체·생성기 |
| `is_synthetic_request(request) -> bool` | 헤더 `X-Synthetic: 1` + `X-Synthetic-Key`(= `.env` `SYNTHETIC_API_KEY`)일 때만 true. `X-Synthetic`이 있는데 키가 없거나 틀리면 `AppError("UNAUTHORIZED", …, 401)` (11-05 A6) | A 가입, B 예약 |
| `get_session_id(request) -> str \| None` | 헤더 `X-Session-Id`(프론트가 모든 요청에 붙이는 UUID). 없거나 형식이 틀리면 `None` | B 예약 서비스가 `log_event`에 넘김 → 서버 이벤트와 프론트 이벤트를 같은 세션으로 묶음(이탈 계산에 필요) |

후기 목록의 공유 계약(#43 PM 승인): B의 `reservation_repo.review_context_query(*, active_only: bool = True) -> Select`를 A의 `review_repo`가 직접 import합니다. 반환 열은 `reservation_id`, `venue_id`, `venue_name`, `category`(`categories.code`)이며, B는 조회식만 만들고 DB 실행·commit·rollback은 하지 않습니다. 공개 후기 목록은 기본값으로 비활성 공간을 숨기고, 내 후기는 `active_only=False`로 기록을 유지합니다. A가 후기·회원과 결합해 필터·정렬·페이지를 계산하며 공개 목록은 replica, 내 후기는 primary에서 실행합니다. `main.py` 등록 방식은 사용하지 않습니다. `review_create`는 후기 생성 201 뒤 프론트만 전송합니다.

어느 의존성을 쓸지는 **경로 규칙표**(`산출물_02` §2)를 따릅니다. 헷갈리면 primary를 씁니다. 틀린 primary는 느릴 뿐이지만, 틀린 replica는 '방금 한 예약이 안 보이는' 버그가 됩니다.

## 4. 다른 파트에서 받는 것

| 이름 | 제공 | 쓰임 |
| --- | --- | --- |
| `reservation_repo.get_owned(db, user_id, reservation_id)` → `(reservation_id, venue_id, reserve_date, start_hour, end_hour, status, created_at)` 또는 `None` | B | 후기 작성 자격 (primary 세션으로 호출). `created_at`은 후기 기한 `max(이용일, 예약한 날)` 계산에 씀 |
| `reservation_repo.count_cancellable(db, user_id)` → `int` | B | 탈퇴 전 확인(primary 세션으로 호출). 0보다 크면 409 `HAS_UPCOMING_RESERVATION` (11-05) |
| `reservation_repo.review_context_query(*, active_only: bool = True)` → `Select` | B | 후기 목록용 예약·공간·유형 조회식. 3절의 공유 계약에 따라 직접 import (#43) |
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
| POST | /auth/logout | 회원 | W | F-02 | 204 (프론트가 저장한 토큰 삭제) | 401 |
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
| phone | 프론트와 같은 휴대폰 형식 `^01[016789]-?\d{3,4}-?\d{4}$` (하이픈 포함 또는 생략) |
| birth | 숫자 6자리, 실제 있는 날짜(YYMMDD) |
| gender_digit | `1`~`4` (DB CHECK와 같게, DB 담당과 확인) |
| marketing_agreed | 필수 boolean(값은 선택) |
| terms_agreed, privacy_agreed | 둘 다 `true`여야 함. 서버가 받은 시각(`get_now()`)을 `terms_agreed_at`·`privacy_agreed_at`에 저장 (11-03 A2) |
| 나이 | birth + gender_digit(1·2 → 1900년대, 3·4 → 2000년대)로 만 나이 계산, **만 14세 미만이면 400 `VALIDATION`**(`reason: "under_14"`) |
| is_synthetic | 본문으로 받지 않음. `X-Synthetic: 1` + `X-Synthetic-Key`(= `.env` `SYNTHETIC_API_KEY`)일 때만 true |

탈퇴(`DELETE /users/me`, 11-03 A4 확정)는 한 트랜잭션에서 개인정보를 바로 지웁니다: `deleted_at = get_now()`, `name = '탈퇴회원'`, `phone = NULL`, `birth = '000000'`, `email = 'deleted+{user_id}@invalid'`, `password_hash`는 무작위 값의 해시로 바꿈, `marketing_agreed = false`. 예약·결제·후기는 `user_id`로 남아 통계·정산이 유지됩니다. **취소할 수 있는 예약(`confirmed`이고 아직 시작 전)이 있으면 탈퇴하지 않고 409 `HAS_UPCOMING_RESERVATION`**(`detail.count`)을 돌려줍니다(11-05 결정). 개수는 B의 `reservation_repo.count_cancellable()`로 같은 primary 세션에서 셉니다. 이용 중인 예약은 취소할 수 없으므로 막지 않고, 끝나면 배치가 `completed`로 바꿉니다. 탈퇴 후 옛 이메일로 로그인하면 `INVALID_CREDENTIALS`.

`GET /users/me` 응답에 `password_hash`는 넣지 않습니다. 생년월일·성별 숫자는 이 응답에만 나옵니다.

토큰 (11-03 결정: **액세스 토큰만, Bearer**):

| 항목 | 정한 것 |
| --- | --- |
| 형식 | JWT HS256, `JWT_SECRET`(32바이트 이상). 클레임은 `sub`(user_id를 **문자열**로, PyJWT 2.10부터 숫자면 오류), `iat`, `exp` 세 개만. 이름·이메일·role은 넣지 않음 |
| 수명 | `JWT_EXPIRE_MINUTES` 60분. 리프레시 토큰 없음, 연장 없음 |
| 전달 | 로그인 응답 본문 → 프론트가 `Authorization: Bearer <토큰>`. 쿠키 안 씀(CORS·CSRF 설정 불필요) |
| 확인 | `get_current_user()`: `jwt.decode(…, algorithms=["HS256"])` → primary에서 `users` 행이 있고 `deleted_at IS NULL`인지 → 아니면 401 `UNAUTHORIZED`. 만료·서명 오류도 401 |
| 로그아웃 | `POST /auth/logout`은 유효한 Bearer 토큰을 확인하고 204 반환. JWT 폐기 목록은 두지 않으므로 프론트가 토큰을 지워야 하며, 이미 복사된 토큰은 만료(기본 60분)까지 유효 |
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
{"session_id":"4b1c0000-0000-4000-8000-000000000001","events":[{
  "schema_version":1,"event_name":"search_submit","occurred_at":"2026-11-06T12:00:00+09:00",
  "user":{"anonymous_id":"anon_1","session_id":"4b1c0000-0000-4000-8000-000000000001","session_sequence":1},
  "site":{"site_id":"main","hostname":"localhost","platform":"desktop_web"},
  "acquisition":{"landing_url":"http://localhost/search","referrer_url":null,"utm_source":null,"utm_medium":null,"utm_campaign":null},
  "page":{"page_view_id":"page_1","page_type":"search_results","url":"http://localhost/search","path":"/search","title":"search_results"},
  "navigation":{"from":null,"to":{"page_view_id":"page_1","site_id":"main","url":"http://localhost/search","path":"/search"},"navigation_type":"direct"},
  "products":[],"properties":{"page":1}
}]}
```

- 프론트 이벤트 12종: `page_view`, `product_impression`, `product_view`, `product_section_click`, `search_submit`, `availability_view`, `rental_slot_select`, `reservation_start`, `reservation_cancel_attempt`, `review_create`, `login`, `signup`.
- 서버 결과 이벤트 3종: `reservation_complete`, `reservation_conflict`, `reservation_cancel_complete`. B가 확정한 `products`를 전달한다. 현재 B의 구형 이름 호출은 새 컬렉션에 기록되지 않으므로 B 변경이 필요하다.
- **미허용 이름만 그 건을 제외**하고 `202 {"accepted": n, "ignored": [{"event_type": "…", "count": k}]}`. 허용된 이름의 필수 문맥·상품 조건이 틀리거나 51건 이상이면 400이다. 비활성 공간 `review_create`가 정상 이벤트와 섞여도 현재는 묶음 전체 400이며 로그에 쓰지 않는다(PR #72 PM 검토 사항).
- FE PR #59는 현재 상품 이벤트마다 `product_id` 하나만 보낸다. A는 추가 `product_name`·`price` 입력을 400으로 거절하고 B의 `venue_repo.get_detail()`을 primary에서 호출해 활성 공간의 이름·수집 시점 가격을 채운다(복제 지연 방지). 인증된 `user_id`는 JWT 확인 결과만 사용한다. 같은 묶음의 서로 다른 공간 ID마다 상세 조회 SQL 한 번이 실행되므로 최대 50건 묶음에서 조회도 최대 50회다. DB 명세는 상품을 1개 이상 허용하지만 현재 FE는 한 개씩 보내므로, 다중 상품 이벤트 도입 전 B의 일괄 공간 스냅샷 조회 계약을 협의해야 한다.
- URL query·fragment를 제거하고 `page.title`은 고정 화면명으로 바꾼다. UTM은 팀 허용 목록 결정 전까지 null, 임의 자유 문자열은 제외한다. `region_id`·`facility_ids`처럼 형식을 확인한 값과 `reservation_conflict.reason=SLOT_TAKEN`은 보존한다.
- 서버 결과 3종은 문맥이 없을 때 `user.anonymous_id`·`user.session_sequence`·`site`·`acquisition`·`page`·`navigation`을 null로 기록한다(#60 승인). `X-Session-Id`가 없으면 A가 요청 ID로 `user.session_id=server-<request_id>`를 채운다(#60 PM 결정). 예약 응답과 이벤트 수집은 독립적으로 유지한다.

#### 생성기 백필에서 A 서비스 사용 (#75)

- 현재 생성기는 별도 프로세스의 `HistoricalRuntime`에서 `Gateway.signup()` 호출 전 업무 시각을 과거 가입 시각으로 맞춘다. 그 안에서 `SignupCreate`를 만들고 `auth_service.signup(db, body, is_synthetic=True)`를 호출한다. A의 `override_business_time(joined_at)` 범위에서 같은 입력·서비스를 호출해도 가입 나이 검증, 동의·가입 시각이 같은 결과를 내는지 비교 테스트로 확인했다. 일반 가입 중복 정책과 기존 bcrypt 해시는 유지한다.
- 후기는 `Gateway.review()`가 `HistoricalRuntime` 시각을 이용 종료 뒤의 작성 시각으로 맞춘 뒤 `review_service.create_review()`를 호출한다. A의 `override_business_time(reviewed_at)` 경로와 정상 작성 결과·`reviews.created_at`이 같은지 비교 테스트로 확인했다.
- 이벤트는 A의 `build_document()`로 조립하고 `is_synthetic=True`, 각 행동 시각은 `occurred_at`으로 명시한다. `received_at`은 `get_event_time()`의 실제 적재 시각으로 둔다. 업무 시각 override를 이벤트 수신 시각에 적용하지 않는다.
- `SERVER_NAME=generator`는 백필 실행 프로세스의 환경에만 지정하고 공용 `backend/.env`에는 넣지 않는다. 예: Linux `env SERVER_NAME=generator python -m <생성기_모듈>`. 앱 설정은 첫 `get_settings()` 때 읽으므로 프로세스를 시작하기 전에 지정한다. API 프로세스의 `api-1`·`api-2` 표시는 유지한다.
- 재실행 때 기존 일반 가입 API의 중복 허용을 추가하지 않는다. 결정적 이메일이 이미 있으면 생성기에서 `is_synthetic` 표식과 manifest의 동일 seed·회원 데이터를 확인한다. 기대한 합성 회원과 일치하면 그 `user_id`를 재사용하고, 일반 회원 또는 다른 생성 결과와 충돌하면 덮어쓰지 말고 중단한다. 비밀번호는 bcrypt 해시 문자열이 매번 달라질 수 있으므로 해시 문자열끼리 비교하지 않는다.
- 후기는 예약당 UNIQUE와 소프트 삭제 정책을 따른다. 같은 seed에서 해당 예약의 후기가 이미 있으면 `user_id`, 내용·평점·작성 시각 및 삭제 상태가 manifest의 기대 결과와 일치할 때만 재생성 없이 건너뛴다. 불일치하면 수정하거나 삭제 후 다시 쓰지 말고 충돌로 중단한다. 새 후기는 `review_service.create_review()`를 호출한다. 삭제된 후기도 예약당 1개 제한에 포함되므로 재작성하지 않는다.
- B 예약 서비스의 일반 요청은 `log_event()`와 `reservation_counter`를 호출한다. 현재 생성기의 `HistoricalRuntime`은 별도 생성기 프로세스 안에서만 이 두 호출을 억제하고 종료 시 원래 참조를 복원한다. 생성기가 확정 결과로 이벤트를 따로 만들어도 예약 이벤트와 운영 지표가 중복되지 않도록 한 방식이다. `SERVER_NAME=generator`는 출처 표식이며 억제 기능을 대신하지 않는다. api1 파일럿에서는 생성기 프로세스를 따로 실행하고 이벤트·카운터 중복 여부를 확인한다. PM은 `HistoricalRuntime`과 `override_business_time()`의 결과가 같다는 테스트가 있으면 현재 방식을 허용했다(#75).

**#60 전환 상태(11-06):** A는 새 문서 조립·저장 대상·재적재 형식을 구현했다. 공식 `mongo_init.js`를 전용 `space_rental_analytics_test`에 적용한 뒤 실제 HTTP 검색 이벤트와 `log_event` 서버 이벤트 각 1건을 `events.log`와 MongoDB에서 확인했고, 같은 로그를 두 번 재적재해도 ID별 1건만 남음을 확인했다. 생성한 두 문서는 삭제했다. 이벤트 pytest 24건·전체 375건, Ruff·프론트 verify가 통과했다. FE PR #59는 develop에 병합됐지만 지역·시설 ID와 예약 문맥 전송은 남았고, B 서버 이벤트 이름·상품 전달도 미완료다. 비활성 공간 `review_create`가 유효한 항목과 섞이면 전체 400인 현행 정책은 PM 후속 논의 대상이다. 옛 로그는 별도로 보존하고 재적재에서 제외한다. HTTP 재전송은 서버가 새 ID를 발급한다.

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
| `event_file_write_failures_total{stage,reason}` | 카운터 | 기록 실패 단계(`serialize`, `directory_prepare`, `thread_lock`, `lock_file_open`, `process_lock`, `event_file_open`, `append` 등)와 원인(`lock_timeout`, `permission`, `disk_full`, `io_error`, `serialization_error`) |
| `event_file_lock_wait_seconds{scope}` | 히스토그램 | `thread`·`process` 파일 잠금 대기시간. scope별 p95 계산 |
| `event_file_write_duration_seconds` | 히스토그램 | 이벤트 직렬화부터 파일 append 시도까지 전체 시간(파일 시스템 write 구간만의 시간은 아님) |
| `db_read_fallback_total` | 카운터 | replica → primary 대체 횟수 |

예약·취소 서버 이벤트는 `events.log` 기록 실패 시 실패 원인을 안전한 고정 코드로 집계하고, 요청 응답 후 MongoDB writer 전달을 계속 시도합니다. 프론트 이벤트 접수 API는 기존처럼 파일 기록 실패 시 503을 반환하고 해당 문서를 큐에 넣지 않습니다. 잠금 대기 제한 0.1초는 실측 원인이 확정될 때까지 유지합니다.

현재 109의 7 VM 실험 구성에서는 Prometheus가 mysqld·node·HAProxy·Nginx·FastAPI·Alloy 자체 `/metrics`를 직접 pull 합니다. Alloy는 journal·로그 파일을 읽어 Loki로 보내며 exporter 지표를 Prometheus에 remote_write하지 않습니다. `infra/monitoring/README.md`의 AWS 예시 및 초기 설계 흐름은 이 배포 구성을 설명하지 않는 참고안입니다.

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
- 가상 데이터: 헤더 `X-Synthetic: 1` + `X-Synthetic-Key`(= `.env` `SYNTHETIC_API_KEY`) → MariaDB `is_synthetic = true`, 이벤트에도 같은 값. 공인 주소로 열려 있어 헤더만으로는 믿지 않음(11-05 A6). 키는 크롤러용 `INTERNAL_API_KEY`와 따로 둠(부하 도구가 `/internal/venues`를 부르지 못하게).

## 7. 테스트

| 파일 | 확인할 것 |
| --- | --- |
| test_auth.py | 가입 성공, 필수 입력·동의·휴대폰·birth 형식 오류 400, 만 14세 제한, 이메일 중복 409, **가입 직후 로그인 성공**, 인증된 로그아웃 204, 탈퇴 회원 로그인·만료 토큰 401 |
| test_users.py | 내 정보 응답에 password_hash 없음, 조회 인증·시간대, 프로필 수정·잘못된 입력, 현재 비밀번호 확인, 새 비밀번호 길이·bcrypt 저장·로그인 변경, **취소 가능 예약 탈퇴 차단·개인정보 익명화·기존 토큰 무효화·이메일 재가입, 예약·후기 보존 및 탈퇴 회원 후기 표시** |
| test_reviews.py | 자격 4단계 각각(404·403·403·409), 남의 후기 수정 403, 공간별·전체 정렬, 이름 가림, **작성 직후 내 후기에 보임** |
| test_events.py | 50건 허용·51건 400, FE 12종·서버 3종의 상품·문맥 조건, 미허용 `event_name`만 빠지고 202 + `ignored`, MongoDB 장애 202/파일 실패 503, X-Synthetic, 개인정보 제거, 새 `events.log` 재적재 중복 제외. 별도 실험에서 공식 validator를 적용한 테스트 MongoDB에 검색·서버 이벤트 각 1건 저장 확인; B 예약 호출 3종 통합은 별도 |
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
