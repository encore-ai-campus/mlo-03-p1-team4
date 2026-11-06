# STRUCTURE.md — 폴더 지도와 개발 큰 틀

2026-11-03 기준. 사람과 AI 에이전트가 **어디에 무엇을 만들고, 무엇을 기준으로 삼는지** 한 번에 보는 지도입니다. 진행 상태는 `STATE.md`, 작업 규칙은 `AGENTS.md`에 있습니다. 폴더를 새로 만들면 이 트리에도 한 줄 더합니다.

## 1. 읽는 순서

| 누구 | 순서 |
| --- | --- |
| 처음 받은 사람 | `README.md` → 이 파일 → `STATE.md` → 내 파트 기준 문서 |
| AI 에이전트 | `AGENTS.md` → `STATE.md` → 이 파일 3절(내 파트 표) → 작업 폴더의 `AGENTS.md`·`README.md` → 기준 문서의 해당 절만 |

`docs/지난설계/`와 `docs/기록/`은 이력입니다. 구현할 때 여기서 표·API·상태값을 가져오지 않습니다.

## 2. 폴더 트리

`[A]` `[B]` `[DB]` `[FE]` `[공동]`은 담당, **(예정)**은 아직 없는 파일입니다. 예정 파일 이름은 기준 문서에 적힌 그대로 만듭니다.

```
Pro_1/
├─ AGENTS.md                  [공동] AI 작업 지침 (Codex·Claude Code 공용)
├─ CONTRIBUTING.md            [공동] GitHub 규칙: 이슈·브랜치·커밋·PR·리뷰·라벨 (11-04)
├─ .github/                   [공동] PR·이슈 템플릿, CODEOWNERS(폴더별 리뷰어), CI(Ruff·프론트 verify·E2E·DB·pytest, CONTRIBUTING 4-1절)
├─ README.md                  [공동] 소개, 처음 받았을 때 할 일
├─ STATE.md                   [공동] 진행 상태·결정 기록·열린 질문
├─ STRUCTURE.md               [공동] 이 파일
├─ environment.yml            [공동] conda 환경 pro_1 (Python 3.12)
├─ ruff.toml · verify.ps1     [공동] 파이썬 린트 규칙, 커밋 전 전체 검증
├─ pytest.ini                 [공동] pytest 공통 설정(테스트 폴더, backend import 경로)
├─ .gitignore                 [공동] .env·node_modules·글꼴 원본 등 제외
│
├─ docs/                      설계 문서 (docs/README.md)
│  ├─ 산출물_01_요구사항명세서.md        F-ID, 예약 규칙, NFR
│  ├─ 산출물_02_시스템아키텍처_흐름도.md  구성, primary/replica 경로, 네트워크, 포트
│  ├─ 산출물_03_서비스흐름도.md          화면 지도, 시퀀스
│  ├─ 산출물_04_DB명세서.md              표 12개·컬렉션 3개, 정규화, 로그·지표 데이터
│  ├─ 산출물_05_구현_운영_계획.md          [공동] AI 활용·서버·자동화·데이터 계획 (11-04)
│  ├─ 백엔드_A_회원_후기_이벤트.md       [A] 구현 명세
│  ├─ 백엔드_B_공간_예약_결제_크롤링.md  [B] 구현 명세
│  ├─ 오류코드.md                        [공동] 오류 코드 전체 (유일한 기준)
│  ├─ 인프라_트래픽_안정성_검토.md       [공동] 정문·용량·AWS 안정성·팀별 검토 (권장안)
│  ├─ 프론트_변경목록_11-03.md           [FE] 확정안에 맞춰 고칠 것
│  ├─ 공간대여_04_UI패턴_글꼴.md · 공간대여_05_프론트_현황.md · 공간대여_06_크롤링_사이트조사.md
│  ├─ 로컬_VM_구성.md                    [공동] 1차 배포: 노트북 4대 · VM 7대 배치·주소·방화벽 (11-05)
│  ├─ 데이터_수집_명세.md                [공동] 1차 수집원 2곳·부족분 생성·약관 검토, CCL 참고 사진 40장과 FE 연결
│  ├─ AWS_프리티어_구성.md               [공동] AWS C안(프리 티어, 11-04) — 참고안
│  ├─ AWS_네트워크_설계.md · MVP_시뮬레이션_크롤링_수치.md   (10-30 기준, 맨 위 안내 참고)
│  ├─ db/                     [DB] mongo_init.js (검증 끝). spacecube_mariadb.sql은 0001로 옮겼다는 안내만
│  ├─ figures/                [공동] 그림 PNG·SVG, src/ 원본, tools/ 렌더 스크립트
│  │  └─ screens/            [공동] README 시연 화면 캡처(목업, 11-04)
│  ├─ architecture/icons/     [공동] 아키텍처 아이콘, SOURCES.md
│  ├─ 기록/                   회의·리뷰·검토 기록 (이력)
│  └─ 지난설계/               10-30 설계, 맛집 주제 research/ (이력)
│
├─ frontend/                  [FE] Vue 3 + Vite (동작함, 11-01 설계 기준)
│  ├─ AGENTS.md · README.md · .env.example · package.json
│  ├─ src/
│  │  ├─ pages/               화면 7개 + PlaceholderPage, UiShowcasePage(/ui)
│  │  ├─ components/          layout · ui(reka-ui 래퍼) · domain(RoomArt 일러스트 등)
│  │  ├─ composables/         useAuth, useBooking, useEventLogger, useReveal
│  │  ├─ api/                 백엔드 호출 함수 + mock/ (→ venuesApi 등으로 바꿀 예정)
│  │  ├─ stores/ · router/ · utils/ · styles/(tokens.css·fonts.css·base.css)
│  │  └─ **/__tests__/        Vitest 단위 테스트
│  ├─ e2e/                    Playwright + axe
│  ├─ public/fonts/           웹용 글꼴 (Noto Sans KR 서브셋)
│  ├─ public/photos/          [FE] CCL 분위기 참고 사진 40장(유형별 8장), README·SOURCES·크레딧 페이지
│  │  └─ studyroom/ · studio/ · cafe/ · lectureroom/ · partyroom/ 1200×780 WebP
│  └─ scripts/check-colors.mjs  tokens.css 밖 색 코드 검사
│
├─ backend/                   [A·B] FastAPI 한 앱 (공식 A 통합, B F-10~14·20~22·30~32·61·get_owned·count_cancellable 구현)
│  ├─ AGENTS.md · README.md · .env.example
│  ├─ app/
│  │  ├─ main.py              [A] 공식 앱 통합, [B] catalog·venues·reservations·internal 라우터 등록
│  │  ├─ core/                [A] config, db, mongo, security, deps, errors, pagination, events, metrics, logging, clock, synthetic (공식 A 구현)
│  │  ├─ models/              [A] base, user, review / [B] catalog·reservation·venue 구현 — DDL 대응 모델
│  │  ├─ routers/             [A] auth, users, reviews, events, health / [B] catalog·venues(조회), reservations(F-30~35), internal(F-61) 구현
│  │  ├─ schemas/             라우터와 같은 이름 ([B] catalog·venues 조회, reservations 생성·취소, internal 등록/갱신 계약 구현)
│  │  ├─ services/            [A] auth_service, user_service, review_service / [B] catalog_service·venue_service 조회, reservation_service(F-30~35)·internal_service(F-61) 구현
│  │  ├─ repositories/        [A] user_repo, review_repo / [B] catalog_repo·reservation_repo(생성·재시도·get_owned·count_cancellable·후기 목록 review_context_query·F-35 완료 배치)·venue_repo·slot_repo·payment_repo 구현
│  │  └─ jobs/                [B] complete_reservations.py(F-35, api1 hourly cron)
│  ├─ scripts/                [A] replay_events (예정)
│  └─ tests/                  [B] test_catalog·test_reservation_dependencies·test_venues·test_reservations·test_concurrency·test_jobs·test_read_routing·test_internal 구현
│     └─ check_venue_browser.py·mjs  [B] 별도 실행: 임시 실제 API + Chrome 검색·정렬·NEW·오류·상세·날짜 목록·시간 칸 검증
│        check_reservation_http.py  [B] 별도 실행: 공식 앱·실제 인증·Postman 예약/재시도·DB 확인, 가상 데이터 정리
│        check_internal_http.py  [B] 별도 실행: 공식 앱·내부 키·Postman 등록/재전송/갱신·DB 확인, 가상 공간 정리
│        check_reservation_events_mongo.py [B] 선택적 CHECK_MONGO_URL: 실제 예약 결과 3종·중복 재적재·문맥 null 정책 확인, 가상 이벤트 ID 정리
│
├─ postman/                   [B] Git-native v3 예약·내부 공간 등록 컬렉션·로컬 환경 (CLI 테스트)
│  ├─ README.md               안전한 실행 방법과 F-30·61 쓰기 요청 안내
│  ├─ collections/            OpenAPI·인증·예약 생성 및 내부 공간 등록 검증
│  │  └─ Internal venues API/ README·6개 요청·.resources 메타데이터(F-61)
│  └─ environments/           Local·Internal.environment.yaml, 로컬 API 주소·비밀값 없는 테스트 변수
│
├─ db/                        [DB] (스키마는 docs/db, 검증 후 여기로)
│  ├─ migrations/             0001_init.sql (11-04 검증, 표 12 + 뷰)
│  ├─ seed/                   categories·facilities·regions(230)·sido/sigungu 별칭·category_map.csv → seed.sql (11-04)
│  ├─ views/                  v_venue_rating (0001에 포함)
│  ├─ loaders/                load_seed.py(CSV → seed.sql), load_synthetic (예정)
│  └─ tests/                  제약 검증 SQL·동시 INSERT (예정)
│
├─ crawler/                   [DB] 스페이스클라우드 크롤러 (동작함, 필터는 옛 기준)
│  └─ data/                   기준선·표본 (지우지 않음)
│
├─ simulator/
│  ├─ generator/              [DB] 과거 데이터 백필 (예정)
│  └─ locust/                 [B] 부하·동시성 (예정)
│
├─ infra/
│  ├─ local/                  [DB] docker compose: MariaDB 11.4(3308) + MongoDB 7, 첫 실행 때 0001·seed·mongo_init 자동 (11-04)
│  ├─ haproxy/                [B] 정문 haproxy.cfg: api1·api2 분산, /health 확인 (11-06 B안, 예정)
│  ├─ nginx/                  [B] 서버마다: 정적 파일 + /api → 127.0.0.1:8000 (11-06 B안, README에 초안)
│  ├─ monitoring/             [A] docker-compose, alloy.config, grafana/dashboards (예정)
│  ├─ vm/                     [공동] 로컬 VM 7대 설치 체크리스트 (11-05, 1차 배포)
│  └─ aws/                    [공동] 팀원별 AWS 체크리스트 (참고안)
│
└─ design/
   └─ fonts/                  글꼴 원본(original/, 압축본에서 뺌)·서브셋 스크립트
```

## 3. 파트별 기준 문서와 첫 작업

| 파트 | 기준 문서 (이 순서로 이김) | 첫 작업 | 남에게 먼저 줘야 하는 것 |
| --- | --- | --- | --- |
| A | `백엔드_A` → `산출물_02` 2절 → `산출물_04` 8~9절 | `core/`(config·db·errors·deps·events·clock·pagination) | `get_db_write/read`, `get_current_user`, `AppError`, `log_event`, `get_today` → B (1일차 오전) |
| B | `백엔드_B` → `산출물_01` 3절 → `산출물_04` 7절 | 공개 조회(catalog·venues·slots) → 예약 트랜잭션 → 동시성 테스트 | `get_owned()` → A, `/internal/venues` → 크롤러 |
| DB | `산출물_04` → `db/migrations/0001_init.sql` | (11-04 끝: 실행 검증·0001·seed·compose) → 크롤러 새 필터·`/internal/venues` 등록 → 가상 데이터 | 검증된 스키마·seed → A·B (1일차 오전) |
| FE | `프론트_변경목록_11-03` → `백엔드_A·B` 5절 → `공간대여_04` | FE-1~9 목업 반영 완료 → A·B 구현 후 실제 API 연결 검증 | 이벤트 이름 목록 → A |

### 합치는 순서 (통합 지점)

```
1일차 오전  DB: 스키마 검증 ─┐   A: core ─┐
                              ├─▶ B: 공개 조회 → 예약 트랜잭션 → 동시성 50건 테스트
1일차 오후  A: 회원·후기 ◀── B: get_owned()        FE: 목업을 새 응답 모양으로
2일차       배포(Nginx·FastAPI 2대·RDS primary+replica·MongoDB·모니터링) → FE VITE_USE_MOCK=false 연결
3일차       자동 환경 구성(사용자 데이터 + Compose), Locust replica 있음·없음 비교, 발표
```

## 4. 큰 버그를 막는 체크리스트

커밋 전에 내 변경이 아래를 어기지 않는지 봅니다. 하나라도 어기면 기준 문서와 다르다는 뜻이니 사람에게 먼저 묻습니다.

| # | 확인 | 어기면 생기는 일 |
| --- | --- | --- |
| 1 | 쓰기·인증·'내 것' 조회는 `get_db_write()`, 공개 조회만 `get_db_read()` | 방금 한 예약·가입이 안 보임 |
| 2 | 예약 = 예약·칸·결제 한 트랜잭션, 중복은 기본키 1062 → 409 `SLOT_TAKEN` + `detail.slots` | 중복 예약, 결제만 남은 예약 |
| 3 | '빈 칸인지 먼저 SELECT'로 막지 않음 | 두 서버가 동시에 '비었음'을 봄 |
| 3-1 | 엔드포인트는 `def`(동기 DB를 `async def`에서 쓰지 않음), 1062만 409로 | 서버 전체 멈춤, 다른 DB 오류가 409로 숨음 |
| 3-2 | 표는 `db/migrations/*.sql`로만 만들고 모델은 그 DDL과 같게(`create_all` 금지) | 복합 외래키·CHECK가 빠진 표가 생김 |
| 4 | `pending`·`expired`·`/confirm`·`room_id`·`/rooms`·`posts`를 새로 쓰지 않음 | 지난 설계가 다시 섞임 |
| 5 | 오늘 날짜는 `get_today()`만 | 테스트·시연 날짜 고정이 안 먹음 |
| 6 | MongoDB 쓰기는 응답 뒤, 실패해도 API 성공 | MongoDB 하나 때문에 예약 실패 |
| 7 | 이벤트 이름은 `백엔드_A` 5-3 목록만, 공간은 맨 위 `venue_id` (프론트·생성기 포함) | 그 이벤트가 버려지거나 공간이 빈 채 저장됨 |
| 8 | 표·컬럼·API는 기준 문서, 오류 코드는 `docs/오류코드.md`에 있는 이름만 | 파트끼리 붙일 때 깨짐 |
| 9 | 비밀값은 `.env`에만, 이름은 `.env.example` | 키 유출 |
| 10 | 테스트 DB는 MariaDB `spacecube_test` (SQLite 금지) | 제약이 달라 테스트가 거짓 통과 |
| 11 | 남의 파트 파일·표를 직접 고치지 않음 | 합칠 때 충돌 |

## 5. 이름 규칙

| 대상 | 규칙 | 예 |
| --- | --- | --- |
| 파이썬 파일 | 계층별 `<이름>.py` / `<이름>_service.py` / `<이름>_repo.py` | `venues.py`, `reservation_service.py`, `slot_repo.py` |
| 테스트 | `test_<라우터 이름>.py` | `test_reservations.py` |
| 마이그레이션 | `NNNN_무엇.sql` | `0002_add_venue_index.sql` |
| API 경로 | 복수형 소문자, `/api` 접두사 없이 | `/venues/{venue_id}/slots` |
| JSON 필드 | snake_case, 기준 문서 예시 그대로 | `start_hour`, `capacity_max` |
| 커밋 | `[파트] F-ID 요약` | `[B] F-30 예약·결제 트랜잭션` |
| 문서 | 한국어 파일 이름, 날짜는 `YYYY-MM-DD` | `회의_2026-11-05_배포.md` |

## 6. 압축본으로 받았을 때

압축본에는 `node_modules/`, `dist/`, 테스트 결과, 캐시, 글꼴 원본(`design/fonts/*/original/`의 TTF), `.env`가 없습니다.

1. `C:\MLops03\Pro_1`처럼 같은 이름으로 풉니다(팀이 같은 상대 경로를 씀).
2. `conda env create -f environment.yml`
3. `frontend/`에서 `npm install`, E2E를 돌릴 PC는 `npx playwright install chromium`
4. `powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1`로 받은 그대로 통과하는지 확인
5. `backend/.env.example`, `frontend/.env.example`을 복사해 각자 `.env`를 만듭니다(값은 팀 채널로만).
6. 글꼴 원본이 필요하면 `design/fonts/README.md`의 배포처에서 받습니다(서비스에는 필요 없음).
