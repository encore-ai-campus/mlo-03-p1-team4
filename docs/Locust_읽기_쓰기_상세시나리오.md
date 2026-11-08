# Spacecube Locust 읽기·쓰기 상세 시나리오

작성: 2026-11-07 · Codex. **상세 설계와 11-07 실행 차이를 함께 적는다.** 실제 결과는 logs/loadsuite-*/RESULTS.md에 분리한다. 구현은 infra/vm/remote109/loadsuite이며 기존 배포 앱 코드는 변경하지 않았다.

기준: 로컬 HEAD `0d7bcb3`의 `backend/app/routers/`, `schemas/`, `core/`, `docs/백엔드_A_회원_후기_이벤트.md`, `docs/백엔드_B_공간_예약_결제_크롤링.md`, `simulator/locust/README.md`. 실제 배포 SHA·OpenAPI와 다르면 구현 전에 차이를 기록한다. 최신 develop이나 현재 VM이 이 SHA라는 뜻은 아니다.

## 1. 실행 대상과 작업 예약

**서버 공용 작업판:** `/home/playdata/spacecube109/SERVER_WORK_BOARD.md`. 배포 완료 인계·실제 VM IP 확인·작업 예약 후에만 실행한다. Codex와 Claude가 서로 다른 Locust를 동시에 돌리면 해당 실행은 단일 시나리오 결과로 사용할 수 없다.

| 항목 | 기준 / 확인할 내용 |
| --- | --- |
| 제어 노드 | `ssh playdata` → 2026-11-07 확인 주소 `192.168.219.102` |
| Host | **현재 정문 원점 http://192.168.219.218**. 경로에 /api를 한 번 붙임 |
| Locust 요청 경로 | `/api/venues`처럼 `/api`를 한 번 붙임. Host에 `/api`를 넣고 경로에도 다시 넣지 않음 |
| API 직접 호출 | 장애 격리용 별도 시험에서만. FastAPI 직결 주소는 `/api` 제거 여부를 실제 OpenAPI로 확인하고 정문 결과와 분리 |
| DB | 현재 192.168.219.212/213:3306/spacecube, MariaDB 10.11.14. 연결 제한 151/사용자 제한 0 유지 |
| MongoDB | 현재 192.168.219.216 MongoDB 8.0.34 온라인. API 202와 실제 적재 성공은 별도 확인 |
| 웹 이미지 | Locust HttpUser는 브라우저처럼 이미지·JS·CSS를 자동으로 받지 않음. 이번 API 용량 시험과 이미지 다운로드/화면 시험은 구분 |

호출 경로와 HTTP 메소드는 아래 표에서 `/api`를 포함해 표기한다. 실제 정문이 Nginx와 HAProxy를 어떤 순서로 지나는지는 배포 설정에서 확인한다.

## 2. 시험을 나누는 이유

| 시험군 | 목적 | 포함 | 분리하는 부하 |
| --- | --- | --- | --- |
| R-PUBLIC | 익명 공개 조회 용량 | 공개 GET 10종 | 로그인·이벤트 전송·데이터 변경 |
| R-PRIVATE | 로그인한 회원 조회 용량 | 내 정보·내 예약·내 후기 GET | 로그인 폭주, 쓰기 |
| A-AUTH | 비밀번호 해시 처리·인증 용량 | 로그인·가입·비밀번호 변경·탈퇴 | 예약 처리량 판정과 분리 |
| W-BOOK | 정상 예약·취소 처리량 | 서로 다른 계정·충돌 없는 시간 자원 | 같은 계정·같은 칸 경합 |
| W-REVIEW | 후기 생성·수정·삭제 | 본인 completed 예약으로 CRUD | 자격 오류를 반복하는 가짜 쓰기 |
| W-PROFILE | 단순 회원 정보 쓰기 | 본인 PATCH | bcrypt가 포함되는 비밀번호 변경 |
| W-EVENT | 이벤트 수용·로그 적재 | POST /events | MariaDB 트랜잭션 처리량 |
| C-COLLISION | 원자성·재시도·경합 정확성 | 같은 칸 예약·취소 경합 | 정상 용량 시험 |
| M-A7 | 최종 사용자 흐름 | Browser 60% / Booker 30% / Reviewer 10% | 위 단독 시험이 끝난 뒤 실행 |

**HTTP GET/POST와 DB 읽기/쓰기는 같은 분류가 아니다.** `POST /auth/login`은 비밀번호 검증과 primary 조회가 중심이고, `GET /users/me`·`GET /reservations/me` 등도 primary를 사용한다. 공개 GET만 replica 경로다. 인증 GET을 replica 부하로 합산하지 않는다.

현재 `infra/vm/remote109/locustfile.py`의 `ReadOnlyBrowser`는 검색 5·유형 2·상세 2·slots 1의 가중치와 대기 1~3초를 사용한다. 검색 첫 항목을 선택하고 검색 전 상세/slots 작업은 요청 없이 끝날 수 있다. **새 loadsuite 실행기는 읽기·쓰기·요청별 기록을 구현했고 경합은 C01/C02부터 실행한다.** 같은 이름의 기존 60초 결과와 새 시나리오를 직접 비교하지 않는다.

## 3. 공통 헤더·계정·데이터 준비

```text
X-Synthetic: 1
X-Synthetic-Key: 실행 환경의 SPACE_SYNTHETIC_KEY
X-Session-Id: 사용자 여정별 UUID
Authorization: Bearer <로그인 응답 access_token>   # 인증 API에만
Content-Type: application/json                    # JSON 본문에만
```

- 합성 키는 서버 `SYNTHETIC_API_KEY`와 일치해야 한다. 키 누락·오류의 401은 정상 부하 결과가 아니라 사전 준비 실패다. 비밀값을 문서·CLI 인자·로그·Git에 넣지 않는다.
- R-PUBLIC은 Authorization 없이 실행한다. R-PRIVATE/W 계정은 사용자 시작 때 로그인하고 워밍업에서 분리한다. 토큰은 응답의 `expires_in`을 사용해 만료 전에 갱신하며, 모든 사용자를 한 번에 재로그인시키지 않는다.
- **쓰기 VU 한 명당 전용 합성 계정 한 개 이상**을 할당한다. 50개 계정을 400명에게 돌려 쓰지 않는다. 예약 서비스는 동일 회원 행을 잠그므로 계정 공유가 별도 병목을 만든다.
- 분산 워커는 겹치지 않는 계정·시간 자원 묶음을 받는다. 각 워커가 같은 CSV의 첫 행부터 시작하면 안 된다. 총 계정 수는 전 워커 VU 합계와 비교한다.
- 실행 준비 원장에는 가명 `account_id`, `user_id`, 소유 예약/후기 ID, 허용 venue ID·날짜·시간, fixture 용도, 분할 번호를 둔다. 이메일·비밀번호를 담은 실행 입력은 Git 밖 보호 경로에서만 읽고 결과 원장에는 쓰지 않는다.
- 활성 공간·가격·정원·영업시간·`min_hours`를 실제 API에서 수집한다. 존재한다고 가정한 venue ID를 임의 생성하지 않는다. 페이지는 실제 `total`에 맞춰 고른다.
- 미래 confirmed 예약, 후기 없는 completed 예약, 수정·삭제할 후기, 탈퇴용 일회용 계정을 **서로 다른 fixture 묶음**으로 준비한다. 본 부하 전에 생성한 건수도 기록한다.
- 날짜는 서버의 한국 날짜와 available-dates의 min/max 범위를 따른다. 운영 VM에 `TODAY_OVERRIDE`를 바꿔 날짜를 맞추지 않는다. 지난 시간도 예약할 수 있으므로 `past=true`만으로 점유로 판정하지 않는다.
- 예약의 `hours`는 `min_hours` 이상·최대 4, 시작·끝은 실제 영업시간 안, 인원은 정원 이하로 고른다. `taken=false` 조회는 참고이고 최종 승자는 INSERT 제약이 결정한다.
- 준비 중 호출과 측정 호출은 별도 파일·통계 그룹으로 구분한다. 계정/예약 부족이면 `fixture_exhausted`를 기록하고 해당 시험을 멈춘다. 무한 조회만 계속하면서 쓰기 부하를 유지했다고 보고하지 않는다.

## 4. 읽기 API: 메소드별 계약과 검증

### 4-1. 공개 GET — R-PUBLIC

아래 가중치는 **단일 HTTP 요청을 보내는 task의 선택 비중**으로 합계 100이다. 실제 완료 요청 비율도 결과에서 확인한다. 준비 때 ID·검색 조건 목록을 확보해 task를 아무 요청 없이 건너뛰는 일을 없앤다. 실제 사용자 여정 비중과는 다르다.

| ID / F-ID | 메소드·경로 | 비중 | 입력·분포 | 정상 응답과 검사 |
| --- | --- | ---: | --- | --- |
| R01 / F-10 | GET `/api/categories` | 3 | 파라미터 없음 | 200 배열, 유형 5개의 code/name. 5분 캐시 효과가 포함되는 점 기록 |
| R02 / F-11 | GET `/api/regions` | 2 | 50% 시도 전체, 50% `sido=<실제 시도>` | 200. 전체는 문자열 목록, sido 지정 시 region_id/sigungu 항목 목록. 존재하는 지역만 사용 |
| R03 / 기준 정보 | GET `/api/facilities` | 1 | 없음 | 200 배열, facility_id/name. 캐시 경로 포함 |
| R04 / F-12·13 | GET `/api/venues` | 30 | 기본 page=1,size=10. 아래 검색 분포 적용 | 200 `items,page,size,total`, 유형·인원·가격·시간 조건 일치. 빈 결과는 허용하되 비율 기록 |
| R05 / F-14 | GET `/api/venues/new` | 4 | page=1,size=10 위주, 실제 페이지 범위 내 변화 | 200 공통 목록 + registered_on/new_days_left. 최근 14일 데이터가 없으면 빈 배열은 정상 |
| R06 / F-20 | GET `/api/venues/{venue_id}` | 20 | 활성 공간에서 균등 선택. 별도 hot 분포 시험도 실시 | 200, 요청 ID·유형·정원·가격·min_hours·영업시간·slots 구조 검사 |
| R07 / F-21 | GET `/api/venues/{venue_id}/available-dates` | 10 | `days=14,offset=0` 80%, `offset=14` 20%. 실제 범위에 맞춤 | 200, venue_id·min_date·max_date·dates. 상한에 걸리면 요청 days보다 짧아도 정상 |
| R08 / F-22 | GET `/api/venues/{venue_id}/slots` | 15 | `date=YYYY-MM-DD`, 허용 기간 안의 실제 날짜 | 200 배열, `hour,taken,past`. hour 중복 없음·영업시간 범위 검사 |
| R09 / F-51 | GET `/api/venues/{venue_id}/reviews` | 5 | page=1,size=10, 후기 유/무 공간을 섞음 | 200 목록, 각 venue_id 일치. 해당 공간 후기 0건도 정상 |
| R10 / F-51 | GET `/api/reviews` | 10 | category는 5개 유형 분산. sort recent/high/low=60/20/20 | 200 목록, 유형 필터·별점 정렬 검사. 페이지 경계·동률 정렬 규칙은 API 계약에 맞춤 |

R04 검색 내부 분포 제안:

| 검색 유형 | R04 내부 비중 | 파라미터 예시 / 주의 |
| --- | ---: | --- |
| 유형만 | 20% | `category=studyroom` 등 5개 유형 균등 |
| 지역 | 20% | 실제 `sido`, `sigungu` 조합 + category 선택 |
| 날짜·시간·인원 | 25% | `date`, `start_hour`, `hours`, `people`를 함께 유효하게 구성 |
| 시설 | 15% | API에서 받은 facility_id를 쉼표로 연결. 실제 존재하는 1~3개 |
| 정렬 | 15% | `sort=popular/price/rating` 균등. `price_asc`, `rating_desc`는 계약에 없음 |
| 검색어 | 5% | 합성 공간 이름에서 얻은 비개인 문자열 `q`. 없는 검색어만 반복하지 않음 |

검색 페이징은 1페이지 70%, 존재하는 나머지 페이지 30%를 제안한다. 전체 공간에 고르게 보내는 시험과 상위 20% 공간에 80% 요청을 보내는 hot 시험을 별도 run으로 남긴다. 이는 실측 사용자 통계가 아니라 병목 비교용 제안이다.

`GET /api/auth/email-check?email=...`도 구현되어 있고 200 `available`을 반환하지만 **primary 조회·가입 시나리오 준비 단계**에 둔다. 접근 로그에서 이메일 query가 제거되는지 확인하기 전 반복 부하에 넣지 않는다. DB 비쓰기 GET이라고 replica 시험에 넣지 않는다.

### 4-2. 인증된 GET — R-PRIVATE

전용 계정 로그인은 준비/워밍업으로 분리한다. 같은 응답을 다른 회원의 데이터와 혼동하지 않도록 fixture 소유권을 확인한다.

| ID / F-ID | 메소드·경로 | 비중 | 요청·성공 판정 |
| --- | --- | ---: | --- |
| R11 / F-40 | GET `/api/reservations/me` | 50 | status 생략 또는 confirmed/completed/cancelled, page=1,size=10. 200 공통 목록·본인 fixture ID·payment·can_cancel·nullable review_id 검사 |
| R12 / F-40 | GET `/api/reservations/{reservation_id}` | 20 | 본인 fixture ID. 200·예약 ID·상태·금액 일치. 예약이 없으면 임의 ID 요청 대신 준비 실패 |
| R13 / F-03 | GET `/api/users/me` | 15 | 200, 로그인한 user_id 일치·password_hash 미노출. 응답 개인정보는 결과 파일에 기록하지 않음 |
| R14 / F-41 | GET `/api/users/me/reviews` | 15 | page=1,size=10. 200, 작성 직후의 본인 후기 확인에 사용. 빈 목록이 전부인 데이터셋으로 목록 부하를 대체하지 않음 |

모두 인증·내 것 경로이므로 primary를 사용한다. 공개 후기/공간 조회의 replica 반영 지연과 섞어 즉시 일치 검사를 하지 않는다.

## 5. 쓰기·인증 API: 메소드별 세부 시나리오

### W01 — POST `/api/reservations`: 정상 예약·모의 결제 (F-30~32)

1. 전용 회원 토큰과 충돌 없는 fixture 공간/날짜/시간을 할당한다. 미래 이용 시작까지 충분한 여유가 있는 자원을 사용한다.
2. 상세에서 min_hours/정원/가격/영업시간을, slots에서 점유를 읽는다. 정상 용량 시험에서는 각 동시 사용자가 서로 다른 시간 자원을 사용한다.
3. 아래 본문으로 한 번 POST한다. 결제는 이 호출에 포함되며 별도의 `/confirm`, `/payments` 호출은 없다.

```json
{"venue_id":7,"date":"2026-11-08","start_hour":13,"hours":2,"headcount":4,"method":"card"}
```

숫자·날짜는 형식 예시다. 실제 존재하는 fixture 값으로 대체한다. 금액을 본문으로 보내지 않는다. 결제수단 `card/transfer/phone`은 60/30/10%를 제안한다. 실제 결제는 발생하지 않는다.

4. **신규 생성은 201**이며 reservation_id>0, venue/date/start/end/headcount 일치, `end_hour=start_hour+hours`, `total_price=price_per_hour×hours`, 미래 예약은 `confirmed`, `payment.status=paid`를 검사한다.
5. `GET /api/reservations/{id}`로 primary에서 소유·상태·금액을 검증한다. 새 생성 단계에서 뜻밖의 200이 계속 나오면 이미 존재하는 예약만 재사용하는 것은 아닌지 fixture를 확인한다.
6. 정상 자원 분리 시험에서 409는 **의도하지 않은 충돌**로 별도 실패 집계한다. 실제 사용자 혼합 시험에서는 `SLOT_TAKEN`일 때만 대안 날짜/시간으로 최대 2번 재시도하고, 모두 차면 사용자 여정 실패로 기록한다.
7. timeout은 서버에서 이미 커밋했을 수 있다. 결과를 모른 채 새 body로 중복 결제하지 않는다. 같은 body의 제한된 재시도 또는 내 예약 조회로 확인하며, 원래 timeout은 성능 오류 통계에 남긴다.

409 후 재조회 주의: 프로젝트 규칙은 충돌 뒤 최신 칸 확인을 primary로 하도록 하지만, 현재 공개 `/slots` 라우터는 `get_db_read`를 사용하고 강제 primary 요청 옵션이 없다. Locust가 임의 헤더로 이를 해결했다고 가정하지 않는다. 이 차이는 B 담당에게 확인하고, 공개 slots의 지연·POST 최종 판정을 별도 기록한다.

예약 DB 원자성 검증은 run이 만든 reservation_id 집합으로 `reservations`·`payments`·`reservation_slots`를 대조한다. SQL을 직접 쓰는 것은 DB 담당이 수행하고, Locust가 DB 비밀번호를 갖고 임의 정리하지 않는다.

### W02 — POST `/api/reservations/{id}/cancel`: 취소·환불 (F-34)

1. W01에서 이 실행이 새로 만든 본인 미래 예약의 `can_cancel=true`를 확인한다. 본문 없이 POST한다.
2. 200, 같은 ID, `status=cancelled`, `payment.status=refunded`, `refunded_at` 존재, `can_cancel=false`를 검사한다.
3. 본인 예약 상세·목록을 primary에서 다시 읽어 같은 상태를 확인한다. 공개 slots는 replica일 수 있어 즉시 해제만으로 오류 판정하지 않는다. 해제 반영 시간도 따로 잰다.
4. 같은 요청을 다시 보내는 별도 부정 시험에서는 409 `ALREADY_CANCELLED`. 완료/시작된 예약은 409 `NOT_CANCELLABLE`. 첫 취소 정상 흐름에서 이 응답이 나오면 준비·동시성 오류다.
5. 취소 뒤 같은 본문으로 새 예약하면 **새로운 reservation_id와 201**이어야 한다. 취소·환불된 예약을 재시도 성공 200으로 반환하면 실패다.

W-BOOK은 우선 **예약→검증→취소→검증** 순환으로 돌려 슬롯을 반환한다. 예약을 유지하는 실사용형 시험은 별도 실행하고 필요한 시간 자원 수를 계산한다. 슬롯 반환으로 같은 시간을 다시 써도 예약·결제 이력 행은 계속 쌓인다.

### W03 — POST `/api/reservations/{id}/review`: 후기 생성 (F-50)

1. 본인 소유·completed·후기 미작성·작성 기한 이내인 예약을 독점 할당한다. 어제 날짜의 비어 있는 시간에 API로 예약하면 생성 시 completed가 되는 규칙을 준비 단계에서 활용할 수 있다. 날짜 허용 범위·실제 정원을 지킨다.
2. 현재 구현의 기한은 `max(reserve_date, created_at.date()) + 7일`이다. 오래된 fixtures의 기한도 확인한다.
3. `{"rating":5,"content":"합성 부하 시험 후기"}`로 POST. 201 및 review_id를 저장하고 `GET /api/users/me/reviews`에서 확인한다. 목록의 최신 페이지 범위 안에서 찾거나 페이지를 이동한다.
4. 공개 후기 목록·평점은 replica라 지연이 있을 수 있다. 즉시 내 후기(primary) 검증과 공개 반영 시간 측정을 분리한다.
5. 같은 예약에 다시 작성하면 409 `REVIEW_EXISTS`. 삭제된 후기도 이력·예약당 1개 제약이 남으므로 **후기 삭제 후 같은 예약으로 무한 재작성하지 않는다.** 새 completed 예약 fixture가 필요하다.
6. 정상 생성 흐름에서 403 `NOT_COMPLETED`/`REVIEW_PERIOD_OVER`가 나오면 처리량 성공으로 치지 않는다. 자격 fixture 실패로 분류한다.

### W04 — PATCH `/api/reviews/{review_id}`: 후기 수정 (F-50)

- W03이 반환한 본인 review_id로 `{"rating":4,"content":"합성 부하 시험 후기 수정"}` 전송. 200·같은 review_id를 확인한다.
- 내 후기에서 변경 내용을 확인한다. 빈 body·null·1~5 범위 밖 별점은 부정 시험에만 사용한다.
- 삭제된 후기·다른 계정의 후기를 랜덤 ID로 수정하는 것은 정상 쓰기 시험이 아니다.

### W05 — DELETE `/api/reviews/{review_id}`: 후기 삭제 (F-50)

- 해당 여정이 만든 본인 후기만 DELETE하고 204를 검사한다. 빈 204 body를 JSON으로 파싱하지 않는다.
- 내 후기에서 사라지는지 확인한다. DB 소프트 삭제·예약의 작성 이력 review_id 유지 여부는 DB/계약 검증으로 확인한다.
- 실제 회원 데이터나 다른 run의 후기를 정리하지 않는다. 삭제해도 디스크/이력 데이터가 사라지는 시험으로 해석하지 않는다.

### W06 — PATCH `/api/users/me`: 회원 정보 수정 (F-03)

- 전용 합성 계정으로 `{"marketing_agreed":true}`와 false를 번갈아 전송한다. 필요하면 name도 가명으로 교체한다.
- 200 뒤 GET `/api/users/me`에서 값을 확인한다. 빈 body, name=null, 공백 이름, marketing_agreed=null은 정상 부하에 넣지 않는다. phone=null은 현재 계약상 허용된다.
- 계정 한 개를 여러 VU가 수정하지 않는다. 마지막 쓰기 값 덮어쓰기를 처리량 성공과 혼동하지 않는다.

### A01 — POST `/api/auth/login`: 로그인 (F-02)

- JSON은 `{"email":"${SYNTHETIC_EMAIL}","password":"${SYNTHETIC_PASSWORD}"}` 형식. 실행 시 환경/보호 입력으로 값을 치환한다.
- 200·access_token·token_type=bearer·expires_in>0를 검사하고 토큰을 메모리에 보관한다. 토큰 본문은 기록하지 않는다.
- DB 신규 행 추가보다 bcrypt CPU·primary 조회 비용을 보는 시험이다. 정상 로그인만 측정하고 의도한 잘못된 비밀번호의 401 `INVALID_CREDENTIALS`는 별도 시험으로 분리한다.
- W01을 반복할 때마다 로그인하지 않는다. 로그인 폭주와 예약 용량은 별도 run으로 잰다.

### A02 — POST `/api/auth/signup`: 가입 (F-01)

```json
{
  "email":"${UNIQUE_SYNTHETIC_EMAIL}",
  "password":"${SYNTHETIC_PASSWORD}",
  "name":"합성시험회원",
  "phone":"${SYNTHETIC_PHONE}",
  "birth":"000101",
  "gender_digit":"3",
  "marketing_agreed":false,
  "terms_agreed":true,
  "privacy_agreed":true
}
```

- 예시의 생년월일은 2000-01-01을 뜻한다. 실행일에 만 14세 이상이어야 한다. 비밀번호는 8자 이상·UTF-8 72바이트 이하, 전화번호는 계약에 맞는 합성 fixture로 치환한다.
- run·worker·일련번호로 중복 없는 이메일을 만든다. 201 user_id 저장, 이어 로그인 200·users/me user_id 일치까지 확인한다.
- 409 `EMAIL_TAKEN`을 계속 허용하면 실제로는 INSERT가 없는 시험이다. 정상 가입에서 중복은 준비 실패이며 의도한 중복 시험과 분리한다.
- 가입은 bcrypt+INSERT·계정 행 증가를 포함하므로 낮은 단계부터 독립 실행한다. 생성 계정 수·run 소유 ID를 기록한다.

### A03 — POST `/api/auth/logout`: 로그아웃 (F-02)

- 유효한 Bearer로 본문 없이 POST → 204. 이후 Locust 사용자 메모리에서 토큰을 지운다.
- 현재 계약은 서버 JWT 폐기 목록이 없으므로 **로그아웃 후 복사한 토큰이 즉시 401이어야 한다는 검증을 넣지 않는다.** 인증 세션 종료/클라이언트 동작 확인이며 DB 쓰기 처리량과 분리한다.

### A04 — PATCH `/api/users/me/password`: 비밀번호 변경 (F-03)

- 전용 격리 계정으로 `{"current_password":"${CURRENT_PASSWORD}","new_password":"${NEXT_PASSWORD}"}` 전송 → 204.
- VU가 새 비밀번호 상태를 갱신하고 새 값으로 로그인해 확인한다. 이어지는 요청을 옛 값으로 보내지 않는다. 타 시험과 계정 공유 금지.
- bcrypt 비용이 크므로 W06 단순 PATCH와 별도 그래프로 본다. `WRONG_PASSWORD` 등 의도하지 않은 400은 fixture 상태 오류다.

### A05 — DELETE `/api/users/me`: 탈퇴 (F-04)

- 이 시험만을 위해 생성한 일회용 합성 계정으로 실행한다. DELETE → 204 후 이전 이메일로 로그인은 401 `INVALID_CREDENTIALS`.
- 미래 confirmed 예약이 있으면 409 `HAS_UPCOMING_RESERVATION` 및 detail.count를 검증하는 별도 사례를 둔다. 정상 탈퇴의 준비 계정은 해당 예약이 없어야 한다.
- 탈퇴는 개인정보 익명화이며 예약·결제·후기 이력을 삭제하는 데이터 청소 기능이 아니다. 공용 부하 계정 50개를 탈퇴시켜 재사용 불가로 만들지 않는다.

### W07 — POST `/api/events`: 이벤트 기록 (F-60)

```json
{
  "session_id":"9414c39c-6f35-46d1-aeaf-e1334ec137bd",
  "events":[{
    "schema_version":1,"event_name":"page_view",
    "event_id":"5f6a5681-7536-4eaf-91c2-193a1d36fa8b",
    "user":{"anonymous_id":"synthetic-example","session_id":"9414c39c-6f35-46d1-aeaf-e1334ec137bd","session_sequence":1},
    "site":{"site_id":"main","hostname":"192.168.219.218","platform":"desktop_web"},
    "acquisition":{"landing_url":"http://192.168.219.218/","referrer_url":null},
    "page":{"page_view_id":"4f6a5681-7536-4eaf-91c2-193a1d36fa8b","page_type":"home","url":"http://192.168.219.218/","path":"/"},
    "navigation":{"from":null,"to":{"site_id":"main","url":"http://192.168.219.218/","path":"/"},"navigation_type":"direct"}
  }]
}
```

- 현재 배포는 중첩 v1 계약이다. 예전 event_type/venue_id/payload 형식은 사용하지 않는다. batch와 user.session_id, X-Session-Id를 맞추고 event_id는 매번 새 UUID, session_sequence는 증가시킨다.
- schema_version=1·user만 있어도 충분한 것은 아니다. site/acquisition/page/navigation의 필수 문맥을 서비스가 검증한다. 처음 실행은 이 문맥 누락으로 이벤트 400을 받아 안전 중단했고, 위 형식은 배포 validator 및 실제 202 accepted=1·ignored=[]로 재검증했다.
- 프론트 행동: page_view, product_impression, product_view, product_section_click, search_submit, availability_view, rental_slot_select, reservation_start, reservation_cancel_attempt, review_create, login, signup.
- 서버 전용 행동: reservation_complete, reservation_conflict, reservation_cancel_complete. 클라이언트에서 전송하지 않는다. 상품 행동은 products에 실제 product_id 하나를 보내고 상품 스냅샷은 서버가 채운다.
- 새 실행기는 batch 10건을 사용한다. 1/10/50건 비교는 별도 후속 시험이다. 202 + accepted=보낸 수 + ignored=[]를 검사하며 accepted=0은 성공 부하로 치지 않는다.
- batch RPS와 accepted 이벤트/초를 분리한다. HTTP 202·Loki 라인 수·Mongo 문서 수는 같다고 가정하지 않는다. Mongo 이벤트의 TTL은 received_at 기준 365일이며 event_daily에는 같은 TTL을 적용하지 않는다.
- 계정 정보·SQL 원문·비밀값·자유 글을 이벤트에 넣지 않는다. 알 수 없는 event_name·51건 batch의 부정 시험은 별도 수행한다.

## 6. 사용자 여정: 순서·대기·쓰기 비율

| 클래스 제안 | 요청 순서 | 행동 대기 | 종료·실패 처리 |
| --- | --- | --- | --- |
| PublicReadUser | R01~R10 단일 요청 가중 선택 | task 사이 1~5초 | 각 task 1요청. 모든 ID·날짜는 준비한 유효 pool 사용 |
| PrivateReadUser | 준비 로그인 → R11~R14 가중 선택 | task 사이 1~5초 | 인증 실패 시 중지·분리 집계. 무한 로그인 루프 금지 |
| BookingTurnoverUser | 준비 로그인 → 검색 → 상세 → 날짜 → slots → W01 → 예약 상세 → W02 → 예약 상세 | 행동 단계 사이 1~5초 | 201·환불까지 한 여정. 409 대안 최대 2회. 종료 시 남은 본인 예약 원장 기록 |
| ReviewCrudUser | 준비 로그인 → 내 completed 예약 선택 → W03 → 내 후기 확인 → W04 → 확인 → W05 → 확인 | 단계 사이 1~5초 | 한 completed 예약을 한 여정에서만 소비. fixture 고갈 시 중지 |
| ProfileWriteUser | 준비 로그인 → W06 → R13 확인 | 두 요청 사이 1~3초, 반복 사이 1~5초 | 계정별 갱신 값 관리 |
| AuthUser | A01/A02/A03/A04/A05 중 선택한 단독 모드 | 1~5초 | signup/password/delete fixture 분리. 생성·종료 수 기록 |
| EventUser | 세션 이벤트 묶음 W07 | batch 사이 1~5초 | batch 크기별 별도 측정 |

Locust task 하나 안의 코드는 순서대로 실행된다. **task 전체 끝에만 적용되는 wait_time을 단계 사이 대기로 착각하지 않는다.** 여정 내부의 생각 시간은 별도로 구현한다. 단독 요청 가중치는 여정 내부 요청 비율이나 CPU 사용 비율을 보장하지 않는다. [Locust 공식 작성 문서](https://docs.locust.io/en/stable/writing-a-locustfile.html)

권장 실행 순서: R-PUBLIC → R-PRIVATE → W-BOOK → W-REVIEW → W-PROFILE → A-AUTH → W-EVENT → C-COLLISION → M-A7. 각 단독 모드는 1→5명 smoke부터 통과시킨다. 쓰기 모드의 GET 검증 요청도 발생하므로 **순수 POST RPS**와 **여정 전체 HTTP RPS**를 따로 보고한다.

최종 M-A7의 60/30/10은 **사용자 클래스 비중**이다. Browser는 검색→상세→날짜→slots→후기에서 종료, Booker는 검색→예약→내역, Reviewer는 내역→후기 CRUD를 수행한다. Booker는 80% 예약 유지·20% 취소를 초기 실험 가정으로 제안하되 fixture 수가 부족하면 실행 전에 비율을 명시적으로 바꾼다. 계정·시간 자원 수와 실제 API 요청 비중을 보고서에 함께 기록한다.

## 7. 예약 경합·재시도 정확성: 별도 실행

| 시험 | 준비·동시성 | 기대 결과 | 실패 조건 |
| --- | --- | --- | --- |
| C01 SameSlotRush | **서로 다른 50계정**, 빈 동일 공간·날짜·동일 연속 칸, 예약 body의 시간 동일 | 201 정확히 1건, 409 SLOT_TAKEN 49건 | 201 2건 이상, 200 등장(준비 오염 여부 확인), 5xx·timeout, 슬롯·결제 중복 |
| C02 SameUserRetry | **한 계정의 같은 body**, 사전 예약 없는 칸에 50요청 | 201 1건·200 49건, 모두 같은 reservation_id | ID 여러 개·결제 추가·200이 아닌 재시도 응답 |
| C03 PartialOverlap | 두 계정, 일부 시간만 겹치는 예약을 동시 전송 | 한 예약만 커밋, 패자는 409, 부분 INSERT 없음 | reservations만 남음·payment만 남음·부분 슬롯 점유 |
| C04 CancelRace | 본인 미래 예약 하나에 같은 계정으로 취소 2요청 | 200 1건·409 ALREADY_CANCELLED 1건 | 이중 환불·잘못된 slots 삭제 |
| C05 CancelThenRebook | 생성→취소→같은 조건 재예약 | 신규 201·새 ID·paid, 옛 예약 cancelled/refunded 유지 | 옛 ID를 200으로 재사용 |
| C06 ReadYourWrites | 생성/취소/후기 직후 내 것 GET | primary 결과 즉시 일치 | 내 것 GET에서 쓰기 전 값이 보임. 공개 replica 지연은 별도 지표 |

HTTP 요청 출발은 gevent 동시 실행·barrier 또는 공통 시작 시각으로 맞추고, 클라이언트 출발 시각 분산을 기록한다. `spawn_rate=50`은 1초 동안 사용자 생성 속도일 뿐 같은 순간 INSERT를 보장하지 않는다. 여러 워커에서는 워커 간 동기화도 필요하다. 승자의 검증이 끝날 때까지 취소를 보내지 않아 슬롯을 재개방하지 않는다.

현재 재시도 계약은 10분 안의 같은 사용자·공간·날짜·시작·시간에 대한 유효 예약 재사용이다. **Idempotency-Key 헤더 계약은 없다.** 존재하지 않는 헤더로 중복 방지가 구현되어 있다고 가정하지 않는다.

## 8. 부하 단계·측정 구간·실패 지점 확장

### 단계 A — 준비/짧은 탐색

- smoke: 1→5명, 각 30~60초. status·body·데이터 쓰임을 먼저 확인.
- 짧은 탐색 제안: **5→20→50→100→200→400명**, 각 목표 도달 후 60초. 오류 원인 탐색용이며 A7 합격 판정이 아니다.
- 쓰기 시작은 반드시 5→20→50부터. 계정/슬롯/후기 fixture 예산이 모자라면 인원을 늘리지 않는다.
- 동일 설정에서 중복 fixture·인증 실패·run 밖 데이터 혼입이 발견되면 시스템 한계가 아니라 **시험 무효/준비 실패**로 중지한다.

### 단계 B — A7 공식 판정

- 우선 50명. 목표 인원 도달 후 **10분 = 워밍업 60초 + 본 측정 540초**로 통일한다. 램프업은 이 10분 밖에 별도 기록한다. 각 run의 실제 구간을 남긴다.
- 대기·spawn rate·API 구성·VM 사양·유선/무선·DB 데이터·워커·Uvicorn 동시성·DB 풀을 고정한다. 단계 간 2분 이상 또는 사전 상태 복구까지 기다리고, 서로 다른 부하 모드는 별도 run_id로 기록한다.
- 조회 p95 **300ms 미만**, 예약 p95 **500ms 미만**, 로그인·가입 p95 **800ms 미만**, 가용성 오류율 **1% 미만**이 기존 A7 기준이다. 수정/삭제·이벤트의 개별 목표는 아직 확정값이 아니므로 원자료를 보고하고 예약 기준으로 임의 대체하지 않는다.
- p95는 API별·정상 응답별로 본다. 1ms짜리 409가 많이 섞여 예약 p95가 낮아지는 경우를 성공 예약 성능으로 해석하지 않는다.

### 단계 C — 실패 지점에서 다시 확장

최초 실패가 F이면 **그 실행의 단계 목록에서 실패 단계보다 세 칸 앞**부터 다시 시작한다. `F/8` 같은 산술식으로 대신하지 않는다.

예: `[5,20,50,100,200,400]`에서 400명 실패 → 50→100→200→400 재시험. 400이 같은 조건으로 통과하고 발생기·fixture 여유가 있으면 800→1600으로 두 배씩 확장한다. 200 통과·400 실패라면 경계를 더 정확히 볼 때 250→300→350 같은 중간 단계를 추가한다. 새 파라미터는 결과에 적는다.

**코드/DB/VM/워커/동시성 설정을 한꺼번에 올리지 않는다.** 먼저 실패 원인과 계측 상태를 확인하고 한 변수씩 바꾼 비교 run을 만든다. 오류 1% 이상이 30초 지속, 양 API가 DOWN, 연결 실패 급증, OOM/디스크 부족 시 자동 탐색 중단을 제안한다. 이는 새 운영 SLO가 아니라 실험 중단 규칙이며 실행 전 담당자가 확정한다.

### 이전 결과를 읽는 법

11-06 동시성 200의 짧은 읽기 시험은 200명에서 오류 0·86.94 RPS·p95 430ms, 400명에서 124.02 RPS·503 155/7360건(2.11%)·p95 940ms였다. **200명도 조회 p95 300ms 기준은 넘었으므로 ‘SLO를 만족하는 최대 200명’으로 부르면 안 된다.**

400명에서는 Uvicorn `Exceeded concurrency limit`와 HAProxy health 503→backend DOWN을 관측했다. 그 원인 사슬을 재확인해야 하며 DB 최대 처리량이라고 단정할 근거는 없었다. 최고 CPU는 api1 55.8%·api2 57.2%(1분 rate를 15초 간격 수집한 값)였고 순간 최고 CPU가 아니다. 새 VM 결과와 하드웨어/조건이 같다고 가정하지 않는다. 근거: `infra/vm/remote109/LOAD-RESULTS-20261106.md`.

## 9. 오류를 숨기지 않는 판정·통계

| 분류 | 예시 | 집계 방법 |
| --- | --- | --- |
| 가용성 오류 | 모든 5xx·연결 실패·timeout | A7 오류 분자. 재시도 성공해도 첫 실패를 지우지 않음 |
| 계약/정합성 오류 | 200인데 필수 값 없음·예약 금액/ID 불일치·중복 결제 | 별도 실패. 가용성 오류율과 분리해도 전체 run 합격을 막음 |
| 의도한 업무 응답 | C01의 정확한 409 SLOT_TAKEN, 부정 사례의 지정 400/401 | 해당 사례에서 body code까지 맞을 때만 expected로 처리. 상태별 카운터와 실제 비율은 보존 |
| 의도하지 않은 4xx | 정상 예약 409·정상 토큰 401·다른 ID 404·잘못 만든 body 400 | 정상 성공으로 바꾸지 않음. fixture/구현/권한 원인 별도 실패 |
| 데이터 준비 실패 | 계정 중복·빈 fixture pool·min_hours 불일치 | 용량 한계로 해석하지 않고 run 무효/중단 |

`catch_response=True`로 JSON 형식·domain code까지 검사한다. `response.success()`는 **의도한 사례의 정확한 기대 응답에만** 사용한다. 모든 409/401/400을 전역 성공으로 바꾸지 않는다. [Locust 공식 응답 검사 설명](https://docs.locust.io/en/stable/writing-a-locustfile.html)

보고할 숫자: 요청 시도 RPS, 정상 HTTP RPS, 신규 예약 201/s, 재시도 200/s, 충돌 409/s, 취소 200/s, 후기 201/s, accepted events/s, 완주 여정/s. 지연은 API별 p50/p95/p99와 예약 여정 전체 시간을 구분한다. VU·HTTP in-flight·프록시 세션·DB 연결은 서로 다른 숫자다.

RPS는 task당 요청 수·대기·응답시간으로 달라진다. 예를 들어 한 여정에 요청 8개와 단계 대기 7번이 있으면 50/평균 대기만으로 RPS를 계산할 수 없다. **관측 RPS**를 기록하고 최대 사용자는 고정 시험 조건·SLO와 함께 말한다.

## 10. Grafana·Loki에서 같이 볼 항목

실제 수집 중인 metric/label을 먼저 확인한다. 아래는 저장소 대시보드의 이름을 기준으로 한 관측 목록이며 현재 VM에서 모두 온라인이라는 보장은 아니다. 없는 지표는 0이 아니라 **N/A / 미수집**으로 표시한다.

| 층 | 볼 지표·로그 | 해석 |
| --- | --- | --- |
| 발생 PC/Locust | 실제 VU·worker 수·CPU/RAM·NIC·요청 RPS·전송 지연·CPU 경고 | 발생기가 먼저 포화됐는지 확인. 발생기 CPU 부족 시 별도 worker/PC 확장 후 조건을 기록 |
| 정문/Nginx | access status별 요청·RPS, active connections, upstream 지연(로그 필드가 있을 때) | 정문 503과 앱 HTTP 수를 비교. health·정적 파일은 API 부하와 구분 |
| HAProxy | server별 loadbalanced_total·current_sessions·status·check_failures·check_up_down | api1/api2 편중·health DOWN·연쇄 오류 확인. 세션 수를 Uvicorn 워커 연결 수라고 부르지 않음 |
| FastAPI | `http_requests_total` handler/method/status, duration histogram, process RSS | API별 정상 p95·5xx·메모리. Uvicorn 선제 503은 앱 미들웨어 이전이라 여기서 빠질 수 있음 |
| API VM | node CPU 모드별·MemAvailable·swap·디스크 await/사용률·NIC | 평균 CPU만으로 여유 판단 금지. 한 코어/프로세스 편중과 DB 대기도 확인 |
| MariaDB | mysql_up·threads_connected/running·max_used_connections/max_connections·connection_errors | 현재 max_connections를 실제 값으로 읽음. 과거 AWS 예시의 28개를 현재 VM 한계로 사용하지 않음 |
| InnoDB/복제 | row lock waits·deadlocks·replica I/O/SQL 상태·seconds behind master | 같은 계정 잠금·슬롯 경합·공개 조회 지연을 구분. exporter에 안 나오면 DB 담당에게 읽기 진단 요청 |
| 저장소/이벤트 | table data_length/index_length·디스크 여유·accepted·mongo_event_write_failures_total | 표 용량은 곧바로 반영되지 않을 수 있음. HTTP 202와 영속 저장 완료는 별개 |
| 공통 로그 | `Exceeded concurrency limit`, `QueuePool limit`, lock wait timeout, deadlock, HAProxy DOWN/UP | 최초 오류 시각 전후 최소 1분을 합쳐 확인 |

소스의 DB 풀은 프로세스·엔진별 `pool_size=3,max_overflow=2,pool_timeout=3초`다. **배포 코드도 같고 API VM 2대×각 worker 2개라면** 지속 애플리케이션 풀 상한은 primary 최대 20연결·replica 최대 20연결의 이론값이다. health의 별도 연결·다른 도구·서비스는 추가될 수 있고 read fallback이면 엔진 구성이 달라진다. 이는 실제 연결 수나 MariaDB 전체 max_connections가 아니다. 먼저 배포 코드·프로세스 수를 확인한다.

예시 쿼리(실제 라벨 확인 후 사용):

```promql
# API method·status별 RPS. handler 필터로 /health·/metrics를 필요에 맞게 제외한다.
sum by (server, method, handler, status) (rate(http_requests_total{job="api"}[1m]))

# VM 전체 코어 평균 CPU 사용률
100 * (1 - avg by (server) (rate(node_cpu_seconds_total{job="nodes",mode="idle"}[1m])))

# VM 메모리 사용률(사용 가능 메모리 기준)
100 * (1 - node_memory_MemAvailable_bytes{job="nodes"} / node_memory_MemTotal_bytes{job="nodes"})

# primary/replica 앱 연결 수
mysql_global_status_threads_connected{job="mariadb"}
```

```logql
{job="journal",server=~"api1|api2"} |= "Exceeded concurrency limit"
{job="api"} | json | status >= 500
```

기존 Instrumentator histogram의 method/status 라벨 유무는 metric별로 다를 수 있다. 없는 라벨로 ‘성공 예약만 p95’를 계산했다고 표시하지 않는다. 정밀 성공 응답별 판정은 Locust request 원본에서 한다. API에서 받은 X-Request-Id와 시각으로 Loki를 추적하며, 프록시/Uvicorn 선제 503은 X-Request-Id가 없을 수 있어 시각·upstream·status로 대응한다.

## 11. 기록 형식·워밍업 제외·후처리

권장 run_id: `spacecube-<배포SHA>-<모드>-u<인원>-<KST시각>`. 시나리오 버전·계정/fixture 묶음 해시·VM 사양·전원 상태·설정값·발생기 위치·네트워크도 함께 기록한다. 계정 원본 해시를 남겨도 파일 내용/비밀번호를 공개하지 않는다.

```text
run_id/
  run.json                 # SHA·단계·환경·목표/실제 VU·측정 시작/종료·시나리오 버전
  locust_stats.csv         # API 이름별 누적
  locust_stats_history.csv # API별 시간 이력
  locust_failures.csv
  locust_exceptions.csv    # 설치 버전이 만드는 경우
  locust.html
  requests.csv            # 추가 구현 필요: 워밍업 제외 및 정상 응답별 정확한 백분위용
  transactions.csv        # 여정 시작/종료·신규/재시도/충돌/취소·fixture 고갈 건수
  resources.csv           # 시각·서버·CPU·메모리·연결·복제 지연·backend 상태
  logs/                   # 해당 시각의 마스킹된 Nginx·HAProxy·FastAPI 로그
  RESULTS.md              # 조건·표본 수·API별 결과·병목 근거·한계
```

requests.csv에는 응답 완료 UTC 시각, 요청 시작 시각, method, **정규화된 Locust name**, status, domain code, latency_ms, response_bytes, phase, 가명 여정 ID, 선택적인 X-Request-Id만 기록한다. 원문 URL query·본문·Authorization·email·password는 기록하지 않는다. 비동기 버퍼·기록 누락 카운터로 파일 쓰기가 발생기 병목이 되지 않게 한다. run_id/session_id/request_id를 새 Loki 고카디널리티 라벨로 만들지 않는다.

각 API p95는 **본 측정 구간에 시작하고 끝난 요청 원본**에서 계산하고, 경계에 걸친 요청 수를 별도 기록한다. 누적 CSV의 p95끼리 평균하거나 구간별 p95를 빼서 워밍업을 제거하면 안 된다. 지연된 요청을 종료 때 버리지 말고 drain 시간을 기록한다.

`--csv-full-history`로 엔드포인트별 이력을 저장하고 `--html`로 보고서를 남긴다. `--reset-stats`는 사용자 생성 완료 시점 초기화이며 목표 도달 뒤 추가 워밍업 60초를 자동으로 제거하지 않는다. 위 requests.csv 또는 정확한 시각의 수동/코드 초기화 설계가 필요하다. [Locust 공식 설정·CSV 설명](https://docs.locust.io/en/stable/configuration.html)

CLI는 자동화·재현성이 필요한 본 시험에 사용하고 웹 UI는 smoke/실시간 관찰에 쓸 수 있다. `-t`는 목표 도달 시점이 아닌 시험 시작부터 흐르므로 총 실행 시간은 램프업+600초로 잡는다. `--stop-timeout`의 유예 중 요청도 별도 phase로 기록한다. [Locust 공식 headless 실행 문서](https://docs.locust.io/en/stable/running-without-web-ui.html)

## 12. Claude 구현 인계와 실행 전 확인

현재 있는 자동화는 보존하고, 위 시험군을 별도 파일/명시적인 모드로 구현한다. 클래스 이름 예시를 지원한다고 가정해 기존 읽기 스크립트에 쓰기 명령을 보내면 안 된다.

- [ ] 서버 작업판의 Claude VM 작업이 완료/인계됐고, 변경/부하 잠금을 선점했다.
- [ ] 실제 정문 주소·/api prefix·배포 SHA·OpenAPI·모든 API 응답 코드/본문을 1명으로 확인했다.
- [ ] DB 두 대 연결·exporter 상태, 제외한 Mongo 상태, API 두 대 health·분배를 확인했다.
- [ ] 계정 독점·worker별 fixture 분리·잔여 자원·run 소유 데이터 목록을 확인했다.
- [ ] task/여정 모드, 가중치, 시간, 생각 시간, expected 오류 규칙을 run.json에 썼다.
- [ ] reset 시점·워밍업 제외 방식·requests.csv·정상 201/재시도 200 분리 통계를 구현했다.
- [ ] 1→5명 smoke에서 신규 예약·취소·후기·정보 변경이 실제로 발생하며 검증도 수행됐다.
- [ ] 409/401/400을 전부 성공 처리하지 않고 5xx·timeout은 원본에 남는다.
- [ ] 실행 중 변경할 설정은 없다. 변경이 필요하면 중단하고 다음 비교 run으로 넘긴다.

구현 제안: 공통 검증 함수 → 읽기 단일 task → 예약/후기 상태 머신 → expected 오류 처리 → 계정·fixture 분배 → 요청별 기록 → 측정 phase 제어 → CLI runner 순으로 만든다. 단일 endpoint와 사용자 여정의 name/태그를 구분해 같은 결과표에 섞이지 않게 한다.

이번 문서 작업에서는 실제 계정 생성·DB 쓰기·부하 실행·VM 재구성·원격 서비스 변경을 수행하지 않았다. VM 작업 담당자가 이 문서와 공용 작업판을 읽고 실행 범위를 예약한 뒤 이어서 구현한다.


## 12. 11-07 실제 실행 범위·설계와의 차이

- 7대 실행, MariaDB exporter 2대 포함 Prometheus 19/19 UP을 확인했다. [현재 IP·사양·권한·계측](DB_운영_모니터링_현황_2026-11-07.md) 참고.
- 이번 탐색은 공개 읽기·예약 쓰기 각각 5→20→50명이다. 이후 인증 조회/후기/회원정보/이벤트는 5명, 혼합 50명은 60초 워밍업+540초 본 측정으로 분리한다. 100/200/400명은 이번 실행 범위가 아니다.
- 1명 smoke는 워밍업 5초·측정 15초·회복 15초, 탐색은 워밍업 10초·측정 60초·회복 30초, 보조 5명은 5초·30초·회복 30초다. 원래 장기 탐색 제안의 2분 간격과 다르며 짧은 구간으로 최대 용량을 단정하지 않는다.
- C01 다른 계정 50개 / C02 같은 계정 재시도 50건을 명시 실행한다. C03~C06 전체를 수행했다고 보고하지 않는다. 인증 가입/비밀번호/탈퇴는 일회용 5계정 smoke다.
- CPU/메모리/디스크는 Prometheus 약 15초, Mongo 포함 7대 SSH 표본은 약 30초 간격이다. 짧은 CPU 피크는 놓칠 수 있다. 앱별 연결/상태 체류/잠금 대기를 구분하며 SQL 본문은 기록하지 않는다.
- 목표 VU 도달 뒤 워밍업을 제외하고 요청 시작·종료가 모두 측정 구간 안에 있는 원본으로 p95/p99를 계산한다. 첫 실패 run도 삭제하지 않고 보존한다. 계정/예약/후기 준비와 인증 시작 비용은 본 측정과 구분한다.
