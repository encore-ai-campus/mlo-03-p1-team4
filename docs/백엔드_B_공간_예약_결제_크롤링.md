# 백엔드 파트 B — 공간·검색·예약·결제·크롤링 등록

2026-11-03 확정안 (DB 명세 반영) · 작성 노진산 · 기준: 변경 ERD → `산출물_04_DB명세서.md`(MariaDB 11.4), 11-03 회의, `공간대여_03_FastAPI_API분담.md`(10-30 분담), `산출물_01_요구사항명세서.md`

10-30 분담대로 B는 '공간과 예약'을 맡고, 동시성(같은 칸 중복 차단)이 핵심입니다. 11-03 결정으로 **결제 화면에서 칸을 잡지 않고 먼저 결제한 사람이 확정**됩니다. 11-02 초안의 '예약 + 모의 결제 한 트랜잭션'이 그대로 맞습니다. DB 명세(`산출물_04`)를 반영해 바뀐 것은 네 가지입니다.

- DB가 master–slave라 **쓰기·'내 것'은 primary, 공개 조회는 replica**로 나눕니다.
- 크롤링을 유지하므로 **`POST /internal/venues`(upsert)**를 B가 만듭니다. 크롤러(DB 담당)가 부릅니다.
- `min_hours`가 복원되어 예약 검증·예약 가능 날짜에 씁니다. 결제수단은 DB에도 영문 코드로 저장합니다.
- 오늘 날짜는 `get_today()`(기본 실제 날짜)로 읽습니다.

## 1. 맡는 범위

| 영역 | 기능 ID | 쓰는 표 (primary) | 읽는 곳 |
| --- | --- | --- | --- |
| 기준 정보 | F-10, F-11 | — | replica: categories, regions, facilities |
| 공간 조회·검색 | F-12~F-14, F-20~F-22 | — | replica: venues, venue_facilities, venue_images, reservation_slots, `v_venue_rating` |
| 예약·결제·취소 | F-30~F-32, F-34 | reservations, reservation_slots, payments | primary: venues |
| 내 예약 | F-40 | — | **primary**: reservations, payments, venues, reviews(후기 썼는지만) |
| 이용 완료 | F-35 | reservations | — |
| 크롤링 등록 | F-61 | venues, venue_facilities, venue_images | primary: regions, categories, facilities |
| 지표 | F-65 | `reservation_total{result}` 카운터 | — |

### 10-30·11-02에서 바뀐 것

| 항목 | 이전 | 지금 | 이유 |
| --- | --- | --- | --- |
| 예약 단위·경로 | rooms, `/rooms/…` | venues, `/venues/…` | rooms 삭제 |
| 예약 흐름 | 신청(pending 10분) → confirm | **결제 버튼 한 번 = 예약·칸·결제 한 트랜잭션** | 11-03 결정 2 |
| `/reservations/{id}/confirm`, 만료 배치 | 있음 | 삭제 | 홀딩 없음 |
| 결제 금액·수단 | `amount`, `'mock'` | `total_price`, ENUM(`transfer`·`card`·`phone`) | DB 명세 2절 |
| 최소 이용시간·최소 인원 | `min_hours`, `capacity_min` | **`min_hours` 유지(복원)**, 최소 인원은 1명 | DB 명세 2절 |
| NEW | `new_until` | `created_at`이 오늘 기준 14일 안 | ERD |
| DB 연결 | 하나 | **primary + replica** | 11-03 팀원 의견 |
| 오늘 | `get_sim_today()`(11-02) | **`get_today()`**(기본 실제 날짜) | 11-03 제안 2의 ③ |
| 공간 등록 | 크롤러 → `/internal/venues` | **그대로**(크롤러 → MongoDB `crawl_raw` → 전처리 → `/internal/venues`). 크롤링 3곳(스페이스클라우드·쉐어잇·루북), 영화관 유형은 강의실로 바뀜(11-03 A3) | 크롤링 유지 결정 |
| 서버 쪽 이벤트 | 로그 파일 | 로그 파일 + MongoDB (A의 `log_event`) | 11-03 결정 1 |

## 2. 파일

```
backend/app/
  models/        catalog.py venue.py reservation.py   # SQLAlchemy 모델 (DDL과 같게)
  routers/       catalog.py venues.py reservations.py internal.py
  schemas/       catalog.py venues.py reservations.py internal.py
  services/      venue_service.py reservation_service.py internal_service.py
  repositories/  catalog_repo.py venue_repo.py slot_repo.py reservation_repo.py payment_repo.py
  jobs/          complete_reservations.py
backend/tests/   test_catalog.py test_venues.py test_reservations.py test_concurrency.py test_jobs.py test_read_routing.py test_internal.py
simulator/locust/  locustfile.py          # [B] 동시 예약 시나리오, replica 있음·없음 비교
infra/nginx/       spacecube.conf         # [B] upstream 2대, /health
```

## 3. 다른 파트에 주는 것 (약속)

| 이름 | 형태 | 쓰는 곳 |
| --- | --- | --- |
| `reservation_repo.get_owned(db, user_id, reservation_id)` | 내 예약이면 `Reservation`(reservation_id, venue_id, reserve_date, start_hour, end_hour, status, created_at), 아니면 `None`(11-03 A1 확정, `created_at`은 A의 후기 기한 계산용). **호출하는 쪽이 primary 세션을 넘김** | A 후기 자격 |
| `reservation_repo.count_cancellable(db, user_id)` → `int` | 그 회원의 `status='confirmed'`이면서 시작 시각(`reserve_date` + `start_hour`)이 `get_now()`보다 뒤인 예약 수. **호출하는 쪽이 primary 세션을 넘김** (11-05) | A 탈퇴 전 확인 |
| `GET /reservations/me` | 5-3 응답 | 프론트 마이페이지 |
| 서버 쪽 이벤트 | `reserve_ok`, `reserve_conflict`, `reserve_cancel_ok` (A의 `log_event()`) | 분석 |

## 4. 다른 파트에서 받는 것

| 이름 | 제공 | 쓰임 |
| --- | --- | --- |
| `get_db_write`, `get_db_read`, `get_current_user`, `AppError`, `paginate`, `log_event`, `get_today`, `is_synthetic_request` | A | 전부 |
| 뷰 `v_venue_rating(venue_id, rating_avg, review_count)` | DB | 평점, 평점순 |
| 기초 데이터, 생성된 공간·과거 예약 | DB | 조회·테스트 |

1일차 오전에 A의 core가 나오기 전까지는 공개 조회 API(기준 정보·검색·상세·칸)부터 만듭니다.

## 5. API

경로 앞 `/api`는 Nginx가 붙입니다. DB 열: W primary, R replica. 오류 코드·문구·`detail` 모양은 [`오류코드.md`](오류코드.md) 4절.

### 5-1. 기준 정보 (R)

| 메서드 | 경로 | 응답 |
| --- | --- | --- |
| GET | /categories | `[{"code":"studyroom","name":"스터디룸"}, …]` 5개 |
| GET | /regions | 시·도 목록 |
| GET | /regions?sido=서울 | `[{"region_id":1,"sigungu":"관악구"}, …]` |
| GET | /facilities | `[{"facility_id":1,"name":"와이파이"}, …]` (필터용) |

### 5-2. 공간 (R)

| 메서드 | 경로 | 기능 | 설명 |
| --- | --- | --- | --- |
| GET | /venues | F-12, F-13 | 검색 |
| GET | /venues/new | F-14 | NEW 공간, 최신순 |
| GET | /venues/{venue_id} | F-20 | 상세 (후기 목록은 A의 `/venues/{id}/reviews`) |
| GET | /venues/{venue_id}/available-dates?days=14&offset=0 | F-21 | 예약 가능한 날. `offset`으로 '더보기' |
| GET | /venues/{venue_id}/slots?date= | F-22 | 그날 칸 상태 |

`GET /venues` 파라미터:

| 이름 | 예 | 조건 |
| --- | --- | --- |
| q | `신촌` | 이름·시·군·구·시설 이름에 포함 |
| category | `studio` | categories.code |
| sido, sigungu | `서울`, `마포구` | regions |
| date | `2026-11-05` | 예약 가능 범위(오늘 −365일 ~ +365일) 안. 없으면 오늘 |
| start_hour, hours | `13`, `2` | 둘 다 있으면 그 칸이 모두 비고 영업시간 안인 공간만 |
| people | `4` | `capacity_max >= people` |
| facilities | `1,4` | 시설 id를 모두 가진 공간 (`GROUP BY … HAVING COUNT = 2`) |
| now | `true` | 오늘, 지금 시 이후 빈 칸이 있는 곳만 |
| sort | `default`·`popular`·`price`·`rating` | popular = 최근 7일(`created_at`, 실제 결제 시각) 동안 결제된 예약 수. 취소·지난 날짜 예약(`reserve_date < DATE(created_at)`)은 빼고 셈 |
| page, size | `1`, `10` | '더 보기'로 다음 page |

검색 항목:

```json
{
  "venue_id": 7, "name": "서대문구 스터디룸 3호",
  "category": {"code": "studyroom", "name": "스터디룸"},
  "region": {"sido": "서울", "sigungu": "서대문구"},
  "capacity_max": 6, "price_per_hour": 10000, "open_hour": 9, "close_hour": 23,
  "rating_avg": 4.8, "review_count": 31, "image": "art:group-0",
  "facilities": ["화이트보드", "와이파이"], "is_new": false,
  "slots": [{"hour": 9, "taken": false, "past": true}, {"hour": 10, "taken": true, "past": false}]
}
```

- `slots`는 결과 공간 id 목록으로 `reservation_slots`를 **한 번에** 읽어 붙입니다(공간마다 쿼리하지 않음).
- `past`: 그 칸이 이미 지났는지(날짜가 오늘 이전, 또는 오늘이고 시 ≤ 지금 시). **표시용이고 막지 않습니다**(11-03 날짜 결정). 지난 칸도 비어 있으면 예약할 수 있습니다.
- replica에서 읽으므로 방금 찬 칸이 잠깐 비어 보일 수 있습니다. 예약은 primary가 판정하니 중복은 생기지 않습니다(6절).

상세는 검색 항목에 `description`, `notice`, `images`(정렬 순), `facilities`(id·이름)를 더합니다. `is_active = false`면 404입니다. `/venues/new`는 `registered_on`, `new_days_left`를 더합니다.

`/available-dates`:

```json
{"venue_id": 7, "offset": 0, "days": 14, "min_date": "2025-11-03", "max_date": "2027-11-03",
 "dates": [{"date": "2026-11-03", "free": 5, "bookable": true}, {"date": "2026-11-04", "free": 0, "bookable": false}]}
```

`bookable`은 **이어진 빈 칸이 그 공간의 `min_hours` 이상**인 날입니다(지난 칸도 포함). `offset`은 오늘 기준 일 수로 음수도 됩니다(`-14`면 2주 전부터). 범위는 설정값 `BOOKING_PAST_DAYS`·`BOOKING_FUTURE_DAYS`(기본 각 365)이고 응답의 `min_date`·`max_date`로 알려 줍니다.

### 5-3. 예약·결제 (W)

| 메서드 | 경로 | 인증 | 기능 | 성공 | 주요 오류 |
| --- | --- | --- | --- | --- | --- |
| POST | /reservations | 회원 | F-30~F-32 | 201 (같은 요청을 다시 보내면 200) | 400 `OUT_OF_RANGE`·`TOO_MANY_PEOPLE`·`INVALID_METHOD`, 404 `VENUE_NOT_FOUND`, 409 `SLOT_TAKEN` |
| POST | /reservations/{id}/cancel | 회원 | F-34 | 200 | 404, 409 `NOT_CANCELLABLE`·`ALREADY_CANCELLED` |
| GET | /reservations/me?status=&page= | 회원 | F-40 | 200 목록 | 401 |
| GET | /reservations/{id} | 회원 | F-40 | 200 | 404 (남의 예약도 404) |

```json
// POST /reservations  (결제 버튼)
{"venue_id": 7, "date": "2026-11-05", "start_hour": 13, "hours": 2, "headcount": 4, "method": "card"}

// 201
{"reservation_id": 1203, "status": "confirmed", "venue_id": 7, "date": "2026-11-05",
 "start_hour": 13, "end_hour": 15, "headcount": 4, "total_price": 20000,
 "payment": {"method": "card", "status": "paid", "paid_at": "2026-11-03T14:03:12+09:00"}}

// 409 — 먼저 결제한 사람이 있음
{"code": "SLOT_TAKEN", "message": "다른 분이 먼저 결제한 시간이 있어요.", "detail": {"slots": [14]}}
```

| 결제수단 (API = DB 값) | 화면 표시 |
| --- | --- |
| `transfer` | 계좌이체 |
| `card` | 카드결제 |
| `phone` | 휴대폰 |

내 예약 목록 항목: 예약 칸 전부 + `venue`(id·이름·유형·지역·이미지) + `payment`(method·status·paid_at·refunded_at) + `can_cancel` + `review_id`(썼으면). `status` 필터는 `confirmed`·`completed`·`cancelled`입니다.

## 6. 예약 트랜잭션 (핵심, primary)

```
POST /reservations  — 결제 화면에 들어올 때는 아무것도 잡지 않음
 1. 검증 (쓰기 전)
    - get_today() − BOOKING_PAST_DAYS ≤ date ≤ get_today() + BOOKING_FUTURE_DAYS
    - venues.min_hours ≤ hours ≤ 4, start_hour ≥ open_hour, start_hour + hours ≤ close_hour
    - 지난 날짜·지난 시간도 허용 (11-03 날짜 결정)
    - 1 ≤ headcount ≤ venues.capacity_max, venues.is_active   ← primary에서 읽음
    - method ∈ {transfer, card, phone}
 2. BEGIN
 3. INSERT reservations (…, total_price = price_per_hour × hours, is_synthetic,
                        status = 끝나는 시각(date, start_hour + hours) ≤ get_now() ? 'completed' : 'confirmed')
 4. INSERT reservation_slots (venue_id, slot_date, slot_hour, reservation_id) VALUES (…13…), (…14…)
 5. INSERT payments (reservation_id, method, status = 'paid', paid_at = NOW())
 6. COMMIT → 201, log_event(session_id = get_session_id(request), user_id, "reserve_ok", venue_id, category = venue.category.code, payload = {date, start_hour, hours}), reservation_total{result="ok"} +1
    4에서 중복 키(1062) → ROLLBACK
      → primary에서 그날 겹친 칸과 그 예약의 주인을 다시 읽음
        ① 같은 사용자·공간·날짜·시작·시간인 예약이 10분 안에 만들어져 있으면 → **200 + 그 예약**(두 번 누름·재시도, 새 이벤트·카운터 없음)
        ② 겹친 칸이 모두 내 다른 예약이면 → 409 SLOT_TAKEN, detail = {slots, mine: true, reservation_id}
        ③ 그 밖 → 409 SLOT_TAKEN, detail = {slots}, log_event(reserve_conflict), reservation_total{result="conflict"} +1
```

- 중복 키는 `IntegrityError`의 `e.orig.args[0] == 1062`일 때만 409로 바꿉니다. 외래키 오류(1452)도 같은 `IntegrityError`로 오니, 1062가 아니면 409로 바꾸지 않고 500으로 둡니다(앞 단계 검증이 빠졌다는 신호).
- **먼저 커밋한 요청이 이깁니다.** 이것이 11-03 결정 2의 '최종 결제순 확정'입니다.
- 3 이전에 '빈 칸인지 먼저 SELECT'로 막지 않습니다. 두 서버가 동시에 '비었음'을 볼 수 있고, replica라면 더 그렇습니다.
- 겹친 칸을 다시 읽는 것도 **primary**에서 합니다. replica에서는 방금 이긴 예약이 아직 안 보일 수 있습니다.
- 칸과 예약의 공간·날짜가 어긋나지 않게 `reservations` UNIQUE `(reservation_id, venue_id, reserve_date)` + 복합 외래키가 필요합니다. DB 담당 스키마에서 확인합니다.
- MongoDB가 꺼져 있어도 예약은 성공해야 합니다. 이벤트는 A의 `log_event()`가 응답 뒤에 따로 씁니다.

### 취소 (primary)

```
POST /reservations/{id}/cancel
 1. BEGIN
 2. SELECT … FROM reservations WHERE reservation_id = ? AND user_id = ? FOR UPDATE
      없음 → 404 / cancelled → 409 ALREADY_CANCELLED / completed → 409 NOT_CANCELLABLE
 3. 시작 전인지: reserve_date > 오늘, 또는 오늘이면 start_hour > 지금 시
 4. UPDATE reservations SET status = 'cancelled'
 5. DELETE FROM reservation_slots WHERE reservation_id = ?
 6. UPDATE payments SET status = 'refunded', refunded_at = NOW()
 7. COMMIT → 200, log_event(reserve_cancel_ok)
```

전액 환불만 합니다.

### 이용 완료 배치 (primary)

```sql
UPDATE reservations SET status = 'completed'
 WHERE status = 'confirmed'
   AND (reserve_date < :today OR (reserve_date = :today AND end_hour <= :now_hour));
```

- `jobs/complete_reservations.py`, FastAPI #1의 cron 1시간마다. 두 번 돌려도 같습니다.
- 생성기가 넣는 과거 예약은 처음부터 `completed`로 넣어도 되고, 이 배치가 바꿔도 됩니다.
- cron은 #1 한 대에서만 돌립니다(두 대에서 돌아도 결과는 같지만 로그가 겹침).
- completed 예약의 칸은 지우지 않습니다(점유율 분석).

## 7. 크롤링 등록 — `POST /internal/venues`

| 항목 | 내용 |
| --- | --- |
| 부르는 곳 | 크롤러(DB 담당, FastAPI #1의 cron). 처음에는 표본 200개 중 후보, 이후 주 1회 신규 |
| 보호 | 헤더 `X-Internal-Key` = `.env` `INTERNAL_API_KEY` + Nginx에서 VPC 대역만 |
| 동작 | `(source_site, source_id)` UNIQUE로 upsert(`INSERT … ON DUPLICATE KEY UPDATE`). 신규 201, 갱신 200 |
| 시설·그림 | 시설은 이름으로 찾고 없는 이름은 버린 뒤 `detail.ignored_facilities`로 알림. 시설·그림은 요청 값으로 통째로 바꿈 |
| 지역·유형 | 모르는 값이면 400 `UNKNOWN_REGION`·`UNKNOWN_CATEGORY`. B가 지역을 새로 만들지 않음 |
| 원본 | 추출값은 크롤러가 MongoDB `crawl_raw`에 둠. B는 정리된 값만 받음. 응답의 `venue_id`를 크롤러가 `crawl_raw`에 기록 |

```json
{
  "source_site": "spacecloud", "source_id": "82391",
  "name": "서대문구 스터디룸 3호", "category_code": "studyroom",
  "sido": "서울", "sigungu": "서대문구",
  "capacity_max": 6, "price_per_hour": 10000, "min_hours": 2,
  "open_hour": 9, "close_hour": 23,
  "description": "유형별 템플릿", "notice": "유형별 이용 안내",
  "facilities": ["화이트보드", "와이파이"], "images": ["art:group-0"]
}
```

- 이름·소개·이용 안내는 크롤러가 **생성한 값**을 보냅니다. 업체 실명·소개 원문은 받지 않습니다.
- 값 검증은 DDL의 CHECK와 같게 합니다(가격 > 0, 인원 ≥ 1, 영업시간 open 9~22·close 10~23, `min_hours` 1~4). 크롤러는 영업시간을 9~23으로 잘라 보냅니다(11-03 A2).
- 생성기로 만든 공간이 필요하면 같은 API로 넣습니다(`source_site = "synthetic"`). `source_site`는 `spacecloud`·`shareit`·`roovook`·`synthetic`.

## 8. 테스트

| 파일 | 확인할 것 |
| --- | --- |
| test_catalog.py | 유형 5개, 시·도 → 시·군·구, 시설 목록 |
| test_venues.py | 필터 조합, 정렬 4종, 칸 상태(taken·past), NEW 14일 경계, 비활성 404, 날짜 더보기(offset) |
| test_reservations.py | 성공 201(3개 표 모두 생김), **같은 요청 다시 보내면 200 + 같은 reservation_id(표에 새 행 없음)**, 내 예약과 일부 겹치면 409 + `mine`, 범위 밖 400(±365일 밖·영업시간 밖·5칸·`min_hours` 미만), 지난 시간 예약은 201 + 바로 completed, 인원 초과, 결제수단 오류, 남의 예약 404, 취소 후 칸 반납·환불, 지난 예약 취소 409, **예약 직후 `/reservations/me`에 보임** |
| test_concurrency.py | **같은 칸 동시 50건 → 201 정확히 1건, 409 49건.** 겹치는 범위(13~15 vs 14~16)도 1건만. 409의 `detail.slots`가 정확함 |
| test_jobs.py | 끝나는 시각이 지난 confirmed만 completed(오늘 끝난 것 포함), 두 번 돌려도 같음 |
| test_internal.py | 키 없음 401, 신규 201·같은 출처 200(갱신), 모르는 시설 무시, 모르는 지역 400, CHECK 위반 값 400 |
| test_read_routing.py | 공개 조회 라우터는 `get_db_read`, 예약·내 예약은 `get_db_write`를 쓰는지(의존성 목록 검사) |

동시성 테스트는 실제 MariaDB(`spacecube_test`)에서 스레드 50개로 돌립니다. SQLite로 대신하지 않습니다.

### Locust (2~3일차)

| 시나리오 | 비교 |
| --- | --- |
| 같은 칸 동시 50명 | 성공 1, 나머지 409, 중복 0 |
| 검색·상세·칸 조회 위주 50명 | **replica 있음 vs `DB_READ_URL` 비움(primary만)**: p50·p95·오류율 |

replica를 넣은 이유(읽기 분산)가 실제로 효과가 있었는지 이 비교로 발표합니다.

## 9. 작업 순서 (1차 일정: 1일 구현 · 2일 배포 · 3일 자동화·발표)

| 일차 | 할 일 | 끝났다는 기준 |
| --- | --- | --- |
| 1일 오전 | 기준 정보, 공간 상세·칸 조회, `/internal/venues`(크롤러가 표본으로 공간을 채울 수 있게) | test_catalog·test_internal |
| 1일 오후 | 예약 트랜잭션·409, 취소, 내 예약, `get_owned()`, 검색 필터·NEW | **test_concurrency 통과**, A 후기가 붙음 |
| 2일 | 배포: 두 DB 연결, Nginx upstream, 완료 배치 cron | 서버 1대 꺼도 응답, 예약 직후 내 예약 보임 |
| 3일 | Locust 두 시나리오, 발표 자료 숫자 | 보고서 2개 |

## 10. 확인 필요

| # | 질문 | 이 문서의 가정 |
| --- | --- | --- |
| 1 | status 3개 값 | `confirmed`·`completed`·`cancelled` |
| 2 | `min_hours` 복원 | 복원 (DB 담당 동의 필요) |
| 3 | 예약 가능 범위 | **결정(11-03)**: 실제 날짜, 과거·미래 모두 `BOOKING_PAST_DAYS`·`BOOKING_FUTURE_DAYS` 기본 365 |
| 4 | API 경로 `/venues` | 프론트 `/rooms`·`room_id` 수정 |
| 5 | `reservations` UNIQUE `(reservation_id, venue_id, reserve_date)` | 복합 외래키에 필요 |
| 6 | 공간 등록 | **결정(11-03 A3)**: 크롤러(3곳) → `/internal/venues`. 영화관 없음, 강의실 유형 추가 |
| 7 | 취소 기한·환불 | 시작 전까지, 전액 |
| 8 | 결제수단 ENUM | 영문 코드로 저장 (DB 담당 동의 필요) |
