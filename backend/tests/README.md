# tests — pytest (담당: A·B 각자)

자기가 만든 라우터 파일과 같은 이름으로 테스트를 둡니다. 파일별 확인 항목은 [백엔드_A 7절](../../docs/백엔드_A_회원_후기_이벤트.md), [백엔드_B 8절](../../docs/백엔드_B_공간_예약_결제_크롤링.md).

| 파일 | 담당 | 꼭 확인할 것 |
| --- | --- | --- |
| `test_auth.py` | A | 가입 입력·필수 동의·이메일 중복 409 `EMAIL_TAKEN`, 프론트 휴대폰 형식, 만 14세 제한, 로그인·로그아웃 204, Swagger Bearer 계약 |
| `test_users.py` | A | 내 정보 응답 필드·시간대, 조회 인증, 프로필 수정·잘못된 입력, 비밀번호 변경·현재 비밀번호 오류·길이 제한·bcrypt 저장, 취소 가능 예약 탈퇴 차단·개인정보 익명화·이메일 재가입 |
| `test_reviews.py` | A | 후기 자격 404·403·403·409, 작성 직후 내 후기에 보임 |
| `test_events.py` | A | 51건 400, MongoDB가 꺼져도 202이고 `events.log`에는 남음, replay해도 중복 없음 |
| `test_models_match_db.py` | A | `app/models`의 표·컬럼 이름·NULL 여부가 `spacecube_test`의 실제 표와 같은지 (SQLAlchemy `inspect`) |
| `test_health.py`, `test_db_routing.py`, `test_metrics.py` | A | primary 끊김 503 / replica·MongoDB 끊김 200 degraded, replica 주소가 틀려도 공개 조회 성공 |
| `test_catalog.py`, `test_venues.py` | B | 기준정보 필터·캐시, 공간 검색·정렬·상세·이미지·NEW·시간 칸·예약 가능 날짜 |
| `test_reservations.py` | B | 예약·칸·모의결제 201, 10분 재시도 200, 409 소유권·대표 ID, 기간·시간·인원·수단 검증, 지난 시간 `completed`, 키 있는 가상 요청, F-34 취소 권한·시간 경계·환불·칸 반납·재예약·실패 롤백·활성/비활성 공간 5개 유형의 취소 이벤트 category |
| `test_concurrency.py` | B | **다른 회원 50명이 같은 칸을 동시 요청 → 201 1건·409 49건**, 한 회원의 같은 요청 50건은 201 1건·200 49건, 겹치는 시간 경쟁, F-34 동시 취소 200 1건·409 1건. DB 행 수·이벤트·카운터 확인 |
| `test_jobs.py` | B | F-35 종료 정각·날짜 경계·멱등·칸/결제 보존·실패 롤백·두 배치 중복 실행·취소 경합·CLI 로그/종료 코드 |
| `test_internal.py`, `test_read_routing.py` | B | upsert 201·200·400, 공개 조회만 `get_db_read` |

## F-35 이용 완료 배치

`test_jobs.py`는 고정 한국 시각과 로컬 MariaDB `spacecube_test`로 `confirmed` 예약의 조건부 일괄 완료를 검증합니다. 종료 시각 직전·정각, 과거 날짜·미래 예약, 이미 취소/완료된 상태, 반복 실행, 완료 뒤 시간 칸·결제 보존, 커밋 실패 롤백을 확인합니다. 별도 MariaDB 세션 두 개를 동시에 실행하고 F-34 취소가 먼저 잠근 예약을 배치가 완료 상태로 되살리지 않는지도 확인합니다.

`CHECK_DB_URL`은 기존 DDL·seed가 적용된 로컬 `spacecube_test`로 지정합니다. 일반 테스트 데이터는 외부 트랜잭션에서 롤백합니다. 동시성 테스트는 커밋이 필요한 합성 데이터를 만들고 종료 때 삭제하며, 실행 전에 이미 있던 종료 대상 예약은 원래 `confirmed` 상태로 복구합니다.

```powershell
python -m pytest backend/tests/test_jobs.py -q -p no:cacheprovider
```

완료 배치는 HTTP API가 아니므로 Postman HTTP 요청은 추가하지 않습니다. CLI의 성공 로그·실패 로그·종료 코드는 `main()` 단위 테스트에서 확인하고, 실제 배포 실행은 api1 한 대에 시간별 cron으로 등록합니다.

## F-51 후기 목록용 B 조회 계약 (#43)

`test_reservation_dependencies.py`는 `reservation_repo.review_context_query(*, active_only=True)`의 반환 열(`reservation_id`·`venue_id`·`venue_name`·`category`), 예약당 한 행, 유형 5개의 영문 코드, 기본·명시적 활성 공간 필터와 `active_only=False`의 비활성 공간 포함을 검증합니다. A가 서브쿼리에 공간·유형 필터, 전체 개수, 정렬·페이지를 결합할 수 있고 호출자의 트랜잭션을 종료하지 않는지도 확인합니다.

테스트는 기존 `connection`·`sample` fixture를 사용해 로컬 MariaDB `spacecube_test`에만 가상 데이터를 넣고 종료 시 롤백합니다. `CHECK_DB_URL`에 기존 0001·seed가 적용된 로컬 DB를 지정하고 conda `pro_1`에서 `python -m pytest backend/tests/test_reservation_dependencies.py -q`로 기존 테스트까지 전부 실행합니다. A의 직접 import 연결·공개 후기 숨김·내 후기 유지에 대한 HTTP 통합 검증은 A 후속 작업입니다.

## F-12 검색·F-13 정렬·F-14 NEW 목록

`test_venues.py`는 실제 MariaDB `spacecube_test`와 연결한 `GET /venues` 검색 API 테스트를 포함합니다.

- 공간명·시도·시군구·시설명 검색, 유형·지역·인원·복수 시설(모두 보유) 필터 조합을 확인합니다.
- 날짜·시작 시각·이용 시간의 빈 칸 조건과 공간별 최소 이용시간, `now=true`의 오늘 기준 동작, 점유 칸 변경 후 재검색을 확인합니다.
- 기본·낮은 가격·평점·인기 정렬, 검색 필터 적용 후 전체 `total`, 페이지 중복 없는 분할을 확인합니다.
- 인기순은 최근 7일 범위에서 취소·예약일이 생성일보다 이른 예약을 제외합니다. 잘못된 값은 기존 400 오류 형식을 반환합니다.
- 페이지별 시설·이미지·점유 시간 조회가 공간 수에 따라 늘지 않고 5회 SELECT로 끝나는지 검사합니다.
- `GET /venues/new`는 활성 공간만 조회하고 오늘·13일 전 경계 포함, 14일 전·미래·비활성 제외, 최신순 동률, 페이지 분할과 `total`을 확인합니다.
- NEW 항목의 `registered_on`, `new_days_left = 14 - 경과일`, 공통 목록 응답 계약과 묶음 조회 5회도 검사합니다.

가상 공간·예약·후기는 테스트 트랜잭션 안에서 만들고 종료 시 롤백합니다. Chrome HTTP 시험도 검색 항목 계약·정렬 값·입력 오류를 확인합니다.

- 테스트 DB는 로컬 MariaDB(`infra/local`)의 `spacecube_test`. SQLite는 제약 동작이 달라 쓰지 않습니다.
- 동시성 테스트는 스레드 50개로 요청을 한꺼번에 보냅니다.

## F-20 상세·F-21 예약 가능 날짜·F-22 시간 칸 API·F-14 날짜 정책

`test_venues.py`는 실제 A 앱의 `GET /venues/{venue_id}`, `GET /venues/{venue_id}/available-dates`, `GET /venues/{venue_id}/slots?date=YYYY-MM-DD`를 로컬 MariaDB와 연결해 호출합니다.
`CHECK_DB_URL`에 기존 DDL·seed가 적용된 로컬 `spacecube_test` 접속 정보를 지정해야 합니다.
이미지·NEW 경계 단위 테스트, 가상 공간 DB 연결, F-14 목록 HTTP 테스트, 상세 HTTP 응답·라우터 등록과 F-22·F-21 테스트를 검증합니다.

- 인증 없이 상세 계약 전체를 반환하며, 내부 출처·등록 시각을 노출하지 않습니다.
- 이미지 누락 시 대표·갤러리 모두 `art:group-0`; 실제 이미지는 정렬 순서와 대표 그림을 유지합니다.
- 시설 ID·이름, 최소 이용시간·설명·안내, 평점 뷰의 평균·건수를 실제 DB 값으로 확인합니다.
- 후기 없는 공간은 평점·후기 수 0이며 삭제된 후기는 뷰 집계에서 빠집니다.
- NEW는 한국 날짜 기준 오늘·13일 전을 포함하고 14일 전·미래 날짜를 제외합니다.
- NEW 목록은 최신 등록순으로 페이지 처리하고 등록 날짜·남은 일수를 반환하며, 빈 이미지는 검색·상세와 같이 `art:group-0`을 씁니다.
- 오늘 시간 칸은 영업시간 안에서 점유·지난 시간 표시를 반환합니다. 다른 날짜의 점유 칸은 제외합니다.
- 없는 공간·비활성 공간은 동일한 404 `VENUE_NOT_FOUND`, 잘못된 ID는 400 `VALIDATION`입니다.
- 동기 라우터와 `get_db_read()` 의존성을 검사하고 재조회 시 DB 변경이 반영되는지 확인합니다.
- F-22의 오늘 응답은 F-20과 같으며 과거·미래 날짜도 영업시간 칸을 모두 반환합니다. 종료 시각은 제외하고 최소시간으로 칸을 줄이지 않습니다.
- 날짜별·공간별 점유 분리, 완료 예약 점유 유지, 재조회 시 새 점유 반영, 한국 시각 자정·영업 시작·종료 후 `past` 경계를 검사합니다.
- 날짜 필수·엄격한 `YYYY-MM-DD` 형식·실제 달력 날짜·ID 오류는 공통 400, 없는 공간·비활성은 동일한 404를 확인합니다.
- 기본 ±365일과 변경된 과거·미래 범위, 0일 설정의 양끝 포함·범위 밖 400 `OUT_OF_RANGE` 및 정확한 `detail`을 검사합니다.
- F-21은 기본 14일·최대 31일, 음수 offset·지난 빈 칸, 설정 범위 양끝·0일 설정·마지막 페이지 잘림을 확인합니다. 응답 `days`는 요청값을 유지합니다.
- 빈 칸 총수와 연속 길이를 구분해 최소 1~4시간 판정, 분산된 빈 칸·완전 점유·끝까지 이어진 빈 칸·영업시간 밖 점유 제외를 검사합니다. 예약 불가능한 날도 반환합니다.
- 공간·날짜별 점유 분리, 완료 예약의 점유 유지, F-22 빈 칸 수와 일치, 점유 추가·삭제·최소시간 변경 후 재조회 반영을 확인합니다.
- 매우 큰 offset도 500 대신 400이며, 31일 조회도 공간·점유 SELECT가 총 2회이고 이미지·평점 조회가 없음을 실제 SQL로 확인합니다.

가상 공간·회원·예약은 테스트 트랜잭션 안에서만 만들고 출처 synthetic 또는 `is_synthetic`으로 표시합니다.
TestClient는 lifespan을 시작하지 않으며 공개 DB 의존성을 테스트 연결로 교체합니다. 종료 시 전체 변경을
롤백하고 가상 공간이 남지 않는지 확인합니다. DDL·운영 DB·실제 replica 장애 전환은 검사하지 않습니다.

```bash
python -m pytest backend/tests/test_venues.py -q
```

F-12·13 검색 검증 8건 추가 뒤 `test_venues.py`는 122건이었고, F-14 조회 검증 4건을 더해 **126건 통과**했습니다.
`verify.ps1` 전체도 통과했습니다: pytest **165건**, 프론트 단위 **54건**, Ruff 린트·포맷,
프론트 린트·색 검사·빌드. Starlette TestClient 사용 중단 예정 경고 1건이며 실패는 없습니다.

기존 검증은 A 로컬 전달본을 사용했습니다. 이번 #31 통합에서는 develop의 공식 A 앱을 사용하며 `main.py`에 `catalog`·`venues` 라우터를 등록했습니다.

```python
from app.routers import catalog, venues

app.include_router(catalog.router, tags=["catalog"])
app.include_router(venues.router, prefix="/venues", tags=["venues"])
```

F-21·22는 기존 venues 라우터에 포함되어 추가 main.py 변경이 없습니다. 공간별 후기 목록은 A API로 별도 연결하며, 실제 프론트 화면 전체 흐름은 이후 검증합니다.

## F-12·13·20~22 추가 검증: 브라우저·읽기 연결 대체

`test_read_routing.py`는 A의 `get_db_read()`를 대체하지 않고 실제 MariaDB 연결을 사용합니다.
시험용 설정·연결 풀은 테스트 프로세스에서만 분리하고, 읽기 주소 미설정·동일 DB의 정상 읽기 연결·수신하지
않는 loopback 포트의 연결 실패를 확인합니다. 세 경우 모두 실제 유형 조회가 200으로 성공하며, 연결 실패
때만 `db_read_fallback_total`이 1 증가해야 합니다. DB 서버를 중지하거나 설정·데이터를 변경하지 않습니다.
실제 복제 DB의 장애·복제 지연을 시험한 것은 아닙니다.

```bash
python -m pytest backend/tests/test_read_routing.py -q
```

`check_venue_browser.py`·`.mjs`는 별도 실행하는 B 검증기입니다. 기본 pytest 수집에는 들어가지 않으며,
가상 공간이 있는 트랜잭션에 실제 앱을 연결해 임시 Uvicorn을 띄우고 Chrome으로 F-12·13 검색 항목 계약·정렬 값·
F-14 NEW 목록의 등록 날짜·남은 일수와 입력 오류, 상세 200·JSON 계약·본문과
없는 공간 404를 확인합니다. F-22는 오늘 칸과 상세 응답 일치·미래 날짜 200, 날짜 누락·형식·달력 오류와
범위 밖 400, 없는 공간 404를 확인합니다. F-21은 기본 날짜 목록·F-22 빈 칸 수 일치·지난 날짜·마지막 페이지
잘림 200, 입력·범위 400, 없는 공간 404를 확인합니다. 테스트가 끝나면 Chrome·임시 API 서버를 종료하고 공간을 롤백합니다.
Node와 frontend의 기존 Playwright 패키지가 필요합니다. DB 접속 정보는 Node·Chrome에 전달하지 않습니다.

```powershell
$env:PLAYWRIGHT_CHANNEL = 'chrome'
python -m pytest backend/tests/check_venue_browser.py -q -s -p no:cacheprovider
```

별도로 기존 프론트 E2E도 같은 Chrome에서 실행했습니다. 프론트 소스·설정은 바꾸지 않았으며 이 시험은
목업 데이터 기반의 화면·접근성·가입·예약 흐름 검증입니다. 실제 F-20과 상세 페이지 전체를 연결한 시험과
구분합니다. F-20·21·22·A 후기 목록까지 실제로 연결한 화면 흐름은 여전히 별도 통합 항목입니다.

11-05 F-14 추가 후 F-12·13·14·20·21·22 별도 Chrome **1건 통과**, Starlette 사용 중단 예정 경고 1건입니다.
기존 F-20 단계의 읽기 경로 **3건 통과**, 목업 화면 E2E **59건 통과·7건 기기 조건 건너뜀** 기록은 유지합니다.
이번 F-21 작업에서 목업 화면 E2E는 재실행하지 않았습니다(프론트 변경 없음).

## F-10·11: 유형·지역·시설 조회

`test_catalog.py`는 실제 A 앱과 로컬 MariaDB에서 공개 목록 응답과 읽기 의존성을 검사합니다.
`CHECK_DB_URL`에 기존 DDL·seed가 적용된 로컬 `spacecube_test` 접속 정보를 지정하고 실행합니다.

```bash
python -m pytest backend/tests/test_catalog.py -q
```

- 유형은 기존 5개 목록과 실제 DB 이름, 5분 캐시 만료·DB 오류 처리를 확인합니다.
- 지역은 활성 공간이 있는 곳만 반환하며 시·도 중복, 타 시·도 혼입, 비활성·공간 없는 지역을 제외합니다.
- 시·도 목록과 시·군·구 조회가 활성 지역 스냅샷 하나를 공유하고 만료 후 DB 변경을 반영하는지 검사합니다.
- 시설은 공간 연결 여부와 관계없이 전체 목록을 실제 ID 순서로 반환하고 5분 뒤 이름 변경을 반영합니다.
- 빈 목록도 캐시하며 DB 오류는 캐시하지 않습니다. 시·도는 DB 컬럼 길이인 20자 이내인지 검증합니다.
- 임시 지역·공간 추가와 이름·상태 변경은 외부 트랜잭션에서 롤백합니다. DDL·기존 데이터 삭제는 없습니다.

캐시는 프로세스마다 독립적입니다. 새 공간 등록·비활성화 후 공개 지역 목록에는 최대 5분의 캐시 지연과
별도의 replica 복제 지연이 있을 수 있습니다. 실제 replica 장애 대체·서버 간 동작은 이 테스트 범위 밖입니다.

11-05 로컬 MariaDB에서 **19건 통과**했습니다.

## F-50 지원: 예약 소유권·A 후기 작성 연결

### #4 후기 작성·목록 검증

`test_reviews.py`는 작성 자격 판정과 commit·rollback을 단위 테스트합니다.
`test_review_lists.py`는 실제 앱 라우터와 로컬 MariaDB에서 후기 목록·수정·삭제,
필터·정렬·페이지, 탈퇴 회원 표기와 비활성 공간 공개/내 후기 구분을 검증합니다.
목록 테스트는 인증 의존성을 테스트 회원으로 교체하며 실제 로그인은 검사하지 않습니다.
DB에 삽입한 행은 외부 트랜잭션을 롤백합니다.

저장소 루트에서 기존 `pro_1` 환경과 로컬 테스트 DB를 준비한 후 실행합니다.
아래 명령은 이 PC의 활성 로컬 DB 설정을 현재 PowerShell에만 불러옵니다.

```powershell
cd C:\mlo-03-p1-team4
$pythonExe = "$env:USERPROFILE\miniforge3\envs\pro_1\python.exe"
$activeDirectory = (Get-Content "$env:LOCALAPPDATA\SpacecubeTestMariaDBActive.txt" -Raw).Trim()
$entry = Get-Content (Join-Path $activeDirectory '.env') | Where-Object { $_ -match '^CHECK_DB_URL=' } | Select-Object -First 1
if (-not $entry) { throw '활성 로컬 테스트 DB의 CHECK_DB_URL을 찾지 못했습니다.' }
$env:CHECK_DB_URL = $entry.Substring('CHECK_DB_URL='.Length).Trim().Trim('"', "'")
& $pythonExe -m pytest backend/tests/test_reviews.py backend/tests/test_review_lists.py backend/tests/test_reservation_dependencies.py -q
```

2026-11-05 로컬 MariaDB에서 위 세 파일 **57건 통과**(Starlette 사용 중단 예정 경고 1건).
B 후기 목록 조회 계약만 골라 실행한 **14건도 통과**했습니다.
실제 HTTP에서 가입·로그인·예약·후기 작성·내 후기·공개 후기 목록을 확인하고,
Swagger에서 후기 목록과 공간 별점 정렬의 200 응답을 확인했습니다.
이후 로컬 `spacecube_test`를 0001 마이그레이션·seed로 초기화했습니다.
DB 제약 검증(`db/tests/check_ddl.py`)과 실제 HTTP의 가입→예약→후기 작성·수정·삭제를 통과했고,
최종 시연 공간 3개만 남긴 상태에서 전체 `backend/tests` **317건 통과**했습니다.
세 공간의 등록 시각은 30일 전으로 두어 `GET /venues/new`의 격리된 개수 검증에 영향을 주지 않습니다.
기본 pytest 임시 폴더에 접근할 수 없는 PC는 위 명령에 다음 옵션을 추가할 수 있습니다.

```powershell
$testTemp = Join-Path $env:TEMP ('spacecube-review-' + [guid]::NewGuid().ToString('N'))
& $pythonExe -m pytest backend/tests -q --basetemp $testTemp
```

### Swagger에서 직접 확인

위 테스트 DB 설정을 불러온 **같은 터미널**에서 서버의 읽기·쓰기 DB도 로컬 테스트 DB로 지정합니다.
임시 JWT 키를 생성하므로 서버를 다시 시작하면 이전 토큰은 사용할 수 없습니다.

```powershell
$env:DB_WRITE_URL = $env:CHECK_DB_URL
$env:DB_READ_URL = $env:CHECK_DB_URL
$env:MONGO_URL = 'mongodb://127.0.0.1:1'
$env:JWT_SECRET = & $pythonExe -c "import secrets; print(secrets.token_urlsafe(48))"
cd C:\mlo-03-p1-team4\backend
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

1. 브라우저에서 `http://127.0.0.1:8001/docs`를 엽니다. `/auth/signup`에서 테스트 회원을 만들고 `/auth/login`으로 로그인합니다.
2. 로그인 응답의 `access_token`만 복사해 **Authorize**에 넣습니다(`Bearer`는 붙이지 않음). 기존 회원이라면 원래 평문 비밀번호를 사용합니다.
3. `GET /venues`와 공간 상세에서 활성 공간의 ID·영업시간·최소 이용시간·최대 인원을 확인합니다. 테스트 DB에 공간이 없으면 먼저 테스트 공간을 준비해야 합니다.
4. `POST /reservations`에 그 공간과 어제 날짜를 넣습니다. 예시: `{"venue_id": 1, "date": "2026-11-04", "start_hour": 10, "hours": 1, "headcount": 1, "method": "card"}`. ID·날짜·시간·시간 수는 확인한 공간과 실제 날짜에 맞게 바꿉니다. 결제는 모의 결제입니다. 빈 칸이 아니면 다른 시간이나 공간을 선택합니다. 응답에서 `status=completed`와 `reservation_id`를 확인합니다.
5. `POST /reservations/{reservation_id}/review`에 `{"rating": 5, "content": "테스트 후기입니다."}`를 보내 201과 `review_id`를 확인합니다. 다시 보내면 409 `REVIEW_EXISTS`가 나와야 합니다.
6. `GET /users/me/reviews`, `GET /venues/{venue_id}/reviews`, `GET /reviews`에서 후기와 마스킹된 작성자 이름을 확인합니다. `category`, `sort`, `page`, `size`도 바꿔 봅니다.
7. 다른 회원 예약은 404 `RESERVATION_NOT_FOUND`, 완료되지 않은 예약은 403 `NOT_COMPLETED`, 작성 기한이 지난 예약은 403 `REVIEW_PERIOD_OVER`입니다. 테스트 데이터의 예약 생성일도 기한 계산에 쓰입니다.

수동 Swagger 요청으로 만든 회원·예약·후기는 DB에 남습니다. 자동 테스트의 롤백 데이터와 구분해 로컬 테스트 DB에서만 진행합니다. 서버는 실행한 터미널에서 `Ctrl+C`로 종료합니다.

`test_reservation_dependencies.py`는 이전 프로젝트에서 가져온 B 코드의 검증 테스트입니다.
예약·칸·결제 및 공간·시설 연결·이미지 모델의 컬럼·타입·기본값·키·인덱스·CHECK·외래키를 현재
`db/migrations/0001_init.sql`과 대조하고, A 모델과 함께 매퍼가 구성되는지 확인합니다.
실제 MariaDB에서는 예약 상태 3개의 본인·타인·없는 예약 조회와 A 후기 작성 API의
성공·타인 예약·미완료·기한 초과·중복·7일 경계·과거 이용일의 최근 예약을 검증합니다.

- A의 실제 `app.main`·공통 모듈·후기 코드가 필요합니다. 인증 의존성만 테스트 사용자로 바꿉니다.
- `CHECK_DB_URL`에 `mysql+pymysql` 형식의 로컬 `spacecube_test` 접속 정보를 지정해야 합니다.
- 테스트 DB에는 기존 `0001_init.sql`과 `seed.sql`이 적용돼 있어야 합니다. 테스트가 DDL을 자동 실행하지 않습니다.
- 테스트 행은 외부 트랜잭션에서 롤백하고, A 서비스의 commit은 SAVEPOINT로 격리합니다.
- 로그인·후기 목록·예약 생성 API·동시 예약은 이 테스트의 검증 범위가 아닙니다.

`test_reviews.py`는 MariaDB 없이 후기 서비스의 자격 판정 순서, 7일 경계, 성공 commit,
실패 rollback, UNIQUE 경합의 `REVIEW_EXISTS`, 탈퇴 회원 작성자 표기를 검사합니다.
실제 MariaDB의 `get_owned` 연결과 후기 작성 API는 위 테스트에서 검증합니다.

```bash
python -m pytest backend/tests/test_reviews.py -q
```

저장소 루트의 `pro_1` 환경에서 실행합니다.

```bash
python -m pytest backend/tests/test_reservation_dependencies.py -q
```

11-05 현재 프로젝트의 `localhost:3306/spacecube_test`에서 **17건 통과**했습니다(기존 예약 의존성 14건 + 공간 모델 3건).
F-12·13까지 추가한 전체 pytest는 **161건 통과**, Starlette TestClient 사용 중단 예정
경고 1건입니다. 비밀번호는 테스트 프로세스에만 전달했고 파일이나 영구 환경변수에 저장하지 않았습니다.
- `test_core_contracts.py`, `test_core_events.py`, `test_auth.py`, `test_users.py`는 공통 계약·이벤트·회원 흐름 확인용입니다. 회원 테스트는 로컬 `spacecube_test`의 `CHECK_DB_URL`이 필요합니다.
- 프로젝트 어디서 실행해도 테스트 파일 위치를 기준으로 경로를 잡는 PowerShell 실행 파일은 `run_auth_tests.ps1`입니다. 로컬 사용자 설정에서 `CHECK_DB_URL`을 찾고, 못 찾으면 현재 PowerShell 세션의 `CHECK_DB_URL`을 사용합니다.
- 확인 명령: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\run_auth_tests.ps1` (backend 폴더에서 실행). 회원 테스트는 MariaDB 트랜잭션 롤백으로 테스트 데이터를 보존하지 않습니다.

## #31 A 공통 코드 통합·F-04 탈퇴 지원

develop(c007470)의 공식 A 코드와 B 조회를 통합하고 main.py에 catalog·venues를 등록했습니다.
test_reservation_dependencies.py는 count_cancellable의 시작 직전·정각·직후, 날짜 경계,
confirmed·completed·cancelled, 타인 예약·0건·복수 예약 수와 호출자 트랜잭션 유지를 12건 추가 검증합니다.
함수는 primary 세션을 전달받으며 커밋하지 않습니다. A의 탈퇴 서비스는 같은 세션에서 이 함수를 호출해 양수면 409 `HAS_UPCOMING_RESERVATION` + `detail.count`, 0이면 개인정보 익명화를 커밋합니다.

11-05 로컬 MariaDB spacecube_test에서 전체 pytest **230건 통과**, Starlette TestClient 경고 1건입니다.
Ruff 린트·포맷과 프론트 verify(단위 **54건**, 린트·색 검사·빌드)도 통과했습니다.
프론트 기존 e2e/account.spec.js의 조건문 린트 경고 1건은 남아 있습니다.
pro_1은 Miniforge 경로의 실행기를 사용했고, DB 접속 정보는 테스트 프로세스에만 전달했습니다.
예약 생성·Postman 산출물은 별도 예약 브랜치에 보존했으며, 이번 브랜치에는 포함하지 않습니다.


## F-30~32 공식 앱·공통 키·실제 HTTP 통합 검증

현재 예약 브랜치는 develop(eae5068)의 공식 A 코드를 통합하고 main.py에
reservations 라우터를 등록했습니다. test_reservations.py 16건은 별도 간이 앱 대신
공식 create_app()을 사용하며 OpenAPI·인증 차단·공통 가상 키 미설정/오류/정상 처리까지 확인합니다.
동시성 3건은 서로 다른 회원 50명, 같은 회원 재시도 50건, 겹친 이용 시간 경쟁을 검증합니다.

11-05 MariaDB **11.4.13 spacecube_test에서 전체 pytest 236건 통과**했습니다.
Ruff 린트·포맷, 프론트 단위 54건·린트·색 검사·빌드도 통과했습니다.
기존 Starlette TestClient 경고 1건과 프론트 E2E 조건문 린트 경고 1건이 있습니다.
검증 구성요소를 Miniforge pro_1과 설치된 Node 실행기를 지정해 각각 실행했습니다.

check_reservation_http.py는 pytest 기본 수집에서 제외된 별도 실행 검증기입니다.
CHECK_DB_URL에 기존 DDL·seed가 있는 로컬 spacecube_test 접속 정보를 지정하고 실행합니다.

    python backend/tests/check_reservation_http.py

공식 앱을 임시 포트에 띄우고 가상 회원가입·실제 로그인 후 Postman 컬렉션 5개 요청을 실행합니다.
**5개 요청·11개 검증 통과**: OpenAPI 200·F-34 경로, 무인증 401, 생성 201, 재시도 200, 취소 200.
DB 취소 예약 1건·해제된 칸·환불 결제, 가상 표시와 예약·취소 카운터를 확인합니다.
임시 `events.log`에서 `reserve_cancel_ok`가 정확히 한 번 기록되고 공간 ID·유형 코드·예약 ID·가상 표시가 맞는지도 확인합니다.
종료 시 서버·임시 비밀 환경과 생성한 ID의 회원·공간·예약을 정리합니다.
Postman CLI와 Node가 필요하며 컬렉션 5개 요청 파일 lint도 오류·경고 0건입니다.
프론트 화면 전체의 실제 예약 API 연결과 실제 replica 장애·복제 지연 시험은 포함하지 않습니다.

## PR #39: 취소·환불 예약의 재시도 성공 제외

`test_reservations.py`는 취소·환불 후 같은 칸을 재예약한 요청을 다시 보내면 새 예약 ID로
200을 반환하고, 다른 회원이 선점했으면 예약 ID를 노출하지 않는 409를 반환하는지 확인합니다.
예약 상태가 confirmed/completed여도 결제가 refunded이면 재시도 성공에서 제외하며,
confirmed/completed + paid인 기존 예약의 재시도 200은 유지합니다.
이 테스트는 예약 재시도 뒤 취소 API로 칸을 반납하고 새 예약 ID가 발급되는 흐름도 확인합니다.

## F-34 예약 취소·모의 환불

`test_reservations.py`는 시작 정각·지난 이용·완료 예약 취소 차단, 타인·없는 예약 숨김,
이미 취소된 예약의 재요청, 상태·결제·슬롯의 원자적 변경과 환불 저장 실패 롤백을 확인합니다.
취소 성공 후 해제한 칸 재예약과 취소 이벤트·카운터 단 1회 증가도 확인합니다.
`test_concurrency.py`는 독립 MariaDB 연결 두 개가 한 예약을 동시에 취소할 때 한 건만 커밋하는지 봅니다.

실제 Postman 확인기는 생성·재시도·취소 요청 뒤 예약 `cancelled`, 결제 `refunded`, 칸 해제,
취소 카운터를 MariaDB에서 확인하고 임시 합성 데이터를 정리합니다.

11-05 설치된 MariaDB 11.4.13으로 별도 loopback 임시 인스턴스를 띄우고 기존 0001·seed를 적용했습니다.
수정 전 회귀 사례 4건의 실패를 확인한 뒤, 수정 후 전체 pytest **241건 통과**
(예약 API 21건·기존 동시성 3건 포함), 기존 Starlette TestClient 경고 1건입니다.
Ruff 린트·포맷 확인과 실제 HTTP Postman **4요청·8검증**도 통과했습니다.

## F-61: 내부 공간 등록·갱신

`test_internal.py`는 공식 앱의 `POST /internal/venues`를 실제 MariaDB로 검증합니다.
키 없음·오류·미설정은 DB 접근 전에 401로 거절하며, 공개 읽기 세션으로 쓰지 않는지 확인합니다.
출처 3종의 신규 201·동일 재전송/갱신 200, 같은 ID와 최상위 응답, 시설 무시·중복 제거,
시설/그림 교체·비우기와 순서, 원래 등록 시각 보존, 입력 범위·미등록 지역/유형을 확인합니다.
신규·갱신 저장 실패 뒤에는 전체가 롤백되고, 별도 연결 8개의 같은 출처 요청에서는
201 1건·200 7건·공간 1개와 마지막 요청의 온전한 시설·그림 목록을 검증합니다.
일반 테스트는 외부 트랜잭션으로 롤백하고 경쟁 테스트는 생성한 고유 synthetic 출처만 지웁니다.

기존 DDL·seed가 있는 로컬 MariaDB `spacecube_test`를 `CHECK_DB_URL`로 지정한 뒤 pro_1에서 실행합니다.

```powershell
python -m pytest backend/tests/test_internal.py -q
python backend/tests/check_internal_http.py
```

`check_internal_http.py`는 임시 공식 Uvicorn 서버와 내부 키를 준비하고
`postman/collections/Internal venues API`의 6개 요청을 실행합니다.
OpenAPI 200·키 없음 401·신규 201·재전송 200·갱신 200·잘못된 출처 400과 DB 공간 1개·목록 교체를
확인한 뒤 임시 서버·키·환경·공간을 정리합니다. 내부 키가 비어 있는 공유 환경은 쓰기를 건너뜁니다.
CLI 컬렉션·환경 lint와 실제 응답 검증은 별도이며, api1 배포·방화벽·실제 크롤러 호출은 후속 확인입니다.

11-05 MariaDB 11.4.13 임시 loopback 인스턴스에서 F-61 **35건**을 포함한 전체 pytest **276건 통과**,
실제 HTTP Postman **6요청·12검증 통과**했습니다. 새 컬렉션 6파일·공유 환경 lint 오류/경고는 0건이고,
Ruff 린트·포맷 및 프론트 verify(단위 55건·린트·빌드)도 통과했습니다.
기존 Starlette TestClient 경고와 프론트 조건문 린트 경고가 각 1건 있습니다.
