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
| 공간 등록 | 크롤러 → `/internal/venues` | **그대로**(크롤러 → MongoDB `crawl_raw` → 전처리 → `/internal/venues`). 1차 수집원은 스페이스클라우드·쉐어잇 2곳, 30개 목표에서 부족한 시연용 공간은 생성기로 보충. 영화관 유형은 강의실로 바뀜 | 11-05 수집 방향 |
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
| `reservation_repo.review_context_query(*, active_only: bool = True)` → `Select` | 예약·공간·유형을 조인해 예약당 한 행, `reservation_id`·`venue_id`·`venue_name`·`category`(`categories.code`) 열을 `.label()`로 고정해 반환. 기본값은 비활성 공간 제외, `False`는 포함. DB 실행·commit·rollback 없음 (#43 PM 승인) | A `review_repo`가 직접 import: 공개 후기는 기본값·replica, 내 후기는 `False`·primary |
| `GET /reservations/me` | 5-3 응답 | 프론트 마이페이지 |
| 서버 쪽 이벤트 | `reserve_ok`, `reserve_conflict`, `reserve_cancel_ok` (A의 `log_event()`) | 분석 |

후기 목록의 필터·정렬·페이지 계산, 후기·회원 조인과 작성자 마스킹은 A가 담당합니다. `review_context_query()`는 후기·회원·결제·시설·그림을 조회하지 않으며 예약 상태나 후기 작성 자격으로 결과를 거르지 않습니다. A가 후기와 결합할 때 해당 조건을 판단합니다. 비활성 공간은 공개 후기 두 목록에서 숨기되 내 후기에서는 공간명을 포함해 유지합니다. 기존 `get_owned()`는 후기 작성 자격 확인용으로 그대로 사용합니다. 연결은 `main.py` 등록 대신 A 리포지토리의 직접 import로 하고, 후기 생성 이벤트 `review_create`는 프론트만 전송합니다.

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
| start_hour, hours | `13`, `2` | 둘 다 입력. 이용시간 1~4시간, 최소 이용시간 이상이며 영업시간 안의 모든 칸이 비어 있는 공간만 |
| people | `4` | `capacity_max >= people` |
| facilities | `1,4` | 시설 id를 모두 가진 공간 (`GROUP BY … HAVING COUNT = 2`) |
| now | `true` | 오늘, 지금 시 이후 빈 칸이 있는 곳만 |
| sort | `default`·`popular`·`price`·`rating` | popular = 최근 7일(`created_at`, 실제 결제 시각) 동안 결제된 예약 수. 취소·지난 날짜 예약(`reserve_date < DATE(created_at)`)은 빼고 셈 |
| page, size | `1`, `10` | 기본 `1`, `10`; size는 1~50. '더 보기'로 다음 page |

F-14 `GET /venues/new?page=1&size=10`:

- 인증 없이 `get_db_read()`로 조회합니다. 활성 공간 중 `created_at`이 한국 날짜 기준 13일 전 00:00 이상, 내일 00:00 미만인 항목을 반환합니다. 따라서 오늘 포함 14개 날짜이고, 14일 전과 미래 등록은 제외합니다.
- 최신 등록순(`created_at DESC`, 동률은 `venue_id DESC`)으로 정렬한 뒤 페이지를 자릅니다. `total`은 필터 적용 후 페이지를 자르기 전 전체 건수입니다. 기본 page/size는 `1`/`10`, size는 1~50입니다.
- 각 항목은 F-12 검색 항목에 `registered_on`(한국 날짜의 `created_at.date()`)과 `new_days_left`(`14 - (get_today() - created_at.date()).days`)를 더합니다. 오늘은 14, 13일 전은 1일 남음으로 표시합니다.
- 시설·이미지·오늘 시간 칸은 검색과 같은 페이지 단위 묶음 조회를 사용합니다. 이미지가 없으면 `art:group-0`을 반환합니다.

```json
{
  "items": [{
    "venue_id": 7,
    "name": "서대문구 스터디룸 3호",
    "category": {"code": "studyroom", "name": "스터디룸"},
    "region": {"sido": "서울", "sigungu": "서대문구"},
    "capacity_max": 6,
    "price_per_hour": 10000,
    "open_hour": 9,
    "close_hour": 23,
    "rating_avg": 4.8,
    "review_count": 31,
    "image": "art:group-0",
    "facilities": ["화이트보드"],
    "is_new": true,
    "slots": [{"hour": 9, "taken": false, "past": true}],
    "registered_on": "2026-11-05",
    "new_days_left": 14
  }],
  "page": 1,
  "size": 10,
  "total": 1
}
```

F-12·13 검색·정렬 구현 기준:

- 활성 공간만 검색합니다. `q`는 공간명·시도·시군구·시설명에 포함되는지 찾습니다. `category=all`, `sido=전국`, `sigungu=전체`는 해당 필터를 적용하지 않습니다. 지정한 시설 ID는 모두 가진 공간을 찾습니다.
- `date`는 선택이며 없으면 한국 오늘입니다. `now=true`면 선택 날짜가 있어도 오늘로 조회하고 현재 시각보다 뒤인 빈 시간 칸이 하나 이상 있는 공간만 남깁니다.
- `start_hour`와 `hours`는 함께 입력해야 합니다. 이용시간은 1~4시간이며, 공간의 `min_hours` 이상이어야 합니다. 시작 시각부터 요청한 모든 칸이 영업시간 안이고 비어 있는 공간만 결과에 포함합니다. 지정한 날짜는 설정된 예약 범위 안이어야 합니다.
- 응답은 `{"items": [...], "page": 1, "size": 10, "total": 132}`입니다. `total`은 모든 검색 조건을 적용한 전체 결과 수이며 페이지를 자르기 전에 계산합니다. 기본 정렬은 공간 ID 오름차순으로 유지합니다.
- F-13 정렬은 가격 낮은 순·평점 높은 순·인기 높은 순입니다. 인기 수는 최근 7일 안에 생성된 예약 중 취소되지 않았고 `reserve_date >= DATE(created_at)`인 예약을 셉니다. 동률은 공간 ID 오름차순으로 고정합니다.
- 날짜 형식·정렬·유형·시설 ID·인원·시각 입력 오류는 400 `VALIDATION`, 예약 범위 밖 날짜는 400 `OUT_OF_RANGE`입니다. 잘못된 검색값은 새 오류 코드를 추가하지 않습니다.
- 검색 결과의 `slots`·시설명·대표 그림은 현재 페이지 공간 ID를 모아 일괄 조회합니다. 이미지 누락 기본값, NEW 날짜 기준, 평점은 F-20과 같습니다.

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

상세는 검색 항목에 `min_hours`, `description`, `notice`, `images`(정렬 순), `facilities`(id·이름)를 더합니다. `slots`는 오늘의 영업시간 칸이고 날짜별 조회는 F-22의 별도 API입니다. `is_active = false`면 404입니다. 평점은 `v_venue_rating`을 읽고 후기가 없는 공간은 `rating_avg = 0`, `review_count = 0`으로 반환합니다. DB에서 NULL인 설명·안내는 JSON에서도 null입니다. `/venues/new`는 `registered_on`, `new_days_left`를 더합니다.

11-05 확정한 응답 기준:

- 이미지가 없거나 빈 값뿐이면 대표 `image`는 `"art:group-0"`, 상세 `images`는 `["art:group-0"]`를 반환합니다. 기존 `RoomArt`의 `kind="group"`, `tone=0` 기본 동작과 같으며 갤러리를 빈 상태로 두지 않습니다. 별도의 `lounge-0` 대체값은 추가하지 않습니다.
- 실제 이미지가 있으면 정렬된 첫 그림을 대표 이미지로 쓰고 갤러리는 그 순서를 유지합니다.
- `is_new`는 DB의 한국 시각 `created_at`을 날짜로 바꿔 `0 <= (get_today() - created_at.date()).days < 14`로 계산합니다. 오늘과 13일 전은 포함하고 14일 전·미래 날짜는 제외합니다. 경과 336시간이 아니라 한국 달력 날짜 14개가 기준입니다.

F-22 `GET /venues/{venue_id}/slots?date=YYYY-MM-DD`:

```json
[{"hour": 9, "taken": false, "past": true}, {"hour": 10, "taken": true, "past": true}]
```

- 인증 없이 `get_db_read()`로 조회하며 `date`는 필수입니다. `YYYY-MM-DD` 형식의 실제 날짜만 허용합니다. 누락·잘못된 형식·존재하지 않는 날짜·잘못된 공간 ID는 공통 400 `VALIDATION`입니다.
- 날짜는 한국 `get_today()` 기준 `BOOKING_PAST_DAYS`일 전부터 `BOOKING_FUTURE_DAYS`일 후까지 양끝을 포함합니다(기본 각각 365). 범위 밖은 400 `OUT_OF_RANGE`, 문구는 “예약할 수 없는 날짜나 시간이에요.”, `detail`은 `{"reason":"date","min_date":"YYYY-MM-DD","max_date":"YYYY-MM-DD"}`입니다.
- 범위를 확인한 뒤 활성 공간을 읽으며 없는 공간·비활성 공간은 같은 404 `VENUE_NOT_FOUND`입니다.
- 응답은 배열입니다. `open_hour`부터 `close_hour` 직전까지 1시간 칸을 오름차순으로 모두 반환합니다. 최소 예약시간·연속 빈 칸 여부로 표시 칸을 제외하지 않습니다.
- `taken`은 해당 공간·날짜의 `reservation_slots` 존재 여부입니다. 완료 예약의 칸도 점유로 표시하고 다른 공간·날짜는 섞지 않습니다. `past`는 위의 표시 규칙을 따르며 지난 빈 칸도 유지합니다.
- 오늘 조회 결과는 F-20의 `slots`와 같습니다. 점유 상태는 캐시하지 않으며 매 요청 다시 읽습니다. replica 복제 지연 가능성과 예약 시 primary 최종 판정 원칙은 동일합니다.

`/available-dates`:

```json
{"venue_id": 7, "offset": 0, "days": 14, "min_date": "2025-11-03", "max_date": "2027-11-03",
 "dates": [{"date": "2026-11-03", "free": 5, "bookable": true}, {"date": "2026-11-04", "free": 0, "bookable": false}]}
```

`bookable`은 **이어진 빈 칸이 그 공간의 `min_hours` 이상**인 날입니다(지난 칸도 포함). `offset`은 오늘 기준 일 수로 음수도 됩니다(`-14`면 2주 전부터). 범위는 설정값 `BOOKING_PAST_DAYS`·`BOOKING_FUTURE_DAYS`(기본 각 365)이고 응답의 `min_date`·`max_date`로 알려 줍니다.

F-21 구현 기준(기존 프론트 목업과 동일):

- 인증 없이 `get_db_read()`로 조회합니다. `offset`은 정수 기본 0, `days`는 1~31 정수 기본 14입니다. 잘못된 값·공간 ID는 400 `VALIDATION`입니다.
- 시작 날짜는 한국 `get_today() + offset`입니다. 시작 날짜가 설정 범위 밖이면 F-22와 같은 400 `OUT_OF_RANGE` 및 `reason="date"`·`min_date`·`max_date` detail을 반환합니다. 큰 정수 offset도 날짜 연산 전에 범위를 확인합니다.
- 시작 날짜가 허용되면 `days`일을 조회하되 최대 날짜를 넘는 뒷부분은 자릅니다. 응답 `days`는 요청값을 유지하고 `dates` 길이는 더 짧을 수 있습니다. `min_date`·`max_date`는 조회 페이지가 아닌 전체 예약 가능 범위입니다.
- `dates`는 조회 구간의 모든 날짜를 오름차순으로 포함합니다. 예약 불가능한 날도 `bookable=false`로 남깁니다. `free`는 `[open_hour, close_hour)` 안의 빈 칸 총수이며 연속 길이와 다릅니다. 예를 들어 최소 2시간에 빈 칸 2개가 떨어져 있으면 `free=2`, `bookable=false`입니다.
- 지난 칸은 제외하지 않고 완료 예약의 칸도 점유로 셉니다. 다른 공간·날짜 및 영업시간 밖 점유는 섞지 않습니다. 없는 공간·비활성 공간은 404 `VENUE_NOT_FOUND`입니다.
- 공간의 영업시간·최소 이용시간과 요청 기간의 점유 칸을 각각 한 번씩 조회합니다. 날짜별 SQL 반복·이미지·평점 조회·점유 캐시는 없습니다. replica 복제 지연 가능성과 예약 시 primary 최종 판정 원칙은 F-22와 같습니다.

### 5-3. 예약·결제 (W)

| 메서드 | 경로 | 인증 | 기능 | 성공 | 주요 오류 |
| --- | --- | --- | --- | --- | --- |
| POST | /reservations | 회원 | F-30~F-32 | 201 (같은 요청을 다시 보내면 200) | 400 `OUT_OF_RANGE`·`TOO_MANY_PEOPLE`·`INVALID_METHOD`, 404 `VENUE_NOT_FOUND`, 409 `SLOT_TAKEN` |
| POST | /reservations/{id}/cancel | 회원 | F-34 | 200 취소 응답 | 404 `RESERVATION_NOT_FOUND`, 409 `NOT_CANCELLABLE`·`ALREADY_CANCELLED` |
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

// POST /reservations/1203/cancel — 200
{"reservation_id": 1203, "status": "cancelled", "total_price": 20000,
 "payment": {"method": "card", "status": "refunded", "paid_at": "2026-11-03T14:03:12+09:00",
             "refunded_at": "2026-11-04T10:00:00+09:00"}, "can_cancel": false}
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
        ① 같은 사용자·공간·날짜·시작·시간인 예약이 10분 안에 만들어져 있고, 상태가 confirmed/completed이며 결제가 paid이면 → **200 + 그 예약**(두 번 누름·재시도, 새 이벤트·카운터 없음). cancelled 또는 refunded인 건은 재시도 후보에서 제외
        ② 겹친 칸이 모두 내 다른 예약이면 → 409 SLOT_TAKEN, detail = {slots, mine: true, reservation_id}
           겹친 예약이 여러 건이면 reservation_id가 가장 작은 예약을 대표로 반환
        ③ 그 밖 → 409 SLOT_TAKEN, detail = {slots}, log_event(reserve_conflict), reservation_total{result="conflict"} +1
```

- 중복 키는 `IntegrityError`의 `e.orig.args[0] == 1062`일 때만 409로 바꿉니다. 외래키 오류(1452)도 같은 `IntegrityError`로 오니, 1062가 아니면 409로 바꾸지 않고 500으로 둡니다(앞 단계 검증이 빠졌다는 신호).
- **먼저 커밋한 요청이 이깁니다.** 이것이 11-03 결정 2의 '최종 결제순 확정'입니다.
- 3 이전에 '빈 칸인지 먼저 SELECT'로 막지 않습니다. 두 서버가 동시에 '비었음'을 볼 수 있고, replica라면 더 그렇습니다.
- 겹친 칸을 다시 읽는 것도 **primary**에서 합니다. replica에서는 방금 이긴 예약이 아직 안 보일 수 있습니다.
- 본인 예약 여러 건과 겹친 경우 대표 `reservation_id`는 겹친 예약 ID의 최솟값입니다. 자동 증가 ID 순서가 실제 커밋 순서까지 보장하지는 않습니다.
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

전액 환불만 합니다. 성공 응답은 `reservation_id`·`status`·`total_price`·환불 시각을 포함한 `payment`·`can_cancel=false`를 반환합니다. `reserve_cancel_ok` 기록과 `reservation_total{result="cancel"}` 증가는 커밋 뒤에 한 번만 합니다. 예약과 무관한 다른 회원·예약 칸은 삭제하지 않습니다.

`reserve_cancel_ok`에는 최상위 `venue_id`·`category`(공간 유형 코드)와 `payload.reservation_id`를 전달합니다. 유형은 커밋 전 같은 primary 세션에서 읽으며, 비활성 공간의 예약도 취소하고 유형을 기록합니다.

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
| 부르는 곳 | api1의 크롤러·생성기(DB 담당). 크롤러는 유형별 후보를 선별해 주 1회 보충하고 생성기는 시연용 공간 부족분을 등록 |
| 호출·보호 | `http://api1:8000/internal/venues`로 직접 호출. 헤더 `X-Internal-Key` = `.env` `INTERNAL_API_KEY`. gw의 `/api/internal/` 차단은 유지하며, 직접 접근 범위는 VM 방화벽 정책을 따름 |
| 동작 | `(source_site, source_id)` UNIQUE로 upsert. 신규 201, 동일 내용 재전송을 포함한 기존 출처 갱신 200. `created_at`과 `is_active`는 갱신 시 보존 |
| 응답 | 신규 201·갱신 200 모두 최상위 `venue_id`·`ignored_facilities`. 무시한 시설이 없으면 빈 배열 |
| 시설·그림 | 시설은 이름으로 찾고 없는 이름은 `ignored_facilities`로 알림(동일 이름은 한 번). 시설·그림은 요청 값으로 통째로 바꾸며 생략하거나 빈 배열이면 기존 목록을 비움. 시설은 ID 기준 중복 제거, 그림은 요청 순서 저장 |
| 지역·유형 | 모르는 값이면 400 `UNKNOWN_REGION`·`UNKNOWN_CATEGORY`. B가 지역을 새로 만들지 않음 |
| 출처 | `spacecloud`·`shareit`·`synthetic`만 허용. 다른 출처는 400 `VALIDATION` |
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

신규 201·갱신 200의 응답은 같은 모양입니다. 아래 예시는 모르는 시설 이름을 무시한 경우입니다.

```json
{"venue_id": 123, "ignored_facilities": ["미등록 시설"]}
```

- 이름·소개·이용 안내는 크롤러·생성기가 **생성한 값**을 보냅니다. 업체 실명·소개 원문을 보내지 않을 책임은 호출 측에 있으며 API가 이름·본문의 출처를 자동 판별하지는 않습니다.
- 값 검증은 DDL의 CHECK와 같게 합니다(가격 > 0, 인원 ≥ 1, 영업시간 open 9~22·close 10~23, `min_hours` 1~4). 크롤러는 영업시간을 9~23으로 잘라 보냅니다(11-03 A2).
- 가격은 INT, 최대 인원은 SMALLINT의 저장 범위까지 검증합니다. 출처 ID는 빈 값 불가·50자 이내, 이름은 100자 이내, 설명·안내는 각각 UTF-8 65,535바이트 이내입니다. 그림은 `art:<영문 종류>-<0 또는 1>` 코드만 받고, 목록은 `sort_order` TINYINT에 맞춰 최대 128개입니다. 알 수 없는 본문 필드는 400 `VALIDATION`입니다.
- `min_hours`·영업시간 생략 시 기본값은 1·9·23, 설명·안내는 null입니다. 이 API는 전체 등록·교체 요청이므로 생략한 기존 값을 부분 유지하지 않습니다.
- 서비스에서 신규 INSERT를 시도하고 출처 UNIQUE의 1062면 롤백한 뒤 `INSERT … ON DUPLICATE KEY UPDATE`로 갱신합니다. 같은 요청을 그대로 다시 보내도 갱신 200을 반환하도록 `rowcount`로 신규 여부를 판단하지 않습니다. 공간·시설·그림은 최종 한 트랜잭션이며 어느 저장 단계가 실패해도 전부 롤백합니다.
- 생성기로 만든 공간도 같은 API로 넣습니다(`source_site = "synthetic"`). 1차 등록의 `source_site`는 `spacecloud`·`shareit`·`synthetic`입니다. 앞의 두 값은 속성 출처이며 실제 업체의 예약 가능 여부를 뜻하지 않습니다.

## 8. 테스트

| 파일 | 확인할 것 |
| --- | --- |
| test_catalog.py | 유형 5개, 시·도 → 시·군·구, 시설 목록 |
| test_reservation_dependencies.py | 모델 DDL·`get_owned()`·A 후기 작성 연결, `count_cancellable()`의 회원·상태·시작 정각·날짜 경계·0건·복수 예약 집계 및 호출자 트랜잭션 유지 |
| test_venues.py | 필터 조합, 정렬 4종, 칸 상태(taken·past), 이미지 누락 시 대표·갤러리 group-0, 실제 이미지 순서, NEW 오늘·13일 전 포함 및 14일 전·미래 제외, 비활성 404, 날짜 더보기(offset) |
| test_reservations.py | 성공 201(3개 표 모두 생김), **10분 안 같은 유효 요청은 200 + 같은 reservation_id(표에 새 행 없음)**, 취소·환불 건 재시도 제외, 취소 후 재예약의 새 ID 반환·타인 선점 409, 본인 예약 충돌의 최소 ID·혼합 소유자 정보 비노출, 결제수단·인원·기간·시간 검증, 지난 시간은 바로 completed, 가상 요청 키 확인, F-34 소유권·상태·시각 경계·환불·칸 반납·실패 롤백 |
| test_concurrency.py | **다른 회원 50명이 같은 칸을 동시에 요청하면 201 1건·409 49건**, 한 회원의 같은 요청 50건은 201 1건·200 49건, 겹치는 시간 경쟁, F-34 동시 취소 200 1건·409 1건. DB 행 수·이벤트·카운터 검증 |
| check_reservation_http.py (별도 실행) | 공식 앱·실제 가상 회원가입/로그인·Postman 컬렉션으로 OpenAPI·F-34 계약·401·생성·재시도·취소 응답, 취소 예약·환불 결제·해제된 칸·예약/취소 카운터와 가상 데이터 정리 확인 |
| test_jobs.py | 끝나는 시각이 지난 confirmed만 completed(오늘 끝난 것 포함), 두 번 돌려도 같음 |
| test_internal.py | 키 없음·오류·미설정 401 및 DB 접근 차단, 출처 3종 신규 201·동일 재전송/갱신 200, 같은 ID와 최상위 응답, 시설 무시·중복 제거·목록 교체/비우기, 원래 등록 시각 보존, 입력 오류 400, 신규/갱신 저장 실패 전체 롤백, 같은 출처 동시 8건의 201 1건·200 7건과 시설·그림 정합성 |
| check_internal_http.py (별도 실행) | 공식 앱·실제 내부 키·Postman으로 OpenAPI 200·키 없음 401·신규 201·재전송 200·갱신 200·출처 오류 400, DB 한 공간·목록 교체·검증 데이터 정리 확인 |
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
| 6 | 공간 등록 | **11-05 수집 방향**: 스페이스클라우드·쉐어잇 2곳의 속성 기반 시연용 공간과 생성기 공간 → `/internal/venues`. 영화관 없음, 강의실 유형 사용 |
| 7 | 취소 기한·환불 | 시작 전까지, 전액 |
| 8 | 결제수단 ENUM | 영문 코드로 저장 (DB 담당 동의 필요) |
