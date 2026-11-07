# STATE.md — 지금 어디까지 왔나

사람과 에이전트(Codex, Claude Code)가 함께 고치는 진행 기록입니다. 작업을 끝낼 때마다 해당 줄을 고치고 '최근 변경' 맨 위에 한 줄 더합니다. 설계 내용 자체는 `docs/`에, 여기는 상태와 결정만 둡니다.

- 마지막 갱신: 2026-11-07
- 단계: **11-06 통합 점검** · 설계 11-03 확정안 + 11-05 회의(탈퇴·A6·A7 확정, A8 보류) · DB 0001·seed·로컬 compose 검증 · 프론트 7화면(목업, 다락큐브·푸터 반영) · GitHub develop 흐름·CI·Project 보드 · **1차 배포 로컬 VM 7대(노트북 4대, 11-05)** · B 조회 #31·예약 #39·내부 공간 등록 #42·후기 목록 조회 계약 #44·A 후기 작성·목록 #47 develop 병합 완료. #43 계약과 로컬 MariaDB 관련 테스트 재확인 완료, Swagger 수동 확인은 별도
- 디자인 캔버스(화면 설계 · 시스템 아키텍처 · 글꼴 시안): https://claude.ai/artifact/5dQciCDEaMm8uNjw6sqZpm
- 실행 환경: Python은 conda `pro_1`(`environment.yml`), 프론트는 `frontend/`의 npm

## 파트별 상태

| 파트 | 담당자 | 지금 | 다음 할 일 | 막힌 것 |
| --- | --- | --- | --- | --- |
| B·일일 페르소나 | 이세훈·PM 보완 | #69 PM 피드백 반영: 새 이벤트 문맥·사용자별 `X-Session-Id`·실제 날짜/공간/시간 분산, 실행별 `logs/` CSV·HTML 경로 | 실제 Write·보고서 파일·Loki 적재 검증, 작업 스케줄러 등록 | `pro_1` Locust 2.43.1과 고정 2.47.0 불일치. A7 혼합 부하·DB exporter 계측은 별도 |
| 프론트 | 노진산(FE·PM) | FE-1~9 확정안 반영, Claude 시안 대조·FE 오류/모바일 결제/가입 UX 재검토 및 목업·화면 검증. 11-06 C안 화풍(흰 바탕·검은 글자·주칠)과 유형별 일러스트 5장 유지. CCL 분위기 참고 사진 40장(유형별 8장)을 정적 경로로 연결하고 유형·venue ID 해시로 안정 선택, 사진 표시·크레딧 추가(API `art:` 계약 그대로) | A·B 구현 후 실제 API 연결·오류·예약 동시성 통합 검증 | 실제 API 미구현 |
| FastAPI A | [이름] | 회원·후기 및 F-60 이벤트 구현. #75의 `override_business_time()`과 생성기 `HistoricalRuntime` 가입·후기·이벤트 시각 경계 비교 테스트 24건 통과. MariaDB 11.4.13 `spacecube_test` 전체 backend/db pytest 407건 통과(경고 1건), PR #86 CI DB·백엔드 테스트와 Ruff 통과. A 기능 PR #86은 2026-11-07 develop에 병합됨. 109 api1 파일럿에서 과거 `occurred_at`·실제 `received_at` 분리, 중복 0건을 확인. #5 후속으로 예약 이벤트 `test_reservations.py` 58건과 F-60 선택 테스트 11건 통과 | #5 FE 예약·취소 `event_context`, 검색 ID·`page_view` 연결 후 최신 코드 배포·브라우저 통합 확인. #75 파일럿 결과 그래프 FE/PM 확인 | 사용자 확인: 실제 Linux 서버는 MariaDB 11.4. #5 FE 변경·DB validator 적용 및 최신 배포 후 통합 흐름 확인 대기 |
| FastAPI B | 이세훈 | #67 `feat/B-nginx`에 최신 develop `e7db36f` 통합, 자체 구성한 api1(.232)·api2(.233) 테스트 VM에서 Nginx/FastAPI 동배치·캐시·WebP·loopback keepalive 검증. #66 HAProxy 정문 설정(gw:80 라운드로빈·/api/health 능동 확인·내부 경로 차단·retries 0·8404 지표) 머지, 장애 제외/복귀 시험은 별도. #74·#76 develop 병합: 예약 결과 이벤트 새 형식, 커밋 후 이벤트 문맥·상품 생성·기록 실패에도 업무 응답 유지. 후속 수정은 `fix/B-issue5-product-factory`에서 검증 대기. #77 `feat/B-F-62-generator`에서 #75 생성기 본체·서비스 연결·재개 구현, 실제 MongoDB 100명/30일 검증 완료 | #76 PM 상품 팩토리 후속 리뷰·병합. #75 A 연결 확인·DB 공간 보충/집계/CSV·api1 수동 파일럿. #79 공유 테스트 DB 경합 방지. #8 api1 cron | 원격 MongoDB 서버 문맥 null validator 동기화 필요. 실제 api1·replica·브라우저 E2E 미검증 |
| DB | [이름] | `0001_init.sql`·`mongo_init.js` 검증(설치형 11.8·compose 11.4 둘 다 29건 통과), seed(유형 5·시설 20·지역 230 → `seed.sql`), `infra/local` compose. F-61 두 수집원 파서·매핑·적재 코드와 오프라인 테스트 작성. API 제외 운영 저장 검증에서 MongoDB `crawl.crawl_raw`와 MariaDB `spacecube.crawl_jobs` 각 1건 삽입·재조회·해당 건 정리 성공. `environment.yml`로 `pro_1`(Python 3.12.16) 설치, 크롤러 오프라인 pytest 17건·Ruff 전체 린트·포맷 통과. FE verify(단위 67건·빌드) 통과. 별도 Compass DB의 events·event_daily 속성 정리 v1을 docs/db에 공유 | 실제 단건 파서 확인 → 시연용 공간 선별·API 등록(B와) → 부족분·과거 30일 행동 데이터 생성기 | 운영 저장소 쓰기 경로는 확인했으나 실제 외부 수집·`venues` 등록은 접속 URL·내부 키가 빈 `backend/.env`와 내부 API 미기동으로 미실행 |

## 기능 진행표

상태: 설계 → 진행 → 완료 → 검증(테스트 통과). F-ID는 `docs/산출물_01_요구사항명세서.md`.

| F-ID | 기능 | 담당 | 상태 |
| --- | --- | --- | --- |
| F-01~04 | 회원가입·로그인·내 정보·로그아웃·탈퇴 | A | 가입·회원·탈퇴 구현 및 수동 확인, 전체 pytest 230건 통과. 탈퇴와 동시 예약은 B 협의 대기 |
| F-04 지원 | 탈퇴 전 취소 가능 예약 수 | B / A 연계 | #50에서 예약 전 회원 FOR UPDATE·활성 재확인, 슬롯 충돌 롤백 후 재잠금, 재시도 200 커밋·잠금 해제, count_cancellable의 FOR UPDATE 최신 읽기를 유지. #49 병합 develop 통합 뒤 예약/탈퇴 양방향 경합·인증 스냅샷·실패/재시도 잠금 해제 및 취소 경합 포함 관련 101건·전체 354건·FE 56건·HTTP 7요청/15검증 통과. CI·리뷰/병합 대기 |
| F-10 | 공간 유형 목록 조회 | B | 검증: 11-05 로컬 MariaDB `localhost:3306/spacecube_test`에서 pytest 5건 통과(공개 읽기·실제 DB 응답·5분 캐시·오류 처리) |
| F-11·기준 정보 | 지역·시설 목록 조회 | B | 검증: 활성 지역 필터·시도/시군구 응답·시설 전체 조회·공유 스냅샷·5분 캐시·공개 읽기·검증 오류. 기존 F-10 포함 test_catalog 19건 통과 |
| F-12 | 공간 검색 | B | 검증: GET `/venues`. q·유형·지역·날짜·시간·인원·복수 시설 필터, 검색 뒤 페이지 total, replica 조회. MariaDB 전용 테스트와 실제 HTTP 검색 계약·입력 오류 확인 |
| F-13 | 공간 정렬 | B | 검증: F-12 API의 기본·인기·가격·평점 정렬. 최근 7일 취소·과거 이용 제외, 안정적인 동률 순서. MariaDB 정렬 테스트와 실제 HTTP 정렬 요청 확인 |
| F-14 | NEW 공간 | B | 검증: GET `/venues/new`, 활성 공간의 한국 날짜 기준 오늘 포함 최근 14일 필터, 최신순·페이지 처리·`registered_on`·`new_days_left`, 기본 이미지·공통 목록 응답 |
| F-20 | 공간 상세 | B / A·FE 연계 | B 상세 API 구현·검증: test_venues 28건, 공간 모델 DDL 3건, 실제 API Chrome 1건 통과. 공개 읽기 경로 3건·기존 목업 E2E 59건 통과. A 후기 목록·FE 실제 서버 연결은 별도 통합 항목 |
| F-21 | 예약 가능 날짜 | B | 검증: 공개 available-dates API 구현. 빈 칸 총수·min_hours 이상 연속 빈 칸 판정, 음수 offset·days 1~31·기간 양끝·0일 설정·마지막 페이지 잘림·큰 offset·점유 분리·재조회·SQL 2회·400/404·읽기 의존성 등 48건 추가. test_venues 114건, 전체 pytest 153건, 실제 HTTP Chrome 1건 통과. FE 전체 연결은 별도 |
| F-22 | 날짜별 시간 칸 | B | 검증: 공개 GET /venues/{venue_id}/slots?date=YYYY-MM-DD 구현. 엄격한 날짜·설정 범위 양끝·0일 설정, 공간/날짜별 점유·완료 칸·past·F-20 일치·재조회·400/404·읽기 의존성 등 38건 추가. test_venues 총 66건, 전체 pytest 105건, 실제 HTTP Chrome 1건 통과 |
| F-30~32 | 예약+모의 결제 한 번, 중복 차단 | B | #76 PM 후속: 상품 팩토리를 이벤트 래퍼 안에서 호출. 상품 생성 실패 시 예약 201·취소 200·충돌 409와 저장·환불·슬롯 결과 유지 회귀 추가. 생성기 흐름에서 운영 상품 빌더 억제 확인. `verify.ps1` Ruff 109파일·pytest 434건·FE 단위 67건·린트/색 검사/빌드 통과. FE 조건문 린트 경고와 Starlette 사용 중단 경고 각 1건 |
| F-34 | 예약 취소·환불 | B | #49에서 develop 3a729f2와 코드 충돌 해결. 실제 취소 API 뒤 F-40 목록/상세가 같은 cancelled·refunded 상태인지 검증. 활성/비활성 공간 5개 유형 category 기록과 원자 환불·슬롯 반납·동시 취소·재예약 유지. 관련 94건·전체 347건·HTTP 7요청/15검증·CI 통과 후 #49가 55ebd23으로 develop 병합됨 |
| F-35 | 이용 완료 배치 | B | #49의 primary 조건부 일괄 UPDATE·get_now 1회·commit/rollback·CLI·완료 뒤 칸/결제 보존을 develop 통합 후 재검증. test_jobs 6건 포함 관련 94건·전체 347건 통과. 실제 api1 시간별 cron 등록·실행은 미완료이므로 #8 유지 |
| F-40~41 | 내 예약, 내 후기 | B / A | #46 조회·필수 nullable review_id·필드 생략 해제는 develop 병합됨. #49·#50 후속 병합도 완료. #45 브랜치에서 A `get_review_ids`를 목록·상세에 연결하고 미작성 null·작성/삭제 이력 ID·페이지당 SQL 1회·소유권 차단을 MariaDB/HTTP로 검증. PR 리뷰·병합 대기. F-41은 A 범위 |
| F-50 지원 | A 후기 작성용 예약 소유권 조회 | B | 예약·칸·결제 모델 및 `get_owned()`를 이전 프로젝트에서 가져옴. DDL 일치·매퍼 구성 4건, 실제 MariaDB 소유권·A 후기 작성 연결 10건 통과. 예약 생성 API 구현 완료를 뜻하지 않음 |
| F-51 지원 (#43) | A 후기 목록용 예약·공간·유형 조회식 | B / A 연계 | 검증: B 4열 `review_context_query(*, active_only=True)` PR #44, A 직접 import·공개 비활성 공간 제외·내 후기 유지 PR #47이 develop 병합됨. 로컬 MariaDB 관련 테스트 58건 통과. Swagger 실제 데이터 수동 확인은 별도 |
| F-50~51 | 후기 작성·조회(후기 모아보기) | A | B get_owned·review_context_query 연결, 작성·목록·수정·삭제 및 탈퇴 후 예약·후기 보존·작성자 익명화 로컬 MariaDB 검증. 공개 비활성 공간 제외·내 후기는 포함. 전체 backend pytest 318건 통과 |
| F-60, F-62~65 | 이벤트(로그 파일 + MongoDB), 가상 데이터, `get_today`, 서버 로그, 지표 | A | 진행: #60 승인 구조의 파일 우선·새 로그 재적재 구현. 테스트 MongoDB에서 FE 검색·서버 이벤트 저장, 개인정보 제거, 재적재 중복 제외·MongoDB 장애 202·파일 실패 503 확인. #5 후속에서 B #80 병합 뒤 예약 이벤트 실패 경계 포함 `test_reservations.py` 58건, 문서/개인정보/중복/장애 선별 테스트 11건 및 MariaDB 11.4.13 전체 backend/db pytest 407건 통과 기록 확인. 사용자 확인: 실제 Linux 서버는 MariaDB 11.4. FE 예약·취소 문맥, 검색 ID·`page_view`, 최신 배포 후 브라우저 흐름이 남아 #5 미완료 |
| F-60 B 지원 (#60·#72) | 예약 결과 3종·상품 스냅샷·선택적 브라우저 문맥 | B / A·DB 연계 | B 구현·A d75deea 임시 통합 검증: 관련 pytest 77건·전체 375건, Postman 7요청/15검증, 지정 MongoDB에서 결과 3종 실저장·동일 ID 중복 제외·가상 데이터 정리. A의 server-요청 ID 보완 및 원격 validator null 허용 반영 전 최종 완료 아님 |
| #20·#69 | 일일 네 페르소나·안전 실행·실험 기록 | B | PM 댓글의 새 이벤트 문맥·사용자별 `X-Session-Id`·예약 날짜/공간/시간 분산·실행별 `logs/` CSV·HTML 반영. 전용 pytest 32건, Ruff·Locust 클래스 목록 통과. 실제 Write·보고서 생성·Loki 적재 및 고정 Locust 2.47.0 미검증 |
| F-61 | 크롤링 신규 등록 | DB / B | 진행: B POST /internal/venues 구현·로컬 검증 완료(35건·같은 출처 동시 8건·HTTP 6요청/12검증). DB 두 파서·유형/지역 매핑·crawl_raw·crawl_jobs·API 재시도와 오프라인 테스트 작성. API 제외 운영 저장 검증에서 MongoDB `crawl_raw`·MariaDB `crawl_jobs` 각 1건 삽입·재조회·정리 성공. `pro_1` 크롤러 오프라인 pytest 17건·Ruff·FE verify 통과. `venues` 등록·실제 외부 수집은 별도 미검증; `backend/.env` 접속 값·키 미설정 |
| #19·#75 생성기 | 과거 30일 회원·예약·결제·후기·이벤트 백필 | B 본체·A 연결 확인·DB 공간/집계/CSV | 구현·검증: CLI·고정 세션·서비스 호출·과거 업무 시각/실제 received_at·관측 억제·manifest/state 재개. 최종 verify.ps1 통과(pytest 399건·FE 67건·린트/빌드), 생성기 21건(실제 MariaDB 및 지정 MongoDB) 통과. 11-07 109 파일럿: 공간 31곳, 100명·30일, 세션 1,260·예약 841(완료 757·취소 84)·충돌 396·후기 189·이벤트 10,368건. 생성기 이벤트 모두 `is_synthetic=true`, `server=generator`; `occurred_at` 10-07 23:00Z~11-06 10:42Z, `received_at` 11-07 09:58Z, 전체 `event_id` 중복 0. PM 보고: `event_daily` 32일 3,974행·재실행 신규 0, 크롤러 법정동 대응을 109에 적용; 별도 PR 예정. 남음: FE/PM 그래프 확인 |
| #54 | HAProxy 정문·서버별 Nginx | B / A / DB | #67 자체 구성한 테스트 환경의 api1(.232)·api2(.233)에 Nginx/FastAPI 동배치 적용. Nginx 1.24 nginx -t·캐시/MIME·404/internal 차단·loopback API keepalive 확인. primary health와 GET categories 200(읽기 전용), MongoDB 주소 미제공으로 degraded. 테스트 VM의 배포·설정·백업 경로는 infra/nginx/README.md. HAProxy 장애 제외/복귀는 #66 별도 |
| F-70 | 헬스체크 3단계 | A | 설계 확정 |
| #78 공통 검증 | 공유 테스트 DB 병렬 실행의 회원 재가입 500 방지 | 공동(B 구현) | 최신 develop f387df2에서 독립 브랜치로 구현. 루트 conftest의 session 잠금·테스트 전 소유권 확인·대기 600초/조정·종료 해제. 실제 DB 잠금 회귀 29건, 기존 실패 재현 두 프로세스 각각 5건 통과(대기 후 진행), 최종 verify.ps1 pytest 407건·FE 67건·린트/빌드 통과. API·DDL·업무 트랜잭션·기존 동시성 검증은 유지. 11-07 ef39125에서 회귀 29건·병렬 재가입 5+5회·전체 verify(Python 407건·FE 67건) 및 하위 폴더 실행 1건 재통과. PR #79(develop) 생성·리뷰 대기. 잠금 미적용 checkout 및 pytest 외 DDL 작업은 별도 순차 실행 필요 |
| — | 같은 칸 동시 50건 중 1건만 성공 | B / DB | 설계 확정 (MVP 통과 조건) |
| — | F-33 결제 대기 만료, F-52 자유게시판·댓글, F-53 공지 | — | 11-03 삭제 |

## 결정 기록

| 날짜 | 결정 | 근거 |
| --- | --- | --- |
| 11-06 | #78: 같은 로컬 spacecube_test의 pytest는 공통 session 명명 잠금으로 직렬화한다. 전용 AUTOCOMMIT 연결로 GET_LOCK/소유권 확인/RELEASE_LOCK만 실행하며 업무 코드는 변경하지 않는다. 직접 pytest·verify·CI에 적용하고, 같은 suite 안의 예약 50요청 동시성은 유지. 구버전 checkout·pytest 외 DB 초기화는 잠금 규약 밖이므로 갱신/순차 실행한다 | 사용자 요청 · 이슈 #78 · tests/README.md |
| 11-06 | #75: B가 생성기 본체·세션·예약 담당. api1 별도 프로세스에서 A 회원/후기 및 B 예약/취소 서비스 직접 호출, 100명·30일·42세션/일, 페르소나 35/25/20/20·409 재시도 1회·취소 10%·후기 25%·별점 5/4/3/2/1=40/30/15/10/5. 과거 업무 시각과 실제 received_at을 분리하고 새 표 없이 manifest/state·UUID5로 재개. DB는 유형별 공간 6개 보충·집계·CSV·정리, FE는 그래프 확인 | 사용자 지시 · #75 PM 댓글 issuecomment-6684120999 · simulator/generator/README.md |
| 11-06 | 사진은 유형별 8장씩 40개의 CCL 분위기 참고 이미지로 사용한다. 프론트가 venue ID와 유형으로 안정 선택하고 실제 공간 사진이 아님을 알린다. 원본·저작자·라이선스·편집 사실은 화면과 `SOURCES.md`에 표시하고 `art:` API·DB 계약은 바꾸지 않는다 | 사용자 요청 · `frontend/public/photos/credits.html` · `docs/데이터_수집_명세.md` |
| 11-06 | #60: 서버 결과 3종에 한해 `user.anonymous_id`·`user.session_sequence`·`site`·`acquisition`·`page`·`navigation` null 허용. `log_event`의 기존 7개 인자를 보존하고 키워드 전용 `products=None` 추가. FE는 공간 ID만 보내고 A가 활성 공간 이름·현재 가격 조회. 옛 로그 보존, 새 로그만 재적재. UTM 코드는 허용값 결정 전 null로 제한 | #60 PM 댓글 · PR #58 |
| 11-06 | 사용자 이벤트 저장 구조는 DB가 만든 `space_rental_analytics`의 `events`·`event_daily`(`docs/db/events_event_daily_컬렉션_속성정리_v1.md`)를 기준으로 채택. 행동 이름 15종·중첩 필드로 바꾸고, 백엔드 A·B·FE·`mongo_init.js`·`산출물_04` 9절을 이 문서에 맞춘다(대응표: PR #58 코멘트). 서버 이벤트의 화면 정보 전달 방식 등 4가지는 11-07 오전까지 결정 | PM 결정 · PR #58 |
| 11-06 | #46 병합 이후 후속 처리는 #49 충돌 해결·검증·병합 → #50 최신 develop 통합·검증·병합 → #45 실제 후기 ID 연결 순서. #8은 실제 api1 시간별 cron 등록·실행 확인 전까지 유지 | 사용자 지시 · PR #49 PM 댓글 issuecomment-6674796150 |
| 11-06 | #45 내 예약의 `review_id`는 삭제된 후기 ID도 유지하고, 미작성만 `null`로 표시한다. A는 `get_review_ids(db, reservation_ids)`로 본인 예약 페이지 ID를 SQL 한 번에 조회해 B에 매핑을 제공하며 트랜잭션은 종료하지 않는다. 새 삭제 상태 필드는 추가하지 않는다 | #45 A·B·PM 합의 · `AGENTS.md` 약속 · `백엔드_A·B` 3절 |
| 11-05 | #43 후기 목록은 B review_context_query(*, active_only=True)의 4열 Select를 A review_repo가 직접 import해 결합한다. 공개 목록은 비활성 공간 후기 숨김, 내 후기는 False로 유지. 세션 실행·후기 조인·마스킹은 A, review_create는 프론트만 전송. B PR #44와 A PR #47 병합·로컬 MariaDB 통합 검증 완료 | #43 PM 승인 댓글 및 B·A 동의 · `AGENTS.md` 약속 · `백엔드_A·B` 3절 |
| 11-05 | F-30~32에서 본인 예약 여러 건과 모두 겹치면 `SLOT_TAKEN.detail.reservation_id`는 겹친 예약 ID 중 최솟값으로 반환한다. 자동 증가 ID는 실제 커밋 순서를 보장하지 않는다고 구분한다 | 사용자 승인 · `docs/백엔드_B` 6절 · `docs/오류코드.md` |
| 11-05 | F-21은 offset 기본 0·음수 허용, days 기본 14·1~31. 시작 범위 밖은 OUT_OF_RANGE, 마지막 페이지 뒷부분은 최대 날짜에서 자르고 응답 days는 요청값 유지. free는 빈 칸 총수, bookable은 연속 빈 칸 ≥ min_hours이며 지난 칸 포함 | 사용자 승인 계획 · 기존 FE venuesApi 목업 · `백엔드_B` 5-2절 |
| 11-05 | F-22 날짜는 필수 `YYYY-MM-DD` 실제 날짜. 형식·누락은 `VALIDATION`, 설정 범위 밖은 `OUT_OF_RANGE`와 날짜 양끝 detail 반환. 지난 칸·완료 점유 유지, F-20과 시간 칸 조합 함수 공유 | 사용자 승인 구현 계획 · `백엔드_B` 5-2절 · `오류코드` |
| 11-05 | F-20 이미지 누락은 RoomArt 기본값 `art:group-0`으로 대표 이미지·상세 갤러리를 통일하고 별도 lounge 대체값은 추가하지 않음. NEW는 한국 날짜 기준 오늘 포함 최근 14일(`0 <= 날짜 차이 < 14`), 미래 날짜 제외 | 사용자 지시 · `산출물_01` F-14·20, `백엔드_B` 5-2절 |
| 11-05 | 로그아웃: 프론트가 헤더 사용자 메뉴·내 메뉴에서 토큰을 지우고, 서버 `POST /auth/logout`(유효 토큰 확인 → 204)도 둠(11-03 "로그아웃 API 없음"을 바꿈). 토큰 폐기 목록은 없음 | PM 결정 · #32·#33·#34, `산출물_01` F-02 |
| 11-05 | 1차 수집원은 스페이스클라우드·쉐어잇 2곳. 속성 기반 시연용 공간 15~20개를 목표로 선별하되, 30개 목표에서 최종 검토 후 부족한 공간은 생성기(`source_site=synthetic`)로 `/internal/venues`에 등록. 과거 사용자 행동 데이터는 우선 30일분 생성하고 `is_synthetic`으로 실제 로그와 분리. 루북·스파크플러스는 1차 제외, 사진안은 미확정 | 사용자 결정 · `docs/데이터_수집_명세.md` |
| 11-05 | 데이터 작업 경계(#38): ① 생성기의 예약·칸·결제는 B 저장 로직 재사용(한 트랜잭션, 백필 경로에만 과거 시각), 회원·후기는 생성기가 SQL로 넣되 비밀번호는 A bcrypt 함수 ② 생성기·크롤러는 api1에서 실행, A가 키·접속 정보·cron 설치, 노트북 4는 API·화면·부하 시험 ③ 과거 이벤트는 MongoDB 직접 적재·분석은 `event_daily`, Loki는 실제 로그, 직접 적재분은 API 전달 성공률에서 제외 ④ F-62(A)와 #19 생성기(DB)는 따로 관리 ⑤ 속성 기반 15~20개 + 생성으로 총 30개, 주간 수집은 보충·0건 허용 ⑥ 과거 30일·회원 풀 1,000명(100명 먼저 검증, 11-07 확정). 미정: `/internal/venues` 제공 시각(B), 쉐어잇 표본 위치(DB), 탈퇴·동시 예약 처리(A·B), Grafana의 MongoDB 연결(A·DB) | PM 결정 · 이슈 #38 |
| 11-06 | **정문 구성 B안**: 사용자 → `gw` HAProxy(:80, api1·api2 라운드로빈, `/health` 2초 능동 확인, `/api/internal`·`/api/metrics` 차단, 통계 8404) → 서버마다 Nginx(:80, Vue 정적 파일 + `/api` → `127.0.0.1:8000`) → FastAPI. A안(Nginx 뒤 HAProxy)은 프록시가 두 겹이고 `gw`에 몰려 확장이 막혀 뺌. `gw` 단일 장애점은 발표 범위에서 허용(실서비스는 HAProxy 2대 + keepalived) | PM 결정 · `docs/figures/haproxy_compare.png`, `로컬_VM_구성.md` |
| 10-30 | 스터디룸 → 공간대여로 확장, 유형 5개(스터디룸·스튜디오·카페·영화관·파티룸, 11-03에 영화관 → 강의실), 전국 | 회의 · `docs/공간대여_01` |
| 10-30 | 결제는 '확정 = 결제 완료'인 모의 결제 | 회의 |
| 10-30 | 예약은 1시간 칸, 중복은 `reservation_slots` 기본키로 DB가 차단 | `docs/공간대여_02` |
| 10-30 | Nginx → FastAPI 2대 → RDS MariaDB, NAT 게이트웨이 없음, 팀원별 VPC 10.1n.0.0/16 | `docs/AWS_네트워크_설계.md` |
| 10-30 | FastAPI 분담: A 회원·후기·게시판·로그 / B 공간·검색·예약·결제 | `docs/공간대여_03` |
| 10-30 | 공간 사진은 크롤링하지 않고 일러스트 10종 × 색 2가지를 순환 | 회의 |
| 10-30 | 가상 데이터는 규칙 기반·`is_synthetic`으로 분리, 구조 검증용 | 회의 |
| 10-30 | 문서는 노션이 아니라 이 저장소의 md로 관리 | 팀 |
| 10-30 | 에이전트 지침은 `AGENTS.md` 하나로 Codex·Claude Code 공용, `CLAUDE.md`는 두지 않음 | 이 파일 '에이전트 사용' |
| 10-31 | 프론트는 Vue 3 + Vite, JavaScript + 일반 CSS(scoped), reka-ui·vue-sonner·@vueuse/core·@lucide/vue | `frontend/README.md` |
| 11-01 | UI 패턴: 패럴랙스만 안 씀, 캐러셀·리빌·스태거·툴팁은 정해진 곳에만, 움직임 줄이기 준수 | `docs/공간대여_04` |
| 11-01 | Python 실행 환경은 conda `pro_1`(3.12) 하나로, 기존 `MLops03` 환경과 분리 | `environment.yml` |
| 11-01 | 글꼴 후보 5종(Noto Sans KR·Pretendard·Freesentation·SUIT·Spoqa) 수집, 결정 전 기본값 Pretendard | `design/fonts/README.md` |
| 11-01 | 글꼴은 Noto Sans KR (`--font-sans`) | 시안 비교 · `docs/공간대여_04` |
| 11-01 | 프론트 검증: Oxlint + ESLint(flat) · Vitest + Vue Test Utils · Playwright + axe. 커밋 전 `npm run verify` | `frontend/README.md` 검증 |
| 11-02 | 파이썬 린트·포맷은 Ruff 하나(`ruff.toml`). 커밋 전 루트 `verify.ps1`로 파이썬+프론트를 한 번에 | `AGENTS.md` 검증 |
| 11-03 | RDB는 MariaDB 11.4(RDS), 비정형은 MongoDB 7(EC2). MariaDB는 master–slave(primary + read replica), 클러스터(Galera)는 안 함 | `docs/산출물_04_DB명세서.md` 1절 |
| 11-03 | 예약 홀딩 없음, 결제 순서대로 확정. 상태는 confirmed·completed·cancelled | 11-03 회의 |
| 11-03 | 회원 글은 후기만(자유게시판·댓글 삭제). 관리자 없음 | 11-03 회의 |
| 11-03 | 사용자 이벤트는 로그 파일(→ Loki) + MongoDB, 지표는 Prometheus, 화면은 Grafana | `docs/산출물_02` |
| 11-03 | 크롤링 유지(스페이스클라우드 → MongoDB crawl_raw → `/internal/venues`), 날짜는 실제 날짜 + 과거 데이터 생성 | 사용자 결정 |
| 11-03 | 구현 기준 문서는 `docs/산출물_01~04`·`docs/백엔드_A·B`·`docs/프론트_변경목록_11-03.md`. 10-30 설계는 `docs/지난설계/`, 회의·검토는 `docs/기록/`로 옮김. 폴더 지도는 `STRUCTURE.md` | 폴더 정리 |
| 11-03 | DB 접근은 SQLAlchemy 2.1 동기 + PyMySQL, MongoDB는 pymongo, 엔드포인트는 `def`. 표 변경은 SQL 파일 마이그레이션(Alembic 안 씀), 모델은 DDL에 맞춤. 백엔드 패키지 버전을 `environment.yml`에 고정 | 사용자 결정 · `backend/AGENTS.md` |
| 11-04 | 일정: 11-04(수) 로컬 개발 → 11-05(목) 합치기·전체 기능 점검 → 11-06(금) 피드백·검토 → 11-07(토) 반영 → 11-08(일) 발표 자료 → 11-09(월) 발표. GitHub 마일스톤·이슈로 관리 | 팀 결정 |
| 11-04 | HTTPS는 먼저 HTTP로 배포·시연 흐름이 다 되면 그때 검토(도메인 + Let's Encrypt 또는 ALB + ACM). 그 전에는 HTTP라 로그인 비밀번호·토큰이 평문으로 감을 알고 시연 계정만 씀 | 사용자 결정 · 2차 검토 #3 |
| 11-04 | 지역 seed는 기초자치단체 단위 230행(시·도 16, 일반구 제외), 2026-11-04 기준(전남광주통합특별시·인천 2군 9구 반영). 둘로 나뉜 옛 구(인천 중구·서구) 주소는 제외 | `db/seed/README.md` |
| 11-04 | 로컬 DB는 `infra/local` compose(MariaDB 11.4 포트 3308 + MongoDB 7), 첫 실행 때 0001·seed·mongo_init 자동 | `infra/local/README.md` |
| 11-04 | DB 연결과 RDS 파라미터 그룹 모두 `sql_mode`에 `STRICT_TRANS_TABLES` 필수(없으면 잘못된 ENUM·빠진 날짜가 조용히 저장됨). DDL·mongo_init은 로컬 실행 검증 통과, RDS 11.4에서 한 번 더 | `docs/기록/검증_2026-11-04_DDL실행.md` |
| 11-04 | AWS는 프리 티어 안에서, **크레딧 방식 계정**(웬만하면 무료, 크레딧 조금). 평소는 노트북(로컬 compose), AWS는 **C안: EC2 3대(① 정문 Nginx + MongoDB, ② FastAPI #1 + cron, ③ FastAPI #2 다른 AZ), Docker 없이 직접 설치(systemd)** + RDS 1대, 측정·시연 때만 켬. replica는 측정하는 날만, 모니터링은 Grafana Cloud 무료. 작업 시간만 켜면 월 약 $17. EC2 5대 + RDS 2대는 확장안 | 사용자 결정 · `docs/AWS_프리티어_구성.md` |
| 11-03 | A4 API 세부 확정: 이중 결제는 같은 요청이면 200(처음 예약), 일부만 내 예약과 겹치면 409 `mine`; 탈퇴 시 이름·휴대폰·생년월일·이메일 즉시 지움(예약·후기는 `user_id`로 남김), 같은 이메일 재가입 허용, 후기 작성자 '탈퇴한 회원' | 사용자 결정 · `docs/백엔드_A·B`, `docs/오류코드.md` |
| 11-03 | A3 기초 데이터 확정: 유형 스터디룸·스튜디오·카페·강의실·파티룸(영화관 → 강의실, 코드 `lectureroom`, 그림 `seminar`), 크롤링 3곳(스페이스클라우드 주·쉐어잇·루북, robots.txt 11-03 확인, 2·3순위는 약관·표본 20건 승인 뒤), 지역은 행정구역 전체 + 공간 있는 지역만 표시 + 시·도 짧은 이름 맞춤, 연습실 계열 제외 | 사용자 결정 · `db/seed/README.md`, `docs/공간대여_06` |
| 11-03 | A2 DB 스키마 확정: `min_hours` 복원(팀원안과 다름), 결제수단 영문 코드(팀원안 한글과 다름), 시간 범위 CHECK 9~23(영업·예약·칸), 필수 동의 시각 2칸, 만 14세 미만 가입 불가 | 사용자 결정 · `docs/산출물_04` 2·7절, `docs/db/spacecube_mariadb.sql` |
| 11-03 | A1 파트 약속 확정: `get_current_user()`→`CurrentUser(user_id)`, `log_event(…, venue_id, category, payload, is_synthetic)`(MongoDB는 내부 스레드 풀 2개·대기열 1,000건), `get_session_id()`, `get_today()`·`get_now()`(시간대 없는 한국 시각), `v_venue_rating`, `get_owned()`(+`created_at`) | 사용자 결정 · `docs/백엔드_A·B` 3절 |
| 11-03 | 날짜는 실제 날짜, 가상 날짜 없음(팀원 제안 검토). 예약은 과거·미래 각 365일 열고 지난 시간 예약은 만들 때 바로 completed, 후기 기한 `max(이용일, 예약한 날)`+7일, 인기순은 실제 결제 시각 기준 | 사용자 결정 · `docs/기록/검토_2026-11-03_가상날짜_제안.md` |
| 11-03 | 오류 코드는 `docs/오류코드.md` 한 곳(공통 8·A 8·B 10·프론트 2)에만, 다른 문서는 링크 | 사용자 요청 |
| 11-03 | UX 법칙 5개(힉·피츠·제이콥·근접성·폰 레스토프)를 화면 규칙으로: 보이는 영역마다 채운 버튼 하나, 선택지 7개 안팎, 누르는 것 44px·간격 8px | `docs/공간대여_04` |
| 11-03 | 서버·프론트 이벤트를 같은 세션으로 묶으려고 모든 요청에 `X-Session-Id` | `docs/기록/검토_2026-11-03_문서_2차검토.md` 1번 |
| 11-03 | 디자인 스킬: 점검은 impeccable·design-motion-principles, 보안 점검은 ecc-security-review. hallmark·design-taste-frontend는 기존 화면에 안 씀 | `frontend/AGENTS.md` |
| 11-03 | 토큰은 액세스 토큰만(JWT HS256 60분, Bearer 헤더, `sub` 문자열), 리프레시·쿠키·로그아웃 API 없음. 프론트는 401이면 로그인으로 보내고 선택 유지 | 사용자 결정 · `docs/백엔드_A` 5-1 |
| 11-03 | 이벤트 `unselect_slot`·`abandon`은 만들지 않고 이탈은 세션 분석으로 계산. `POST /events`는 모르는 이벤트를 그 건만 버리고 202 + `ignored`. 공간은 이벤트 맨 위 `venue_id` | 사용자 결정 · `docs/백엔드_A` 5-3 |
| 11-03 | 공간 등록은 `/internal/venues` 한 길(DB 직접 로더 없음), 백엔드 운영 스크립트는 `backend/scripts/` | 폴더 정리 |
| 11-05 | 취소할 수 있는 예약(`confirmed`·시작 전)이 남은 회원은 탈퇴를 막는다: 409 `HAS_UPCOMING_RESERVATION` + `detail.count`, 이용 중인 예약은 막지 않음. B가 `reservation_repo.count_cancellable(db, user_id)` 제공(A·B 확인 필요), FE는 탈퇴 창에서 버튼을 끄고 예약 내역 링크 | 11-05 회의(이슈 #12) |
| 11-05 | A6 배포 확정: ① `X-Synthetic: 1`은 `X-Synthetic-Key`(= `SYNTHETIC_API_KEY`, `INTERNAL_API_KEY`와 따로)와 함께일 때만 인정, 키 없음·틀림은 401 `UNAUTHORIZED`(새 코드 없음) ② RDS 자동 백업 7일·삭제 보호·파라미터 그룹 ③ `limit_req`는 넣지 않음(Locust가 IP 하나라 부하 시험을 막음, B8 조건 그대로) ④ Nginx `max_fails=2`·`proxy_connect_timeout 2s`·GET만 다시 보내기. HTTPS는 11-04대로 나중. A는 새 설정 키 확인 필요 | 11-05 회의(이슈 #18) |
| 11-05 | A7 측정 기준 확정: 동시 50명에서 판정(조회 p95 300ms·예약 p95 500ms·로그인/가입 p95 800ms 미만, 오류율 1% 미만), 200명은 한계 찾기(기록만). Locust 쪽 p95로 판정, 단계 10분(첫 1분 뺌). 오류 = 5xx·연결 실패·시간 초과(시나리오가 일부러 만드는 409·401·400은 뺌). 서버 1대 끄기는 끈 뒤 1분 오류 1% 미만·중복 0. 불합격이어도 5일 안에 서버를 늘리지 않고 원인을 발표 | 11-05 회의 |
| 11-05 | **1차 배포를 AWS 대신 팀 노트북 4대(16코어·32GB)의 VM 7대로**: 노트북 1(DB) `gw`·`db1`·`mongo`, 노트북 2(A) `api1`·`mon`, 노트북 3(B) `api2`·`db2`, 노트북 4(FE·PM) Locust·생성기·E2E·시연. VirtualBox 브리지, 팀 공유기, Ubuntu Server 24.04, apt·systemd(Docker 없음), `ufw`. replica 계속 켬, 모니터링은 `mon` VM, 백업은 cron, 삭제 보호 대신 VM 스냅샷. A6·A7 나머지는 그대로(A7은 유선 기준). AWS C안·확장안은 참고안 | PM(노진산), `docs/로컬_VM_구성.md` |

## 후속 검증 — 실제 primary·replica 환경 준비 후

- [ ] 현재 DB는 한 대이므로 실제 복제 연결·replica 서버 장애·복제 지연 시험은 환경을 마련한 뒤 진행한다(11-05 사용자 확인).
- [ ] 별도 replica에서 공개 조회가 수행되는지, 새 데이터가 복제되는지 확인한다.
- [ ] 실제 replica 연결이 끊겼을 때 primary 전환·응답·대체 지표를 확인하고, 복제 지연 관측도 별도로 검증한다.
- 현재 통과한 DB 한 대의 연결 실패 모의 시험은 실제 복제 환경 시험을 대신하지 않는다.

## 열린 질문 — 한 번에 검토할 목록

방향(11-03): **먼저 지금 설계로 띄우고 재 본 뒤, 조건을 넘는 것만 더한다.** 그래서 A(지금 정할 것)만 검토하고, B(나중에 추가)는 조건과 함께 적어 둔다. A는 막는 순서대로 정렬했다. 정해지면 `[x]` 목록으로 옮기고 결정 기록에 한 줄 쓴다.

### A. 지금 정할 것 (1차 필수, 검토 순서)

| # | 묶음 | 정할 것 | 권장 | 막는 것 | 근거 |
| --- | --- | --- | --- | --- | --- |
| ~~A1~~ | 파트 약속 | **확정(11-03)** — 아래 '이미 정한 것' | — | — | `백엔드_A·B` 3절 |
| ~~A2~~ | DB 스키마 | **확정(11-03)** — 아래 '이미 정한 것' | — | — | `산출물_04` 2·7절 |
| ~~A3~~ | 기초 데이터 | **확정(11-03)** — 아래 '이미 정한 것' | — | — | `db/seed/README.md` |
| ~~A4~~ | API 세부 | **확정(11-03)** — 아래 '이미 정한 것' | — | — | `백엔드_A` 5-1·5-2, `백엔드_B` 6절 |
| A5 (추후 확정) | 협업 | git 원격 저장소·브랜치·PR 리뷰, 비밀값(`.env` 값) 나누는 곳 | GitHub + `main` 보호 + 파트 브랜치 + PR 1명, 비밀값은 팀 채널 비밀 메시지 하나로 | 파트 합치기 | 2차 검토 4절 |
| ~~A6~~ | 1차 배포 구성 | **확정(11-05)** — 결정 기록 11-05 | — | — | `인프라_트래픽_안정성_검토.md` 1-1절 |
| ~~A7~~ | 측정 기준 | **확정(11-05)** — 결정 기록 11-05 | — | — | 같은 문서 1-1절, `산출물_01` NFR-05 |
| A8 (추후 확정, 11-05 회의에서 보류 → 다음 회의) | 발표 전 | 시연 시나리오·시연 계정, 크롤링 약관 최종 확인, 서비스명 겹침 | `docs/시연_시나리오.md` 만들기, 발표 전 확인 | 3일차 발표 | 2차 검토 4절 |

A1~A4는 11-03에 확정했고, **A5~A8은 추후 확정**으로 미뤘다(11-03). 그 전까지는 각 줄의 '권장'을 임시 기준으로 쓰고, 코드에 박아 넣지 않는다(예: 정문·모니터링 위치·합격선은 설정값·문서로만).

### B. 나중에 추가 (띄워서 잰 뒤 조건을 넘을 때만)

| # | 추가할 것 | 넣는 조건 |
| --- | --- | --- |
| B1 | 정문 교체: ALB(권장) 또는 HAProxy | 서버 1대 끄기 시험에서 실패 1% 이상, 도메인 HTTPS를 붙일 때, 정문 EC2 장애 |
| B2 | Auto Scaling 그룹 + 시작 템플릿 (cron은 모니터링 EC2로) | 목표 인원에서 CPU 70% 이상 10분 넘게, p95 초과 원인이 CPU |
| B3 | EC2 크기 올리기 | `CPUCreditBalance`가 시험 내내 줄어듦 |
| B4 | RDS 크기 올리기 / replica 추가 | 연결 수 80%·CPU 70% 이상 / replica CPU 70% 이상 또는 조회 p95만 초과 |
| B5 | RDS Multi-AZ | 운영 단계(실사용자) |
| B6 | CloudWatch 경보 세트 → SNS, 런북 상세 | 하루 넘게 켜 둘 때 |
| B7 | SSM Session Manager·Parameter Store | 서버가 3대를 넘거나 B2를 넣을 때 |
| B8 | 요청 제한(`limit_req`/WAF) | 시연 밖에서도 열어 둘 때, 로그인 실패가 몰릴 때 |
| B9 | MongoDB 스냅샷 자동화 | 이벤트를 시연 뒤에도 남길 때 |
| B10 | Locust EC2 | 1,000명 시험 때만 |

그 전까지 Codex는 실행한 폴더의 `AGENTS.md` 하나만 읽으므로 `Pro_1`에서 실행한다.

이미 정한 것:

- [x] A4 API 세부 → 같은 결제 요청을 10분 안에 다시 보내면 200 + 처음 예약, 내 다른 예약과 겹치면 409 + `mine`; 탈퇴 회원 후기는 '탈퇴한 회원'으로 남김; 탈퇴하면 개인정보 바로 지우고 같은 이메일 재가입 허용(11-03)
- [x] A3 기초 데이터 → 유형 스터디룸·스튜디오·카페·강의실·파티룸(영화관 → 강의실), 지역은 행정구역 전체 seed + 화면엔 공간 있는 지역만, 연습실 계열 제외(11-03). **수집원은 11-05 결정으로 변경:** 스페이스클라우드·쉐어잇 2곳 + 부족분 생성
- [x] A2 DB 스키마 → `min_hours` 복원, 결제수단 영문 코드, 예약 시간 DB CHECK 9~23, `users.terms_agreed_at`·`privacy_agreed_at` + 만 14세 미만 가입 불가(11-03). DB 담당 팀원에게 알릴 것
- [x] A1 파트 약속 → 문서대로 확정 + `get_owned()`에 `created_at`, `log_event()`에 `category`, MongoDB 쓰기는 내부 스레드 풀, `get_now()`는 시간대 없는 한국 시각(11-03)
- [x] 날짜 → 실제 날짜, 가상 날짜 없음, 예약은 과거·미래 365일(지난 시간은 바로 completed), 후기 기한 `max(이용일, 예약한 날)`+7일(11-03)
- [x] 오류 코드 → `docs/오류코드.md` 한 곳에 전체(11-03)
- [x] 토큰 → 액세스 토큰만, JWT 60분, Bearer, 리프레시 없음(11-03)
- [x] 이벤트 `unselect_slot`·`abandon` → 만들지 않음, 이탈은 분석으로 계산. 모르는 이벤트는 그 건만 버림(11-03)
- [x] ORM·드라이버 → SQLAlchemy 2.1 동기 + PyMySQL, pymongo, 마이그레이션은 SQL 파일(11-03)
- [x] 결제 대기·만료 → 없음(11-03), venues·rooms 통합 → venues 하나(11-02), 가상 날짜 → 실제 날짜(11-03), 일러스트 값 → `art:<종류>-<색>`, 글꼴 → Noto Sans KR(11-01)

## 에이전트 사용

- 지침은 루트와 파트 폴더의 `AGENTS.md`. Codex는 저장소 루트부터 지금 폴더까지 모두 합쳐 읽고, Claude Code는 `CLAUDE.md`가 없을 때 `AGENTS.md`를 읽는다(v2.1.277 이상).
- `CLAUDE.md`나 `CLAUDE.local.md`를 만들면 Claude Code가 `AGENTS.md`를 읽지 않으니 만들지 않는다. 개인 설정은 각자 `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`에 둔다.
- 개인 기억(Claude 자동 메모리 등)은 팀에 공유되지 않는다. 팀이 알아야 할 것은 이 파일과 `docs/`에 쓴다.

## 최근 변경 (최신이 위)
- 11-07 · A · develop(당시 `97b533a`; 이후 PR #87·#89 병합)에서 B #80 병합 뒤 예약 이벤트 예외 경계를 재확인. `test_reservations.py` 58건과 F-60 문서·개인정보·중복·장애 선별 테스트 11건 통과. MariaDB 11.4.13 `spacecube_test` 전체 backend/db pytest 407건 통과 기록(PR #87 반영)을 기준에 포함했다. 사용자 확인: Linux 서버 MariaDB 11.4. FE `event_context`·검색 ID·`page_view`, 최신 배포·브라우저 흐름이 남아 #5 미완료.

- 11-07 · 공동 · PR #87 PM 코멘트 반영: 109 api1 파일럿의 생성 이벤트 10,368건에서 과거 `occurred_at`과 실제 `received_at` 분리 및 중복 0건을 확인. PM 보고: `event_daily` 32일 3,974행·재실행 신규 0, 크롤러 법정동 대응을 109에 적용했으며 별도 PR 예정. #75의 남은 작업은 FE/PM 그래프 확인.

- 11-07 · A · #75 A 시각·이벤트 경계 작업 완료. 생성기 `HistoricalRuntime`과 A `override_business_time()` 비교 테스트 24건 및 Ruff 통과. 별도 Windows MariaDB 11.4.13 `spacecube_test`에서 `backend/tests db/tests` 전체 pytest 407건 통과(Starlette 경고 1건, 69.44초); GitHub PR #86 CI의 DB·백엔드 테스트와 Ruff도 통과했고 PR #86은 develop에 병합됨(merge commit `97b533a`). A 확인: 11-07 109 api1 파일럿에서 과거 `occurred_at`·실제 `received_at` 분리, 중복 0건. DB 공간 보충·집계/CSV는 후속 PR, 그래프 확인은 #75 공동 미완료 항목.

- 11-07 · A · 동일 MariaDB 10.11.14 VM에서 MongoDB 8.0.34 테스트 서버를 함께 연결해 생성기 서비스 pytest 3건 통과. 전용 space_rental_analytics_test.generator_validation_bd7d60618758442c84f05e74b4201966에 100명·1,260세션의 이벤트 10,111건 실제 저장, 재개 시 추가 0건/중복 10,111건, 공식 validator 적용 및 121 거절 확인. MariaDB 테스트 거래는 롤백해 기존 회원 3명 유지, 공간·예약·후기 0건. Mongo 테스트 컬렉션은 DB 담당 확인용 보존, 운영 events 변경 없음.

- 11-07 · A · MariaDB VM 100.100.100.31(10.11.14)에 현재 #75 병합 커밋 2bfc5b6을 별도 복사하고 environment.yml로 Linux conda pro_1을 구성. VM 로컬 spacecube_test에서 회원·후기·A 시각·생성기·동시성 집중 pytest 88건 및 backend/db/생성기 전체 pytest 406건 통과(Starlette 경고 1건). Windows MariaDB 13.0에서 실패한 동시성 4건도 VM 실행에서 통과. 테스트 후 원격 DB 기존 회원 3명 유지, 공간·예약·후기 0건. MongoDB 8.0.34 전용 테스트 컬렉션 실저장 10,033건과 중복 재실행 0건은 별도 Windows+로컬 MariaDB 실행에서 검증했으며 운영 Mongo 컬렉션은 변경하지 않음. 팀 목표 MariaDB 11.4 실검증은 남음.

- 11-07 · A · #75 원격 테스트 환경 확인: MariaDB 10.11.14 VM의 spacecube_test에 기존 13개 표 유지, 비어 있던 기준 seed(유형 5·시설 20·지역 230)만 적용하고 기존 회원 3명은 보존. MongoDB 8.0.34 VM 복구 후 전용 space_rental_analytics_test.generator_validation_* 컬렉션에서 생성기 서비스 테스트 3건 통과. 100명·1,260세션·예약 916·취소 91·완료 825·후기 206·이벤트 10,033건 저장, 같은 실행 재개 시 추가 0건/중복 10,033건, 공식 validator 및 오류 121 확인. 초기 구성 후 SSH로 VM pro_1을 구성하고 10.11.14 전체 pytest 406건을 통과함. 이 Mongo 테스트에서 MariaDB는 Windows 로컬 13.0.2 트랜잭션 롤백으로 사용함. 테스트 Mongo 컬렉션은 DB 담당 확인용으로 보존.

- 11-07 · A · #75 브랜치에 최신 develop의 생성기 본체를 로컬 병합하고 A 시간 경계·생성기 테스트를 실행. 로컬 MariaDB 13.0.2에서 생성기+A 집중 pytest 25건 통과, Ruff 통과. 전체 pytest는 402건 통과·예약/탈퇴 동시성 4건 실패(1020 Record has changed, 50명 경쟁에서 409 수량 불일치), Starlette 경고 1건. 실제 MongoDB 저장은 CHECK_MONGO_URL 없이 실행해 미검증. 생성기는 A override_business_time() 대신 별도 HistoricalRuntime 패치를 사용하므로 계약 정리 필요.

- 11-06 · A · #75 백필 연계 지침 갱신. 기존 로컬 `override_business_time()`은 가입 입력 객체 생성·`auth_service.signup()`·`review_service.create_review()` 범위에 한정하고, 이벤트 발생 시각은 `build_document(occurred_at=...)`, 수신 시각은 실제 `get_event_time()`으로 분리한다. `SERVER_NAME=generator`는 생성 프로세스에만 지정하도록 문서화. 중복 회원·후기 재사용 기준과 B 자동 이벤트·예약 지표 오염 위험 및 필요한 내부 억제 옵션을 기록했다. A 경계·회원·후기 로컬 MariaDB 13.0 테스트 56건, 관련 비DB 테스트 31건·Ruff 통과(11-07). 최신 develop 생성기는 런타임 패치를 사용해 A override 함수와 직접 연결되지 않으므로 결합 검증은 남음.
- 11-07 · B · PR #69 PM 댓글 반영: 최신 develop을 병합하고 `/events` 요청을 `event_name`·schema version·사용자/사이트/획득/페이지/이동 문맥·상품 참조 형식으로 수정. 가상 사용자마다 다른 `X-Session-Id`와 이벤트 순번을 사용한다. Write 예약은 고유한 실제 날짜 2개 이상을 요구하고 사용자별 날짜 순환, 검색 결과 페이지 분산, 프로세스 내 겹치는 슬롯 선점 방지로 409 쏠림을 낮춘다. 기존 `run_daily.ps1`의 실행별 `logs/` CSV·HTML 출력을 문서에서 확인. 전용 pytest 32건, Ruff·format, Locust 네 클래스 목록 통과(gevent/SSL 경고 1개). 실서버 Write·실제 보고서 파일/Loki 적재는 미검증; 설치 Locust 2.43.1은 `environment.yml` 고정 2.47.0과 다름.

- 11-06 B·PM: #69에 실험 #73의 제한·기록 주의점을 반영했다. 네 페르소나 기본 조회 모드, 명시적 이벤트/예약 쓰기, 20/15/10/5명 상한·사용자당 예약 1건, 목표/실제 인원·오류·응답시간 요약을 보완했다. 가짜 응답 회귀 27건, 실제 Explorer 조회 1명·10초 12건 실패 0. A7 판정과 실제 쓰기 적재는 미검증.
- 11-07 · B · #67 테스트 환경 검증: 자체 구성한 api1(.232)·api2(.233) 테스트 VM에 Nginx 1.24와 FastAPI/Uvicorn을 같이 설치하고 API를 loopback 8000에 바인딩. develop `e7db36f` 프론트 빌드를 양쪽 테스트 VM에 배포하고 이전 릴리스를 보존. VM별 systemd encrypted credential로 DB·JWT·internal·synthetic 설정 보관. `/api/health`·읽기 전용 `/api/categories` 200, asset 1년 immutable·WebP image/webp/7일·index no-cache·404 차단·loopback stub_status 200, health 8회 후 각 VM keepalive 연결 1개를 확인. MariaDB primary(.212)는 SSH·DDL·쓰기 없이 health와 GET categories만 확인. MongoDB 주소 미제공으로 health 본문은 `degraded`/`mongo: down`. 최신 develop 통합 후 verify.ps1 통과(Ruff·115 파일 포맷·pytest 451·FE 67·린트·색 검사·빌드; 기존 경고 2건). HAProxy 장애 제외/복귀는 #66에서 확인.

- 11-07 · B · PR #67 PM 코멘트 확인 후 전용 워크트리 `.worktrees/pr-67-nginx`의 `feat/B-nginx`에서 origin/develop 1583778 병합·STATE 충돌 해결. 최신 A·DB·생성기 기록과 기존 Nginx 검증 이력을 보존. 로컬 FastAPI upstream keepalive 16·유휴 4초 및 WebP MIME 명시, 서버별 assets/사진 캐시·없는 파일 404·keepalive·#66 장애 시험 확인 절차 작성. verify.ps1 전체 통과(exit 0): Ruff 115파일·pytest 451건·FE 단위 67건·린트/색 검사/빌드. 기존 Starlette·FE 조건문 경고 각 1건. git diff --check 통과. 수정본 nginx -t·실제 HTTP·api1/api2 적용·#66 장애 시험·E2E는 미실행. SSH 접속 정보와 VM 소유자 확인 대기, Draft 유지.

- 11-07 · B · 사용자 승인으로 #54 nginx 후보안 커밋·푸시·Draft PR 준비. 제목 [B] #54 nginx 설정 초안, develop 대상·Refs #54로 연결. 커밋 전 verify.ps1에서 Ruff 린트·90파일 포맷·pytest 362건 통과(경고 1); 프론트 verify는 이 워크트리 의존성 미설치로 run-s를 찾지 못해 실패(exit 1). Nginx 원본 VM 문법 검사 및 git diff --check 통과. HTTP·HAProxy·실제 적용은 미검증이며 비교·검토용 초안 유지.

- 11-07 · B · 사용자 제공 VM에 SSH 접속해 #54 원본 Nginx 후보 검사. Ubuntu 24.04.4·Nginx 1.24.0, 원본 SHA256 일치 확인. /tmp의 별도 최상위 설정에서 원본 후보를 include한 sudo nginx -t 통과(exit 0); 포트·경로·upstream 치환 없음. 기존 Nginx active 및 80번 listener 유지 확인, 임시 디렉터리 삭제·SSH 종료. 설정 설치·서비스 reload·패키지 설치 없음. HTTP·실제 API·HAProxy·장애 복구 시험 및 기존 운영 설정 전체와의 충돌 검사는 미실행. 접속 비밀번호는 파일에 저장하지 않음.

- 11-06 · B · #54 Nginx 공통 후보안: `infra/nginx/spacecube.conf`를 api1·api2용으로 수정하고 `infra/nginx/README.md`를 로컬 VM 기준으로 정리. HAProxy는 서버 선택, Nginx는 Vue 정적 파일과 `127.0.0.1:8000` 전달을 맡음. `/api/internal`·`/api/metrics` 차단, 로컬 `stub_status`, 개인정보를 남기지 않는 JSON 접근 로그 반영. `git diff --check`와 정적 검토 통과; Windows에 Nginx가 없어 `nginx -t` 미실행, HTTP·실제 VM 배포 미검증. `127.0.0.1:8000`과 `mon`의 8000 직접 scrape 표기 불일치 확인 필요.
- 11-06 · B · nginx 작업 트리 feat/B-nginx에 최신 origin/develop(9b9b223, 22개 커밋)을 fast-forward 반영. 기존 미커밋 설정은 복원하고 문서 충돌은 최신 진행 상태를 유지해 정리. #14 종료·#54 이관 및 HAProxy 정문 → 서버별 Nginx 구조 확인. spacecube.conf는 이전 정문 후보안이라 서버용 수정 필요. 기존 변경 원본은 nginx-develop-sync-2026-11-06 stash에 보존. 이번 작업은 Git 동기화·파일 확인이며 실행 테스트·배포 없음.

- 11-07 · B · PR #76 PM 후속으로 `_event_product()`를 이벤트 래퍼 내부에서 실행하도록 `product_factory`를 전달. 예약·충돌·취소 각 API가 상품 조립 실패에도 201·409·200과 커밋 결과를 유지하는 회귀, HistoricalRuntime에서 상품 팩토리 미호출 및 MariaDB 생성기 전체 흐름을 운영 상품 빌더 실패 상태로 검증하는 테스트를 추가. `verify.ps1` 통과: Ruff 109파일, pytest 434건, FE 단위 67건·린트·색 검사·빌드. 기존 Starlette 사용 중단·FE 조건문 린트 경고 각 1건. 브랜치 `fix/B-issue5-product-factory`, 미커밋·미푸시, PR 후속 리뷰 대기.

- 11-07 · 공동(B) · 사용자 승인으로 `fix/B-generator-db-race`와 재검증 기록 커밋을 푸시하고 develop 대상 PR #79([B] F-62 생성기 검증 시 공유 테스트 DB 경합 방지)를 생성. Closes #78 및 앞서 확인한 로컬 검증 결과를 본문에 포함. jinsan02·naturedevworks 자동 리뷰 요청과 open·비초안·충돌 없음 상태 확인. GitHub 연결 도구의 생성 권한 부족 및 기존 gh 인증 만료는 정상 Git 인증을 통한 CLI 실행으로 처리했으며 인증정보는 출력·파일 저장하지 않음. 이번 게시 작업에서 제품 코드 수정·테스트 재실행·머지 없음. 원격 CI 결과는 후속 확인.

- 11-07 · 공동(B) · 사용자 요청으로 `fix/B-generator-db-race`의 경합 수정 커밋 ef39125(#78)를 로컬 MariaDB spacecube_test에서 재검증. `python -m pytest tests -q` 29건 통과, 재가입 대상 pytest 두 프로세스를 각각 5회 실행해 총 10회 통과하고 실제 잠금 대기 후 진행 확인. `verify.ps1` Ruff 98파일·pytest 407건(예약 50요청 동시성 포함)·FE 단위 67건·린트/색 검사/빌드 통과. backend 폴더 직접 pytest의 잠금 fixture 적용과 재가입 1건 통과도 확인. 기존 Starlette 사용 중단 경고·FE 조건문 린트 경고 각 1건. DDL 검사·E2E·원격 CI는 미실행. 제품 코드 수정 없이 검증 기록만 갱신하고 develop 대상 PR 제목·본문을 채팅으로 제시. 커밋·푸시·PR 생성 없음.

- 11-07 · 공동(B) · 사용자 요청으로 #78의 공통 테스트 DB 잠금·29건 회귀·verify/CI 경로·문서를 `fix/B-test-db-lock` 로컬 커밋 대상으로 확정하고 develop 대상 PR 제목·본문을 준비. 최종 verify.ps1 pytest 407건·FE 67건·Ruff/린트/빌드 및 병렬 재가입 두 프로세스 5+5건 통과 결과를 사용한다. 이번 커밋 준비에서는 제품 코드 변경·테스트 재실행 없음. 생성기 PR #77과 분리하며, 잠금 미적용 checkout·pytest 외 DDL 작업은 보호하지 못하는 범위를 본문에 명시한다. 푸시·PR 생성은 하지 않음.

- 11-06 · 공동(B) · 사용자 요청으로 최신 develop f387df2에서 `fix/B-test-db-lock` 생성, 원인·완료 조건을 이슈 #78에 등록. 공통 conftest/session 잠금·매 테스트 전 소유권 확인·제한 시간·비밀값 없는 오류·연결 종료 해제를 추가하고 tests/ 공통 회귀·verify/CI 탐색 경로·기여 안내를 갱신. 회원 서비스·API 응답·DDL·패키지는 변경하지 않음. 회귀 29건 통과, 수정 전 1213→1305→500이 나던 동일 재가입 테스트 두 프로세스가 수정 후 각각 5건 통과하며 한쪽의 실제 대기/해제 후 진행 확인. 첫 전체 검사에서 새 하위 프로세스 출력 테스트 1건이 Windows CP949/UTF-8 차이로 실패(406건 통과)해 UTF-8 출력·해석을 고정했고, 이후 회귀 29건 및 verify.ps1 전체 407건·FE 단위 67건·Ruff 98파일·린트/빌드 모두 통과. 기존 Starlette 사용 중단·FE 린트 경고 각 1건. backend/ 폴더에서 공통 fixture 탐색도 확인. DDL 검사·E2E·원격 CI는 미실행. 커밋·푸시·PR은 아직 하지 않음.

- 11-06 · B · 사용자 요청으로 생성기 커밋 `8c9aef4`를 `feat/B-F-62-generator`에 푸시하고 develop 대상 PR #77(`[B] F-62 과거 데이터 생성기 구현 및 재실행 중복 방지 (#75)`)을 생성. 검토한 본문에 최종 verify.ps1 399건·FE 67건·지정 MongoDB 생성기 21건 결과와 공유 테스트 DB 병렬 검증 500 재현·별도 방지 PR 계획을 명시. DB·FE 후속이 남아 Refs #75·#19로 연결하고 자동 종료하지 않음. 코드 변경 없이 기존 검증 결과를 사용했으며 이 등록 기록만 추가함.

- 11-06 · B · 사용자 요청으로 #75 생성기 구현·테스트·기준 문서 변경을 `feat/B-F-62-generator`의 로컬 커밋 대상으로 정리하고 develop 대상 PR 제목·본문을 준비. 최종 verify.ps1 399건·FE 67건 및 실제 MongoDB 생성기 21건 검증 결과를 사용하며, 이번 커밋 준비에서는 코드 변경·테스트 재실행 없음. 공유 테스트 DB 병렬 실행의 1213→1305→500 방지 코드는 별도 후속 PR로 분리한다. #75는 DB 집계·CSV·공간 보충·api1 운영 적재/FE 결과 확인이 남아 자동 종료하지 않는다. 푸시·PR 생성은 하지 않음.

- 11-06 · B · 사용자 요청으로 회원 재가입 500 원인 진단. 제품 코드 변경 없이 임시 진단 훅으로 단독 40회·원래 순서 포함 261건 통과를 확인하고, 같은 로컬 spacecube_test를 두 프로세스가 공유하는 병렬 실행에서 두 차례 동일 테스트의 재가입 500을 재현. DBAPI 원인 1213(교착상태) 뒤 SQLAlchemy SAVEPOINT 롤백 1305가 이어지는 예외 체인과 InnoDB의 users.uq_users_email 상호 잠금 대기를 확인. fixture는 테스트 전체 외부 트랜잭션+요청별 create_savepoint라 서비스 commit이 실제 잠금을 해제하지 않으며, deadlock의 전체 롤백 뒤 savepoint가 사라진다. #76 코드와 호출 경로는 다르지만 검증이 동일 DB에서 겹치면 간접 영향 가능. 최초 실패 예외는 미보존이므로 최초 건도 같은 원인이었다는 것은 추정. 당장은 공유 DB 검증을 순차 실행하고, 테스트 공용 잠금 또는 DB 분리는 A/공동 후속으로 권고. 진단 보고서 logs/signup-root-cause.json, 잠금 요약 logs/innodb-signup-deadlock.json. 이 병렬 재현은 의도한 진단 실패이며 기존 최종 verify.ps1 통과 기록과 구분한다.

- 11-06 · B · #75 커밋 전 verify.ps1 최종 재검사 전체 통과: pytest 399건, FE 단위 67건·린트·빌드, Ruff 104파일. 첫 통합 실행에서 기존 회원 탈퇴 후 같은 이메일 재가입이 500으로 한 번 실패했으나 단독 1건·회원 묶음 15건·전체 399건 재실행은 모두 통과. 제품 회원 코드는 수정하지 않았으며, 이후 공유 테스트 DB 병렬 실행에서 같은 재가입 500과 1213→1305 예외 체인을 재현함(최초 실패와의 동일성은 추정). MongoDB 실저장 검증은 전용 컬렉션의 10,089건·재개 추가 0건 보고서를 유지. 브랜치만 생성했고 커밋·푸시는 하지 않음.

- 11-06 · B · #75 PM 결정대로 `feat/B-F-62-generator`에 생성기 CLI·세션 계획·A/B 서비스 연결·시각/관측 컨텍스트·manifest/state·MongoDB 적재/중복 대조를 구현. B 예약 복구 조회와 실행 소유 가상 예약 한 건 완료 처리를 추가하고 기존 API·DDL은 유지. 기본 100명 파일럿을 포함한 생성기 21건 통과. 최종 verify.ps1 전체 통과(pytest 399건·FE 67건·Ruff·린트·빌드). 사용자 지정 MongoDB의 전용 테스트 컬렉션에서 공식 validator·TTL·UNIQUE 적용 후 이벤트 10,089건 저장, 동일 실행 재개 0건 추가·잘못된 문서 121 거절 확인. MariaDB는 spacecube_test 외부 트랜잭션 롤백, 원격 검증 결과는 DB 확인용으로 보존. 보고서는 logs/generator-validation-2fb310d4-928e-5e7a-8cbf-577df43591a9/report.json. api1 운영 적재·집계·CSV·FE 그래프는 별도이며 커밋·푸시는 아직 하지 않음.

- 11-06 · B · 사용자 요청으로 #5 B 수정 브랜치 `fix/B-issue5-reservation-events`의 원격 푸시·develop 대상 PR 등록 진행. 준비한 제목·본문과 기존 검증 결과를 사용하고 `Refs #5`로 연결해 전체 이슈는 자동 종료하지 않음. 생성기 작업 트리는 그대로 유지.

- 11-06 · B · 사용자 요청으로 #5 B 수정 4파일을 `fix/B-issue5-reservation-events`에서 커밋하고 develop 대상 PR 제목·본문 초안 준비. 검증 결과는 위 수정의 최종 실행 기록을 사용하며 이번 커밋 준비에서는 코드 변경·테스트 재실행 없음. #5는 FE·DB 후속이 남아 PR에서 `Refs #5`로 연결하고 자동 종료하지 않음. 생성기 미커밋 작업은 포함하지 않으며 푸시·PR 생성은 하지 않음.

- 11-06 · B · #5 최종 검증: `verify.ps1`을 pro_1 실행기로 실행해 Ruff 93파일·로컬 MariaDB `spacecube_test` pytest 381건·FE 단위 67건·린트·빌드 모두 통과. 최종 예외 주입·문맥 복원 3건도 별도 통과. 실제 Uvicorn/JWT/Postman 7요청/15검증 및 임시 데이터 정리 통과. 기존 Starlette·FE 린트 경고 각 1건. MongoDB 실저장·배포·브라우저 E2E는 미실행. 커밋·푸시·PR은 하지 않음.

- 11-06 · B · #5 최신 PM 결정(issuecomment-6683005424)에 따라 `_log_reservation_event()` 전체에 예외 경계를 적용하고 기존 문맥 복원 유지. 수정 전 model_dump·log_event 예외 주입에서 500 재현, 수정 후 로컬 MariaDB `spacecube_test`에서 201·예약/칸/결제 저장·성공 카운터 회귀 2건 및 문맥 복원 1건 통과. 예약·동시성 65건, Ruff, 실제 Uvicorn/JWT/Postman 7요청/15검증·임시 데이터 정리 통과. 최신 develop `f387df2`의 별도 작업 트리 `.worktrees/fix-B-issue5-reservation-events`에서만 수정하며 `feat/B-F-62-generator` 미커밋 작업은 포함하지 않음. #5 전체 종료는 FE·DB 후속 통합 후 담당자가 판단.

- 11-07 · DB · 사용자 재요청으로 로컬에 보존한 F-61 크롤러 코드·문서·테스트와 실행 환경 기록을 같은 기능 브랜치에 다시 커밋·푸시. 크롤러 오프라인 pytest 17건, Ruff 린트·포맷, 프론트 verify 통과; 전체 `verify.ps1`은 `CHECK_DB_URL` 미설정으로 pytest 실패. 실제 외부 수집·`venues` 등록은 미검증이고 이슈 #10은 진행 상태로 유지.

- 11-07 · DB · 사용자 요청으로 `feat/DB-F-61-crawler`의 원격 HEAD를 `d59c777`에서 두 커밋 전 `f387df2`로 `--force-with-lease` 복원. 브랜치는 유지하고 `156e1d5`·`d59c777`의 파일 변경은 로컬 스테이징에 보존했다. PR #81은 이미 닫힌 미병합 상태이며, `develop`은 변경하지 않았다.

- 11-07 · DB · F-61 브랜치 추가 기록 커밋 전 `verify.ps1` 실행: Ruff 린트·99파일 포맷 확인, 프론트 verify는 통과. 전체 pytest는 `CHECK_DB_URL`이 설정되지 않아 DB 연동 테스트 다수가 설정 단계에서 실패해 검증 명령은 종료 1. 같은 조건의 전체 검증은 반복하지 않고, 앞서 크롤러 오프라인 pytest 17건 통과 결과를 유지. 루트 README의 기존 빈 줄 변경은 보존.

- 11-07 · DB · 사용자가 기존 루트 `.env`를 비운 뒤 설정 형식을 요청해 `backend/.env.example`의 키·기본값을 루트 `.env`와 `backend/.env`에 작성. 두 파일은 Git 제외 대상이며 실제 DB_WRITE_URL·MONGO_URL·INTERNAL_API_KEY·JWT_SECRET 등 비밀값은 비어 있어 접속·API 검증은 미실행. 기존 연결 값은 복원할 수 없음.

- 11-07 · DB · 공식 Miniconda를 사용자 폴더에 설치하고 `environment.yml`로 `pro_1`(Python 3.12.16)을 생성. `python -m pip check` 충돌 없음, 크롤러 오프라인 pytest 17건 통과, Ruff 전체 린트와 99파일 포맷 확인 통과. 전체 `verify.ps1`은 로컬 `spacecube_test`의 `CHECK_DB_URL`이 없어 실행하지 않음. 실제 외부 수집·API 등록은 아직 미실행.

- 11-07 · DB · F-61 브랜치 커밋 전 검증: 작업 폴더 Ruff 0.17.3으로 전체 Python 99파일 린트·포맷 확인 통과, 프론트 `npm run verify`는 설치된 Node 24를 명령에 지정해 린트(경고 1·오류 0)·단위 67건·빌드 통과. `pro_1`이 없어 `verify.ps1`의 pytest는 실행하지 못함. 이슈 #10의 실제 수집·15~20개 API 등록은 미완료로 유지.

- 11-07 · DB · 사용자 요청으로 API를 제외한 운영 저장소 쓰기 시험 실행. 루트 `.env`의 `spacecube` MariaDB와 `crawl` MongoDB에 검증용 각 1건을 커밋·삽입하고 재조회 결과를 확인한 뒤 삽입한 각 1건만 삭제했다(`WRITE_READBACK_OK mongo=1 mariadb=1`, `CLEANUP_OK mongo=1 mariadb=1`, 종료 0). `pro_1`이 없어 설치된 동일 버전 PyMongo·PyMySQL로 일회성 진단을 했으며 진단 파일은 제거. 실제 사이트 크롤링·`venues` API 등록·pytest는 실행하지 않음.

- 11-07 · DB · 요청 범위를 API 제외한 저장 검증으로 좁혀 `db/tests/check_crawler_storage.py` 추가. `spacecube_test`가 아닌 MariaDB URL은 쓰기 전에 거부하고, MongoDB `crawl.crawl_raw`와 MariaDB `crawl_jobs`에 각 1건을 저장·재조회한 뒤 해당 건만 정리하도록 구성. 현재 루트 `.env`는 애플리케이션 `spacecube`이고 `pro_1`·`backend/.env`가 없어 실제 스크립트 실행은 대기.

- 11-07 · DB · F-61 실제 적재 요청에 따라 실행 환경 재확인. 새 루트 `.env`의 `DB_HOST`·`MONGODB_URI`는 각각 MariaDB·MongoDB에 TCP 연결되며 공간 대여 DB·`crawl` DB를 가리킨다. 크롤러가 읽는 `backend/.env`의 `DB_WRITE_URL`·`MONGO_URL`·`INTERNAL_API_KEY`, `pro_1`, 실행 중인 내부 API는 여전히 없다. 외부 수집·MongoDB `crawl_raw`·MariaDB `crawl_jobs`/`venues` 적재는 시작하지 않았고 실행 환경 제공을 요청함.

- 11-07 · DB · F-61 실행기 루트 모듈 경로·허용 사이트의 비표준 포트 차단·파서 실패 시 조회 건수 기록을 점검하고 회귀 테스트를 추가. 작업 폴더의 Ruff 0.17.3으로 전체 98개 Python 파일 린트·포맷 확인 통과. `pro_1`과 `backend/.env`가 없어 pytest·실제 수집/등록은 실행하지 못함. 실행 결과의 조회·등록과 공개 API 전체 공간 수 확인 방법을 크롤러 README에 기록.

- 11-06 · DB · 사용자 요청으로 최신 develop `f387df2`에서 `feat/DB-F-61-crawler`를 만들고 F-61 크롤러 코드 작성. 기존 다른 경로의 Python 파일 3개는 해시가 같아 복사하지 않고 요청 클라이언트·스페이스클라우드 파서를 재사용. 쉐어잇 구조화 데이터 파서, 사이트별 robots·3초 간격·실행당 상세 20건, 유형/지역 매핑, MongoDB `crawl_raw`와 MariaDB `crawl_jobs`, B 내부 API 업서트·재시도, 생성 이름·`art:` 3개와 오프라인 테스트를 추가. 두 경로 모두 과거 표본 `crawler/data`가 없음. 현재 PC에 `pro_1`과 `backend/.env`가 없어 Ruff·pytest·실제 DB/API/사이트 단건 검증은 대기. 기존 README 미커밋 변경은 보존.

- 11-06 · B · 사용자 요청으로 `feat/B-F60-events`를 푸시하고 GitHub CLI에서 Draft PR #74를 develop 대상으로 생성. B 변경만 포함하며 A #72 의존성과 서버 세션 ID·원격 MongoDB validator 후속 항목을 PR 본문에 명시. 이전 통합 검증 결과를 그대로 첨부했고 이번 PR 작성 작업에서는 테스트를 재실행하지 않음.

- 11-06 · B · A #72+B 임시 통합 브랜치에서 최종 `verify.ps1` 전체 통과: Ruff 93파일·pytest 375건·FE 67건·린트/빌드. 잘못된 브라우저 문맥도 유효한 세션 헤더와 함께 보내 예약 응답을 유지하는지 별도 1건 통과. B 전용 브랜치와 A+B 통합 테스트 브랜치를 로컬에 분리 보존했으며 원격 푸시·PR은 아직 하지 않음. 지정 MongoDB의 문맥 null 거절(121)과 A의 세션 ID 보완 미반영은 후속 항목으로 유지.

- 11-06 · B · #60·#72 요청에 따라 예약 결과 3종을 새 이름과 `products` 키워드로 전환. primary 공간명·확정 예약 조건·시간당 금액(취소는 저장 총액/시간)·KST 시각을 전달하고 선택적 `event_context`는 기록 후 복원. 본문 없는 취소·재시도 중복 방지·동시성 유지. `test/B-F60-integration`에서 A d75deea와 관련 pytest 77건·전체 pytest 375건 통과. 최초 정렬 예상값 오류 수정 후 통과. 실제 JWT/Uvicorn·Postman 7요청/15검증과 지정 원격 MongoDB 결과 3종 저장·같은 ID 재적재 0건 추가·이번 가상 데이터 정리 확인. 원격 validator는 문맥 null을 121로 거절하며 변경하지 않았고 A 세션 ID 보완도 미반영. 전체 verify 최초 실행은 프론트 run-s 미설치로 실패했으나 기존 잠금파일로 의존성 설치 후 별도 FE verify 67건·린트/빌드 통과. 비밀값은 실행 환경에만 전달. 푸시·PR·배포는 하지 않음.

- 11-06 · A · 공식 `mongo_init.js`를 전용 MongoDB `space_rental_analytics_test`에 적용해 strict validator·event_id 고유 인덱스를 확인. 실제 검색 HTTP 202와 `log_event` 서버 결과 각 1건이 `events.log`·MongoDB에 저장되고 URL query/fragment·자유 문자열이 제거됨을 확인. 같은 로그 2회 재적재는 매회 중복 2건으로 처리되고, 생성 문서 2건은 삭제. MongoDB 장애 HTTP 202·파일 기록 실패 503 검증. 헤더 없는 서버 결과의 `session_id`를 `server-<request_id>`로 채움(#60 PM 결정). 관련 pytest 24건·전체 375건, Ruff·FE verify 67건/빌드 통과. B 이벤트 이름·상품과 FE ID/예약 문맥 통합은 미완료.
- 11-06 · A · 공식 `docs/db/mongo_init.js`와 문서 조립 코드를 정적 대조해 15종 이름·서버 3종·빈 상품 허용 4종·최상위 필수 필드·strict/고유 인덱스 일치를 확인. PM #72의 비활성 공간 후기 1건 때문에 정상 검색 이벤트까지 400으로 버려지는 사례를 API 계층에서 재현(혼합 400·추가 로그 0건). 기존 계약은 미허용 이벤트 이름만 `ignored`이며 필수 상품 오류는 400이므로, 선택적 건너뛰기는 확정하지 않고 정책 결정을 기다린다. 항목 순서 양쪽 회귀 테스트를 추가했다.

- 11-06 · 공동(PM 요청) · MongoDB 초기화를 새 구조 하나로 정리. 옛 `docs/db/mongo_init.js`(`spacecube.user_events`)를 삭제하고 #68의 `mongo_init_2.js`를 `mongo_init.js`로 이름 변경(compose·CI 자동 실행 경로 그대로). `db/tests/check_mongo_init.js`를 새 `events`·`event_daily`·`crawl_raw` 기준 24건으로 다시 씀. 로컬에서 mongosh·Docker를 쓰지 않아 실행 검증은 CI로 확인. `산출물_04` 8절·백엔드 A 문서의 `user_events` 설명은 #63에서 DB·A가 고침

- 11-06 · A · F-60 최신 FE PR #59 요청과 A 스키마를 대조해 상품 이름·가격 위조 입력을 거부하고 정상 `product_id`의 서버 스냅샷 보강을 각각 검사하도록 이벤트 테스트 수정. 관련 pytest 21건, 전체 verify Python 372건·Ruff 92파일·FE 62건/빌드 통과. 처음 1045는 실행 중인 `SpacecubeTestMariaDB1` 대신 다른 인스턴스 설정을 읽은 결과였으며 올바른 로컬 `spacecube_test` 설정으로 재검증했다. 별도 원격 테스트 DB 임시 validator에서 15종 15건 저장·동일 ID 재삽입 15건 중복 제외·임시 데이터 정리 확인. 로컬 Mongo 미기동·DB 공식 초기화 #63·B 구형 호출·FE 지역/시설 ID와 예약 문맥 남음. 현재 FE는 상품 이벤트당 한 ID이며, 여러 ID는 B 일괄 조회 계약 전까지 지원하지 않음. 기존 stash와 미추적 항목 보존.

- 11-06 · A · #5·#48·#60 및 PR #58·#59 최신 결정을 반영해 F-60 실행 코드의 대상과 문서 구조를 `space_rental_analytics.events`로 전환. FE 12종·서버 3종, 필수 문맥, 상품 스냅샷, URL query/fragment 제거, 제한된 properties, 파일 우선·새 형식 로그 재적재를 구현. 기존 7개 `log_event` 인자는 보존하고 `products` 키워드 선택 인자만 추가. 공통 계약·이벤트 pytest 21건, Ruff 92파일, FE 단위 56건·린트·빌드 통과. 전체 verify는 로컬 `spacecube_test` 계정 인증 1045로 DB 테스트가 막혀 실패(4 failed, 59 passed, 299 errors); 로컬 Mongo 미기동으로 새 validator 실제 저장 미검증. B 구형 호출/상품값·FE PR #59 남은 작업·DB validator가 연결되기 전까지 F-60 완료 아님. stash·DB/FE/B 구현 파일과 기존 미추적 임시 항목 보존.

- 11-06 · A · PR #58 새 `events` 명세와 #5·#48 합의를 대조. 기존 이벤트 payload는 형식 확인된 코드·날짜·정수만 남기고 자유 문자열을 제외하며, `events.log` 실패 문서를 MongoDB 대기열에도 보내지 않도록 보강. 신규 `test_events.py`에서 개인정보·혼합 이벤트·파일 실패를 검증. `verify.ps1` 통과: Ruff 91파일, pytest 357건, FE 단위 56건·린트·빌드. Starlette·기존 FE lint 경고 각 1건. 필수 화면 문맥을 B 서버 이벤트에서 채우는 정책 미정으로 새 MongoDB 전환·실저장·재적재는 보류. stash·DB/FE/B 코드는 변경하지 않음.
- 11-06 · B · #54 정문 HAProxy 설정 초안: 별도 `chore/B-haproxy-conf` 브랜치에 gw:80 라운드로빈·/api/health 2초 능동 확인·내부 경로 차단·8404 지표/통계 설정과 README 작성. 실제 VM 검증·PM 안 비교 후 채택 대기.

- 11-06 · FE · 사용자가 승인한 CCL 참고 사진 25장을 더해 5개 유형별 8장, 총 40장을 맞춤. 모두 1200×780 WebP(약 34~167KB, 합계 3.29MB). `RoomArt.vue`가 정적 `/photos/...` 경로에서 유형별 사진을 venue ID 해시로 고르고, 상세 갤러리는 슬롯 번호로 별도 선택. 사진 로드 실패 시 일러스트로 대체한다. 실제 등록 공간 사진이 아님을 이미지와 푸터에 표시하고, 40개 출처·저작자·라이선스·편집 기록을 파일 원장과 사용자용 크레딧 페이지에 연결. 기존 `art:` API·DB 계약 변경 없음. `npm run verify`: 린트 오류 0(기존 경고 1), 단위 62건, 빌드 통과. E2E는 74개 결과가 모두 출력(성공 67, 조건부 건너뜀 7)됐으나 CLI가 결과 요약 없이 70초간 종료되지 않아 중단, 전체 명령 통과로 집계하지 않음. Playwright 브라우저에서 상세 사진·배지·푸터 링크와 크레딧의 40개 이미지(전부 1200×780), 출처 링크 40·라이선스 링크 40 확인.

- 11-06 · FE · 사용자 요청으로 Wikimedia Commons CCL 사진 후보를 유형별 3장씩 15장 수집, 파일별 라이선스·저작자·원본·변경 내역을 `frontend/public/photos/SOURCES.md`에 기록. README의 크기 기준에 맞춰 1200×780 WebP로 통일하고 얼굴·상호·간판·화이트보드 글씨를 검토, 카페 2장·강의실 1장·파티룸 1장의 식별 글자를 생성형 편집으로 제거. [후보 미리보기](docs/사진_후보_미리보기_2026-11-06.jpg) 추가. 기존 `art:` UI·API는 그대로이며 실제 공간 사진으로 연결하지 않음. 이미지 크기 15장 확인, 프론트 테스트는 실행하지 않음

- 11-06 · B · #50 병합 후 최신 origin/develop `b6a97c6`에서 이슈 #45 브랜치 `feat/B-F-40-review-ids` 작업. `reservation_service`의 목록은 본인 현재 페이지 ID만 A `review_repo.get_review_ids`에 한 번 넘기고, 상세는 소유권 확인 후 해당 ID를 넘기도록 연결. 미작성 null·작성/소프트 삭제 ID 유지, 비활성 공간 이력, 타인/없는 예약 같은 404, 빈 페이지 SQL 0회·일반 페이지 후기 SELECT 1회를 MariaDB 테스트 8건으로 추가 검증. 실제 Uvicorn/JWT/Postman 7요청/15검증과 추가 HTTP 후기 생성·삭제·목록/상세 ID 유지·중복 작성 409 확인, 임시 후기/예약 정리. `verify.ps1`: Ruff 90파일·Python 362 passed·FE 56 passed·린트/색 검사/빌드 통과(exit 0); 기존 Starlette 및 Playwright 조건문 경고 각 1건. A 소유 코드·프론트 코드는 수정하지 않음. api1·실 replica·브라우저 E2E 미검증. PR 생성·CI·리뷰 대기.

- 11-06 · DB · F-60 참고용 `docs/db/events_event_daily_컬렉션_속성정리_v1.md` 추가. events 15종·사용자/페이지/가격·테스트/서버 구분·365일 TTL, event_daily 속성·복합 고유 인덱스를 정리. 별도 Compass DB의 설정 기록이며 기존 user_events/API 계약 변경이나 집계 구현을 의미하지 않음. 원본 파일 해시 일치·문서 공백 검사 통과. verify.ps1은 pro_1 환경 부재로 ruff·pytest를 찾지 못하고 Node 활성 버전이 없어 실패; 실행 코드 변경은 없음.

- 11-06 · B · #49 병합 확인 후 #50 전용 worktree feat/B-F-04-withdraw-race에서 PM 원격 1676499를 fast-forward하고 develop 55ebd23 병합. STATE·예약 리포지토리/서비스·테스트 README·B 명세 5파일 충돌 해결. #50의 create_reservation·_lock_active_user·count_cancellable AST와 #49의 조회/취소/완료 함수 AST를 각각 보존했으며 양쪽 동시성 테스트 함수 누락 없음 확인. 관련 MariaDB pytest 101 passed(예약/탈퇴 양방향·오래된 스냅샷·롤백 재잠금·실패/재시도 뒤 잠금 해제·50건 예약 경쟁·동시 취소·완료 배치), 실제 Uvicorn/JWT/Postman 7요청/15검증 통과 및 임시 데이터 정리. verify.ps1 전체 Ruff 90파일·Python 354 passed·FE 56 passed·린트/색 검사/빌드 통과(exit 0). 기존 Starlette·FE 조건문 경고 각 1건. lock 파일 동일성 확인, 기존 프론트 의존성 재사용. A 공통/회원·라우터·스키마·배치·Postman·FE는 최신 develop 내용 그대로이며 루트 #46 STATE 미커밋 변경 및 #49 작업 트리 보존. 실제 api1 배포·cron·브라우저 E2E는 미실행, #45 후기 ID 실제 연결은 #50 병합 뒤 별도 후속.

- 11-06 · B / A 연계 · #38 동시성 변경을 최신 origin/develop `bdd6dea`와 대조. 예약 전 회원 행 잠금·활성 재확인, 슬롯 충돌 롤백 뒤 재잠금, `count_cancellable()` 최신 행 읽기 구현. A·B 시각을 고정하고 실제 회원 인증 의존성 조회를 양쪽에서 완료한 후 예약/탈퇴 선행 경합, 오래된 스냅샷, 검증/결제 실패 및 재시도 200 뒤 잠금 해제를 독립 MariaDB 연결로 검증(신규 7건). `verify.ps1` 전체 통과: Ruff 85파일·pytest 310건·FE 단위 55건/린트/빌드. 실제 Uvicorn·Postman 4요청/8검증 및 DB 원자 저장·임시 데이터 정리 통과. 기존 Starlette·FE E2E 조건문 경고 각 1건. 백필과 #49 코드는 이번 범위에 포함하지 않으며 #38 전체 종료는 하지 않음.

- 11-06 · B · 사용자 지시에 따라 PR #49 전용 worktree에서 원격 1d0bf5d를 fast-forward한 뒤 develop 3a729f2를 병합. 리포지토리·서비스·라우터·스키마·테스트·HTTP 검증기·README·Postman 정의·STATE 13파일의 충돌을 양쪽 기능 보존으로 해결. 공통 예약 생성 함수 AST 동일성을 확인하고 #49 취소/완료 함수와 develop 목록/상세 함수를 결합, 취소 이벤트 category 수정을 유지. 기존 SQL 취소 fixture를 실제 취소 API로 바꾸고 취소 뒤 목록 항목과 상세 응답 일치 검증. Postman은 목록/상세 뒤 마지막에 취소하도록 order 5000으로 조정해 7요청/15검증 통과, 실제 MariaDB 11.4.13 환불·칸 반환·카운터·events.log category/단 1회 기록·임시 데이터 정리 확인. 관련 pytest 94 passed, verify.ps1 전체 Ruff 90파일·Python 347 passed·FE 56 passed·린트/색 검사/빌드 통과(exit 0). 기존 Starlette·FE 조건문 경고 각 1건. lock 파일 동일성 확인 후 기존 프론트 node_modules를 junction으로 재사용. A·FE 파일은 upstream과 동일하며 수동 변경 없음, 루트 #46의 기존 STATE 미커밋 변경과 #50 worktree 보존. 실제 api1 배포·cron·브라우저 E2E는 미실행. #49 푸시/CI 확인 뒤 PM 병합, 이후 #50 → #45 순서 유지.

- 11-06 · B · 사용자 요청으로 PR #49 보완 커밋 대상 6개 파일 확인: 취소 서비스, 예약 회귀 테스트, HTTP 검증기, 테스트 README, B 명세, STATE. 커밋 메시지는 `[B] F-34 예약 취소 이벤트 유형 기록 보완`, 원격 대상은 `origin/feat/B-F-34-35-reservations`. 직전 verify.ps1(백엔드 324건·프론트 55건·Ruff·린트·빌드) 및 실제 HTTP/Postman 5요청/11검증 통과 이후 코드 추가 변경 없음. 루트 #46 브랜치의 기존 STATE 변경은 보존하며 병합 순서는 #46 → #49 → #50 유지.

- 11-06 · B · PR #49 PM·FE 코멘트 확인 후 전용 worktree `.worktrees/feat-B-F-34-cancellation`의 `feat/B-F-34-35-reservations`(HEAD `2f7817f`)에서 `reserve_cancel_ok.category` 누락 수정. 기존 `venue_repo.get_booking_info()`를 같은 primary 트랜잭션에서 재사용하며 비활성 공간도 포함하고 커밋 뒤 이벤트를 기록. 활성/비활성 × 유형 5개 회귀 10건 추가, 실제 HTTP 검증기에 events.log의 category·venue_id·reservation_id·합성 표시·이벤트 1회 검증 추가. 로컬 MariaDB 11.4.13 spacecube_test 관련 pytest **88건**, verify.ps1 전체 **324건·Ruff 87파일·프론트 55건·린트·빌드 통과**, 실제 Uvicorn·JWT·Postman **5요청/11검증 통과**, 임시 데이터 정리 확인. 기존 Starlette deprecation 및 FE E2E 조건문 린트 경고 각 1건. 프론트 lock 파일 일치 확인 후 기존 node_modules를 임시 junction으로 재사용. B 명세·테스트 README 갱신. 루트 #46 브랜치와 기존 STATE 미커밋 변경 보존. 커밋·푸시·PR 코멘트 작성·병합·VM 배포·cron·브라우저 E2E는 실행하지 않음. 병합 순서 #46 → #49 → #50 유지.

- 11-06 · B · 실제 서비스 api1이 아닌 테스트용 VM(`100.100.100.201`)에 현재 F-34·35 브랜치의 `backend/app`을 `/home/test/spacecube_backend`로 분리 배포. 기존 `/home/test/app`은 유지. Ubuntu Python 3.12에 `python3.12-venv` 설치 후 전용 `.venv`와 프로젝트 백엔드 의존성을 구성. 로컬 `spacecube_test`를 대상으로 테스트 VM `test_jobs.py` **6건 통과**(초기 실행에서 테스트 수집용 `conftest.py` 누락을 확인해 추가 배포 후 재실행). 실제 `python -m app.jobs.complete_reservations`도 테스트 예약 1건을 `completed`로 바꾸고 슬롯 1건·결제 `paid` 보존·JSON 성공 로그를 확인, 임시 행 정리. VM `127.0.0.1:3306`에는 MariaDB가 없고 호스트 DB에 대한 접속은 1130 권한 거부라 임시 SSH 역방향 터널로만 접속. 테스트 후 터널 종료, `.env` 자격 증명 비움(권한 600), 스모크 파일 삭제. 테스트 VM cron과 실제 서비스 api1은 변경하지 않음.
- 11-06 · B · F-35 완료 배치 구현: 예약 저장소의 `confirmed` 조건부 일괄 UPDATE, 서비스가 한국 현재 시각을 한 번 읽고 commit/rollback, CLI `python -m app.jobs.complete_reservations`가 primary 세션·기존 JSON 로그·안전한 오류 종류만 사용. 시간 칸과 결제는 유지. MariaDB F-35 테스트 6건 및 백엔드 전체 **314건 통과**, Ruff check·format(81개 파일) 통과. 기존 Starlette/httpx 경고 1건. 실제 HTTP/Postman 계약 변경이 없는 배치라 Postman 요청은 추가하지 않음. F-34와 같은 브랜치에서 #8 단일 PR로 제출 예정.
- 11-06 · B · 사용자 요청으로 `feat/B-F-34-cancellation`을 `feat/B-F-34-35-reservations`로 변경, F-34 커밋 `4cb0c26` 보존. worktree 경로는 `.worktrees/feat-B-F-34-cancellation` 유지. #8 열림·댓글 0건 및 B 명세 6절·jobs README·로컬 VM 배치 확인 후 F-35 구현 계획 작성. 예약 리포지토리 조건부 일괄 UPDATE, 서비스 트랜잭션, primary CLI 진입점·JSON 완료 건수 로그, api1 한 대의 시간별 cron 실행 안내를 예정. 고정 한국 시각으로 종료 직전/정각·날짜 경계·상태 필터·반복/중복 실행·취소 경합·칸/결제 보존·실패 롤백·CLI 종료 코드를 로컬 MariaDB에서 검증할 계획. 이번에는 브랜치명·STATE 계획만 변경, F-35 코드·테스트 실행·커밋·푸시·PR 없음.

- 11-05 · B · 최신 origin/develop `bdd6dea`에서 `feat/B-F-34-cancellation` 별도 worktree 생성. F-34 `POST /reservations/{id}/cancel` 구현: primary에서 본인 예약 `FOR UPDATE`, 잠금 뒤 시작 시각 검사, 예약 `cancelled`·해당 예약 칸 삭제·결제 `refunded`를 한 트랜잭션으로 커밋. 취소 전용 200 응답(`reservation_id`, `status`, `total_price`, 결제·환불 시각, `can_cancel=false`)을 B 명세에 기록. `reserve_cancel_ok`·`reservation_total{result="cancel"}`는 커밋 후 한 번 기록. MariaDB 11.4.13 `spacecube_test`의 예약·의존성·동시성 pytest 72건 통과, 전체 pytest 308건 통과, Starlette deprecation 경고 1건. 공식 Uvicorn/Postman 5요청·11검증 통과: OpenAPI·401·생성·재시도·취소, DB 환불·칸 해제·카운터 확인 및 합성 테스트 데이터 정리. Ruff lint·format과 Postman collection lint 통과. `verify.ps1`의 Ruff·pytest 통과; 격리 worktree에 프론트 `node_modules`가 없어 `run-s`를 못 찾았으나 기존 작업 트리에서 프론트 verify(55건·빌드) 통과. 코드·문서 변경은 F-34 branch에 있으며 커밋·푸시·PR은 아직 없음.

- 11-06 · FE · C안 화풍 적용(PM): `tokens.css` 색을 흰 바탕 `#ffffff`·검은 글자 `#111111`·주칠 `#a8441e` 한 색으로(회색은 검정을 옅게). 공간 그림은 `RoomArt.vue`가 도형 대신 `assets/art/venue-*.jpg` 유형별 일러스트 5장(1600×1040)을 보여 줌. API `art:<종류>-<색>` 계약은 그대로, 종류 9개 → 그림 5장 대응, 색 1은 좌우 반전. 공간 유형을 받으면 유형 그림 우선(크롤러는 스터디룸에도 seminar·lounge를 줌). 명세에 API가 없는 몰리는 시간대 차트·찜 버튼은 뺌(HourlyChart 삭제). 푸터 기술 스택을 HAProxy·Nginx·로컬 VM 7대로 고치고 위키 링크 추가. verify 단위 56·E2E 67 통과(재시도 없음)

- 11-06 · B · 사용자 요청으로 PR #46의 feat/B-F-40-reservations(HEAD f2edf4c, 원격 동일)에서 A 함수 제공 전 B 응답 준비를 구현. review_id 필수 nullable·변환 함수 필수 인자·라우터 exclude_unset 제거, 목록/상세 기존 생략 검증을 null 포함 검증으로 교체하고 변환/필수 필드 단위 3건 추가. Postman 기존 목록·상세 테스트에 미작성 null 확인 추가, B 명세·관련 README 갱신. A 파일·FE 코드·DDL은 변경하지 않음. A 함수는 최신 develop에도 없어 호출부의 null TODO와 작성/삭제 후기 DB 연동 미완료를 문서화하고 Draft 유지. 관련 MariaDB pytest 70 passed, Postman lint 6파일 오류/경고 0, 실제 Uvicorn·인증·MariaDB 11.4.13 HTTP 6요청/12검증 통과 및 임시 데이터 정리. pro_1 경로를 PATH 앞에 두고 verify.ps1 실행: Ruff 85파일·pytest 309 passed·FE 단위 55 passed·린트/색 검사/빌드 모두 통과(exit 0). 기존 Starlette·FE 조건문 경고 각 1건. A 일괄 SQL·작성/삭제 후기 통합·브라우저 E2E·실제 replica는 미검증. 기존 STATE 변경 보존, 브랜치 전환·커밋·푸시·외부 댓글 없음. #46 → #49 → #50 순서와 각 후속 브랜치의 develop 반영·수동 충돌 해결·회귀 검증을 유지.

- 11-06 · B · F-40 후속 작업 계획 수립. 현재 브랜치는 PR #46의 feat/B-F-40-reservations, HEAD f2edf4c이며 미커밋 변경은 기존 STATE.md뿐임을 확인. 원격 PR head도 동일하고 #45 PM 결정은 유지되며 develop의 A 일괄 함수는 아직 없음. 계획: ① 기존 #45에서 A에게 합의된 get_review_ids 구현·삭제 후기/후기 없음/빈 입력/일괄 SQL 및 트랜잭션 비간섭 테스트·반영 PR/커밋 요청 ② A는 develop 기반 별도 A 브랜치에서 구현하고 공유 계약 문서 반영, B는 현 브랜치에서 응답·회귀 테스트 준비 ③ A 변경이 develop에 병합되면 현 브랜치에 최신 develop 반영·충돌 정리 ④ B 서비스는 소유권 확인된 현재 페이지 ID만 일괄 전달하고 목록/상세에 review_id 또는 null을 항상 설정, 스키마는 필수 nullable로 정리 ⑤ MariaDB·실제 HTTP/Postman·verify.ps1 검증 후 PR 본문 갱신·Draft 해제·리뷰 요청. FE 목업 수정은 병행하고 화면 통합 때 확인, DB 스키마 변경은 불필요. 이번 요청 범위는 브랜치 확인·계획이며 코드 구현·브랜치 전환·커밋·외부 댓글 등록은 하지 않음.

- 11-06 · B · 사용자 요청으로 PR #46·#45 최신 댓글·원격 develop을 검토. PM·FE 결정(#45 comment-6672677838)은 이미 확정됐으며, A 제공 함수 get_review_ids(db, reservation_ids) → dict[int, int]와 공유 계약 문서가 후속 산출물임을 확인. 삭제 후기 ID도 유지하고 후기 없는 예약만 null로 응답해야 하나 현재 서비스는 필드를 설정하지 않고 라우터가 생략하며 테스트 2곳은 생략을 기대함. 최신 develop의 A review_repo에 일괄 함수가 없고 FE 목업도 삭제 후기를 제외함. #47은 이미 병합되어 별도 후기 목록 연결을 이번 함수 제공과 혼동하지 않도록 확인. #46은 Draft·정식 리뷰/인라인 스레드 없음·head f2edf4c CI 성공(run 42041269018)·mergeable=false. PM 제안 병합 순서는 #46 → #49 → #50. 구현·테스트 실행·외부 쓰기 없이 검토 및 STATE만 갱신했으며 기존 미커밋 변경은 보존. gh 인증 401·Project 조회 실패, GitHub 연결 도구로 원격 근거 확인. Postman은 계정·워크스페이스 미연결이라 원격 검색을 사용하지 않음.

- 11-05 · B · #45 댓글 0건 확인 후 최신 `origin/develop` `bdd6dea`에서 `feat/B-F-40-reservations` 생성. 목록·상세 라우터·스키마·서비스·리포지토리를 추가하고, `review_id`는 A 묶음 조회 계약이 미합의라 응답에서 생략. `test_reservations.py` 24건과 `test_reservation_dependencies.py` 43건, 총 67건이 로컬 MariaDB `spacecube_test`에서 통과(exit 0); F-40 신규 3건 포함. Ruff lint·format 통과, 기존 Starlette TestClient deprecation 경고 1건. 별도 실제 Uvicorn/Postman 검증은 MariaDB 11.4.13에서 6요청·12검증 통과(exit 0): OpenAPI·무인증 401·예약 생성/재시도·F-40 목록/상세. 일시 Uvicorn과 합성 회원·공간·예약은 종료 시 정리됨. CLI workspace 로그인 안내는 있었으나 no-report-events 로컬 실행은 성공. 커밋·푸시·PR 없음.

- 11-05 · B · GitHub CLI 일반 Windows 환경의 hun117 로그인 정상 확인(샌드박스 인증은 이전 자격 증명으로 401). 중복 F-40 제목 이슈가 없는지 확인 후 사용자 승인 초안으로 #45 등록: jinsan02·naturedevworks 멘션·담당, B·feature·review-needed 라벨, 11-05 통합 마일스톤. 원격 본문·담당·라벨·마일스톤 재조회 검증 완료. https://github.com/encore-ai-campus/mlo-03-p1-team4/issues/45 . 구현·테스트는 아직 진행하지 않음.

- 11-05 · B · 사용자 승인 초안으로 F-40 이슈 등록 시도(검토 요청·담당 jinsan02/naturedevworks, B·feature·review-needed). GitHub 연결 도구가 403 Resource not accessible by integration으로 생성 거절. 브라우저 대체도 접근 호스트·네이티브 연결 부재로 불가. 이슈는 생성되지 않았고 번호 없음. GitHub 이슈 쓰기 권한 복구 후 등록 필요. 코드·테스트 변경 없음.

- 11-05 · B · F-40 기존 합의 재점검: 기준 문서·관련 이슈 #3·4·7·8·9·11·43 댓글 및 PR #31·34·36·39 논의를 확인. 목록/상세 경로·primary·상태 필터·응답 필드는 기존 기준이며 #7 PM 댓글도 F-40 미구현을 확인함. #43 승인은 B→A 후기 목록 문맥 제공 계약으로, A→B 후기 ID 묶음 조회 승인은 확인되지 않음. 삭제 후기 숨김·예약당 후기 UNIQUE 및 삭제 후 재작성 차단은 기존 코드/DDL에 존재함. develop 목업은 삭제 후 review_id=null, MyPage는 null이면 기한 내 작성 버튼 노출하므로 화면과 재작성 차단의 불일치 보완 필요. 최신순은 목업 동작, ID 동률 정렬·상세와 목록 동일 구조·비활성 공간 예약 유지·새 묶음 함수는 제안으로 구분. 정적 확인만 수행, 테스트·GitHub 변경 없음.

- 11-05 · B · F-40 계획 재확인: GitHub develop의 예약 라우터는 생성 POST만 구현되어 있고 B 명세 5-3절은 내 예약 목록·상세 및 review_id를 요구함. 기존 이슈 전체와 F-40·내 예약 검색에서 독립 구현 이슈는 확인되지 않음. 이전 설명 보정: A의 get_by_reservation(db, reservation_id)는 이미 존재하며 삭제 후기까지 반환하므로 '후기 조회 함수가 전혀 없음'은 아님. 없는 것은 내 예약 목록용 묶음 조회 계약이고, 추가 함수는 A·B 합의할 개선안. 삭제 후기의 review_id 처리도 작성 중복 방지와 화면 표시 목적을 구분해 합의 필요. 원격 코드·명세 정적 확인만 수행, 테스트·이슈 등록 없음.

- 11-05 · B · 남은 예약 기능 계획 검토. GitHub #7 종료·#8 진행 전·#12 결정 완료·#43 열림 및 관련 댓글을 확인하고 코드·B 명세·프론트 목업과 대조. F-40 목록·상세 → F-34 취소·환불 → F-35 완료 배치 순서와 기능별 PR을 제안. F-40 독립 이슈, A 후기 ID 조회 계약, 취소 응답 명세 보완이 선행 항목이며 탈퇴·동시 예약 잠금은 A·B 협의 후 별도 처리. gh 인증 401로 Project 보드는 미확인. 이번에는 계획·상태 기록만 변경, 구현·테스트·GitHub 변경 없음.

- 11-06 · A · develop의 PR #44·#47에서 #43 계약과 A 직접 import·공개 비활성 공간 숨김·내 후기 유지를 확인. 로컬 MariaDB `spacecube_test`에서 `test_reservation_dependencies.py`·`test_reviews.py`·`test_review_lists.py` 58건 통과(Starlette 사용 중단 예정 경고 1건). 기능 코드 변경 없음. Swagger 실제 데이터 수동 확인은 남음.

- 11-06 · A · #45 `review_repo.get_review_ids(db, reservation_ids) -> dict[int, int]` 구현. 삭제된 후기 포함·빈 입력 SQL 없음·중복 ID에도 SQL 1회·호출자 트랜잭션 유지 로컬 MariaDB 테스트 2건 추가. 관련 pytest 60건 통과, `verify.ps1` 전체 통과: Ruff 88파일, pytest 320건, 프론트 단위 56건·린트·색 검사·빌드 통과. Starlette 경고와 기존 FE E2E 조건문 경고 각 1건. B PR #46의 실제 호출 연결·목록/상세 통합 검증은 남음.

- 11-06 · 공동 · 정문 구성 B안 확정(HAProxy 정문 → 서버마다 Nginx → FastAPI): 결정 기록, `로컬_VM_구성`(배치·방화벽·흐름), `infra/vm` 체크리스트, 산출물 02·인프라 검토 안내, 아키텍처 그림(HAProxy 로고 devicon 2.18.0), 비교 그림 `haproxy_compare`(draw.io 원본) 반영. `infra/haproxy`·`infra/nginx` 설정은 B, 설치는 노트북 주인
- 11-06 · 공동 · README를 강사님 목차(9항목)에 맞춰 221줄 → 112줄로 줄임: 기술 스택 뱃지 11개 한 줄(HAProxy 포함), 팀 소개 역할 칸 비움, 요구사항은 이슈, ERD는 그림만, 주요 프로시저는 위키 링크, 시연 화면은 토글. 긴 설명은 GitHub 위키 5쪽(목표·기술 스택·요구사항·ERD·주요 프로시저)으로
- 11-06 · FE · #45 결정 반영: 목업 내 예약의 `review_id`가 지운 후기도 포함(예약당 한 번), 지운 뒤에도 '후기 쓰기'가 다시 나오지 않음. 단위 56·E2E 67 통과(재시도 없음)
- 11-06 · A · 후기 자격·탈퇴 연계 테스트 보완: 실제 `DELETE /users/me` 후 완료 예약·후기 보존, 공개 후기의 `탈퇴한 회원` 표시를 MariaDB 통합 테스트로 확인. `NOT_COMPLETED`·`REVIEW_PERIOD_OVER` 기존 단위·API 테스트 포함 관련 73건, 전체 backend pytest 318건 통과. Ruff 검사·포맷 확인 통과. 시스템 pytest 임시 경로 권한 문제는 프로젝트 전용 임시 경로 지정으로 해결. Swagger의 만료 기한 경계는 API에서 과거 `created_at`을 만들 수 없어 수동 생성에 한계가 있음.

- 11-05 · A · 사용자 승인으로 로컬 33316/spacecube_test 초기화, 0001 스키마와 기준 seed 복구. DB 제약·동시 예약 검증 29건, 전체 backend pytest 317건 통과(Starlette 경고 1건). 실제 HTTP 공간·후기 목록 0건 확인. 앞선 시연 데이터로 인한 NEW 목록 테스트 3건 실패 해소.

- 11-05 · A · 사용자 요청으로 로컬 `127.0.0.1:33316/spacecube_test`만 삭제·재생성하고 0001·seed를 적용. 기존 회원·공간·예약·후기 등 시연 데이터를 모두 제거. 백엔드 전체 pytest 317건, Ruff 린트·포맷, DB 제약 검사, 임시 실제 HTTP 가입→예약→후기 작성·중복·수정·삭제 통과. HTTP 시험 데이터도 다시 제거한 뒤 B 내부 API로 가상 공간 3개만 등록하고 30일 전 등록 시각으로 설정. 최종 회원·예약·결제·후기 0건, 공간 3건이며 이 상태에서 전체 pytest 317건 재통과. 사용자가 실행한 8002 서버의 공개 공간 3건·후기 0건 조회 확인.

- 11-05 · A · 이슈 #4 재검토: B 후기 목록 계약 14건, 관련 57건, Ruff 린트·포맷 통과. 실제 서버 HTTP에서 공개 후기 목록·공간별 목록 200, Swagger에서 후기·공간 별점 정렬 200 확인. 전체 backend pytest는 314건 통과·B `GET /venues/new` 3건 실패: 로컬 `spacecube_test`에 수동 시연용 최근 공간 6건이 남아 테스트의 고정 개수 가정과 충돌. 시연 데이터는 보존하고 테스트용 DB 분리가 후속 과제.

- 11-05 · A · 이슈 #4: B 후기 목록 조회 계약 연결, 작성 자격·트랜잭션·목록 API 테스트 보강. 로컬 MariaDB 관련 57건 통과, 2건 추가 전 전체 backend pytest 315건 통과. 임시 서버의 OpenAPI·공개 목록 HTTP 확인, Swagger 수동 검증은 미실시.

- 11-05 · B · #43 PM 제안 및 B 동의에 따라 최신 develop(87de174, #41·#42 병합)에서 feat/B-F-51-review-context 생성·기준 커밋 확인 후 구현. review_context_query(*, active_only=True)가 예약·공간·유형을 조인한 4열 Select를 반환하며 예약 상태·후기 작성 자격은 거르지 않음. 기본값은 비활성 공간 제외, False는 포함. A 코드·main.py·DDL·API·이벤트 변경 없이 루트 약속·A/B 명세 3절·리포지토리/테스트 안내·구조에 계약 반영. pro_1·격리된 loopback MariaDB 11.4.13의 spacecube_test(0001·seed)에서 계약 14건 추가 포함 예약 의존성 43건·전체 pytest 303건 통과. verify.ps1 구성요소를 설치된 Miniforge pro_1·Node 경로로 실행해 Ruff 린트/포맷 및 프론트 린트·색 검사·단위 55건·빌드 통과. Starlette 사용 중단 예정·pytest 캐시 경로 권한·기존 FE 조건문 경고 각 1건. 테스트 데이터 6개 표 모두 0건 확인, 임시 DB 종료·정리. 후기 목록 HTTP·실제 replica·E2E·DDL 전용 검증은 이번에 실행하지 않았으며 A 직접 import 연결 후 통합 검증 예정. 커밋·푸시·PR은 아직 하지 않음.

- 11-05 · B · 사용자 승인에 따라 feat/FastAPI-B-internal-venues로 이름을 맞추고 원격 푸시, develop 대상 PR #42 생성. 본문에 Refs #38·#10·#19와 구현 범위·검증 결과·api1 후속 배포를 명시하고 A 담당 naturedevworks에게 리뷰 요청. 관련 이슈의 나머지 작업은 열어 두며 예약 후속 기능은 보류. 코드 변경 없이 진행 기록만 갱신, PR CI 결과 확인 대기.

- 11-05 · B · F-61 내부 공간 등록 구현: 예약 로컬 c4c000a를 backup/B-reservation-c4c000a로 보존하고 최신 develop(cbb69d7)에서 새 브랜치 생성. POST /internal/venues에 A 내부 키 검증·primary 의존성을 연결하고 출처 3종, 신규 201·재전송/갱신 200, 최상위 venue_id·ignored_facilities, 시설·그림 전체 교체 및 트랜잭션 롤백 구현. 기존 created_at·활성 상태 보존, UNKNOWN_REGION/CATEGORY·VALIDATION 사용. MariaDB 11.4.13 loopback 임시 인스턴스에서 전체 pytest 276건(F-61 35건·같은 출처 동시 8건 포함), 실제 HTTP Postman 6요청/12검증·컬렉션/환경 lint, Ruff 린트/포맷, 프론트 단위 55건·린트·빌드 통과. 기존 Starlette·프론트 조건문 경고 각 1건. DDL·공통 계약·예약 후속 기능 변경 없음. #38 옛 초안 stash는 보존하고 확정 계약만 새 문서에 반영. 사용자 요청으로 F-61 범위만 커밋하고 푸시·PR은 별도 확인 대기. api1 배포·방화벽·실제 크롤러 연동은 후속.

- 11-05 · B · PR #39에 최신 develop(71d0681, FE #36·40)을 통합. STATE.md 충돌은 예약 수정 기록과 FE 회원·후기 작업 기록을 함께 보존해 해결. 백엔드·DB는 검증된 f627774와 동일하며 MariaDB pytest 241건·Postman 4요청/8검증 결과 유지. 통합 후 프론트 verify(단위 55건·린트·빌드) 통과, 기존 린트 경고 1건. 변경 커밋 푸시 후 CI 재확인, #38 문서 변경은 별도 보존.

- 11-05 · B · PR #39 리뷰 P1 수정: find_recent_matching에서 confirmed/completed + paid만 재시도 후보로 조회. 취소 후 같은 칸 재예약은 새 예약 ID로 200, 타인 선점은 소유권 비노출 409, 환불 건 제외와 완료 예약 재시도 유지를 검증. MariaDB 11.4.13 loopback 임시 인스턴스·spacecube_test에서 수정 전 4건 실패 재현 후 전체 pytest 241건·실제 HTTP Postman 4요청/8검증·Ruff 린트/포맷 통과(기존 Starlette 경고 1건). 프론트 verify(단위 54건·린트·빌드)도 통과. 기존 Starlette·프론트 린트 경고 각 1건. PR 기존 head의 CI 성공 확인, 수정 커밋의 CI 확인 필요. #38 문서 변경은 별도 작업으로 보존.

- 11-05 · B · feat/FastAPI-B-reservation을 푸시하고 develop 대상 PR #39 생성: F-30~32 예약·모의 결제 API, 공식 A 통합·예약 라우터 연결, Postman 실제 HTTP 검증 포함. 리뷰어 jinsan02·naturedevworks 지정, 충돌 없음 확인. 로컬 pytest 236건·Postman 4요청/8검증·FE 단위 54건 및 린트·빌드 통과 기록 유지, GitHub CI 실행 중. 검색 개선 권고는 후속 PR로 분리.

- 11-05 · B · 예약 브랜치에 develop(eae5068, #31 병합본) 통합. 로컬 A 전달본 42개를 해시 검증 백업하고 backup/B-reservation-before-A-integration-fec14e6 참조 보존, 공식 A 파일로 전환·전달본 제외 설정 제거. 구형 cookies.py는 백업으로 보존. 예약 생성·재시도·get_owned와 count_cancellable 및 A·B 문서 기록을 함께 보존해 충돌 해결. 공식 main.py에 /reservations 등록, 별도 SyntheticSettings 제거 후 A is_synthetic_request 재사용. API 테스트를 공식 create_app으로 전환하고 등록·인증·공통 키 미설정 차단 검증 추가. pro_1·로컬 MariaDB 11.4.13 spacecube_test 전체 pytest 236건 통과(Starlette 경고 1건), FE 단위 54건·린트·색 검사·빌드 통과(기존 조건문 경고 1건). 별도 check_reservation_http.py로 임시 Uvicorn·실제 가상 회원가입/로그인·Postman 4요청/8검증 통과: OpenAPI 200, 무인증 401, 생성 201, 재시도 200. 예약 1건·칸 2개·결제 1건·is_synthetic·성공 카운터 1회를 확인하고 생성 ID의 데이터·임시 서버·비밀 환경 정리. Postman 컬렉션 4파일·공유 환경 lint 오류/경고 0건. 검증 구성요소는 Miniforge pro_1·설치된 Node를 지정해 실행. 프론트 실제 API 화면 연결·실제 replica 장애 시험은 후속 항목. A 탈퇴 서비스의 503 해제·호출 연결과 동시 예약/탈퇴 잠금 계약은 A와 후속 확인. PR 본문 확인 전이며 아직 푸시하지 않음.

- 11-05 · B · Postman CLI 1.86.0을 npm 전역 설치하고 F-30~32용 로컬 v3 컬렉션·환경을 추가. OpenAPI 경로 계약·인증 오류·예약 생성 및 같은 요청 재시도 200 확인을 분리하고 토큰·예약 조건이 비면 쓰기 요청을 건너뜀. 컬렉션 4개 요청 파일·환경 2개 lint 오류/경고 0건, 빈 환경에서 쓰기 요청 2개 생략 러너 exit 0, Postman Echo HTTP 및 스크립트 검사 1개 통과. 실 API HTTP 검사는 미실행: `127.0.0.1:8000` 미기동, 지침의 `pro_1` Python 환경과 `backend/.env`가 현재 PC에서 발견되지 않음. `postman status`는 CLI 1.86.0을 확인했으며 프로젝트 init·Postman 계정 인증은 없음(로컬 실행은 성공). 전체 init은 스킬 파일 다수 추가와 루트 `AGENTS.md` 갱신이 필요해 이번 범위에서 제외. 이 실행 셸의 `postman`은 여전히 WindowsApps 데스크톱 별칭이 우선하므로 NVM shim 직접 실행으로 검증; 사용자 프로필 PATH 변경은 이 실행 컨텍스트에서 확인되지 않음. 기존 F-30 MariaDB pytest는 앞선 검증 결과(14 API + 동시성 3 시나리오, 전체 pytest 182건)로 유지.

- 11-05 · B · F-30~32 `POST /reservations` 예약·모의 결제 구현. primary에서 공간·기간·영업시간·`min_hours`·인원·결제수단을 검증하고 `reservations`·`reservation_slots`·`payments`를 한 트랜잭션으로 커밋. 지난 종료 시각은 즉시 `completed`, 성공 201, 10분 안 같은 요청은 200 + 기존 결제. 시간 칸 기본키의 1062만 롤백 후 충돌로 처리하며 `slots`, 본인 단일·복수 충돌의 최소 ID, 혼합 소유자 ID 비노출을 확인. 가상 예약은 `X-Synthetic`과 `SYNTHETIC_API_KEY`를 함께 검사. MariaDB API 14건·경쟁 테스트: 다른 회원 50명(201 1건/409 49건), 같은 회원 재시도 50건(201 1건/200 49건), 겹친 시간 경쟁(201 1건/409 1건) 통과. 전체 `verify.ps1`: pytest 182건, FE 단위 54건, Ruff·프론트 린트·색 검사·빌드 통과, Starlette TestClient 경고 1건. 로컬 A `main.py`에는 reservations 라우터를 연결했으나 Git 제외 상태라 A 통합 후 등록을 확인해야 함. develop의 A 공통 `is_synthetic_request`는 키 검증을 제공하므로 통합 후 B의 별도 검증과 정합성을 확인해야 함. 예약 코드·테스트·API 문서는 `ad16619`로 커밋 완료; 이 진행 기록은 별도 문서 커밋으로 정리.
- 11-05 · FE · 이슈 점검으로 찾은 프론트 빈 곳 보완: ① 탈퇴 막기(11-05 결정) — 취소할 수 있는 예약이 있으면 탈퇴 버튼 대신 '예약 내역 보기', 서버 409 `HAS_UPCOMING_RESERVATION`도 같은 안내, 목업도 409 ② 회원 정보 수정(F-03: 이름·휴대폰·소식 받기)·비밀번호 변경(`WRONG_PASSWORD` 칸 오류) ③ 내가 쓴 후기 고치기·지우기(F-50, 지우기 창은 '지우지 않기' 기본 초점) ④ Playwright `E2E_BASE_URL`·`E2E_SYNTHETIC_KEY`로 실제 서버·가상 데이터 헤더 ⑤ 창 뒤 배경 올리브 토큰 `--c-overlay`, 내 메뉴 탭 제목. 단위 55·E2E 67 통과(재시도 없음)·7 기기 조건 건너뜀
- 11-05 · 공동 · #38 회의 결정(A·B·DB 댓글 정리)을 결정 기록·진행표·VM 문서에 반영: 생성기·크롤러 api1 실행, 예약은 B 로직 재사용·회원·후기는 SQL+A bcrypt, `event_daily` 분석 기준, 30일·회원 1,000명. 미정 4개는 #38에서 담당자에게 질문
- 11-05 · 공동 · 1차 수집원을 스페이스클라우드·쉐어잇 2곳으로 확정하고, 시연용 공간 30개에서 검증 후 부족한 수를 생성기로 보충하도록 문서 정리. 속성 기반 15~20개는 목표치, 카페 표본 5개는 1차 후보. 과거 행동 데이터는 우선 30일분, 실제 로그와 `is_synthetic` 분리. 기준 문서·크롤러 지침·생성기 계획·폴더 지도를 갱신하고 사진안은 미확정으로 유지. 코드·수집 실행 없음
- 11-05 · A · 이슈 #2 회원·탈퇴 기능에서 취소 가능 예약 확인과 개인정보 익명화를 연결하고 회원 테스트를 보강. 예약 있는 회원의 탈퇴 차단은 pytest로 검증했으며 Swagger UI 수동 테스트는 미실시. 로컬 `verify.ps1`에서 Ruff 린트·포맷, pytest 230건, 프론트 단위 테스트 54건·린트·빌드 통과(Starlette 및 프론트 린트 경고 각 1건). 탈퇴 확인 직후 동시 예약 처리는 B와 협의 대기.
- 11-05 · B · #31 브랜치 전용 작업 트리에서 origin/develop(c007470, A #34 포함)을 통합. STATE.md는 A 진행·로그아웃 결정과 B 조회 검증 기록을 함께 보존하고 backend/tests/README.md는 양쪽 검증 안내를 보존해 충돌 해결. 공식 main.py에 catalog·venues만 등록. A 탈퇴용 count_cancellable(db, user_id) → int 제공: 한국 시각 한 번을 기준으로 시작 전 confirmed 예약만 primary에서 집계하며 시작 정각은 제외, 커밋하지 않음. 기존 205건 + 경계·집계 12건 = MariaDB pytest 217건 통과(Starlette 경고 1건), Ruff 린트·포맷과 FE verify(단위 54건·린트·색 검사·빌드) 통과. FE 기존 E2E 파일의 조건문 린트 경고 1건. A 탈퇴 서비스는 503 유지, 실제 호출 연결·동시 탈퇴/예약 통합은 A와 후속 확인. 예약·Postman 커밋은 별도 예약 브랜치에 보존. 그 브랜치의 로컬 A 전달본 제외 설정은 공식 A 통합 때 정리하며 이 작업 트리는 모든 A 파일을 Git 추적 상태로 사용. 검색 개선 권고·실제 replica 장애 시험·브라우저 E2E는 이번에 진행하지 않음.

- 11-05 · B · PR #31 브랜치에 origin/develop(1cc11a8)을 머지. STATE.md 충돌 2곳은 B 구현·검증 기록과 공동의 11-05 통합일·로컬 VM 배포·회의 결정을 함께 보존해 해결. STRUCTURE·B API 명세·요구사항은 양쪽 변경을 자동 병합. A 전달본의 로컬 Git 제외는 유지하며, 새 공유 계약 count_cancellable()과 X-Synthetic-Key 반영 여부는 A 통합 및 후속 구현에서 확인해야 함. 머지 후 verify.ps1 전체 통과: pytest 165건·프론트 단위 54건·Ruff 린트/포맷·프론트 린트/색 검사/빌드. Starlette 경고 1건. A 전달본을 사용한 로컬 검증이며 실제 replica 장애·복제 지연과 GitHub A 통합 후 재검증은 후속 항목.

- 11-05 · B · F-14 `GET /venues/new` 구현. 한국 날짜 오늘~13일 전의 활성 공간만 DB에서 조회하고 `created_at DESC, venue_id DESC`로 정렬, page/size·전체 `total`과 `registered_on`, `new_days_left = 14 - 경과일`을 반환. 검색과 시설·이미지·오늘 점유 칸 일괄 조합을 공유하고 새 마이그레이션 없이 구현. F-14 DB API 4건 추가 후 `test_venues.py` **126건**, 전체 `verify.ps1` pytest **165건**, 프론트 단위 **54건**, Ruff·프론트 린트·색 검사·빌드 통과. 별도 임시 Uvicorn + MariaDB + Chrome 검사 **1건 통과**(NEW 목록 날짜·14일·기본 이미지 포함), 가상 공간 롤백 확인. Starlette deprecation 경고 1건. 실제 replica 장애·지연은 미검증. A 통합 `main.py` 라우터 등록은 별도 확인 필요. 구현·검증 및 문서 변경 11개 파일을 F-14 커밋으로 정리.

- 11-05 · B · 진행상황 및 오늘 작업계획을 `docs/기록/진행상황_2026-11-05_백엔드B.md`에 정리. F-20 이미지 기본값 `art:group-0`, 오늘 포함 14일 NEW 기준, `reservation_repo.py`의 `get_owned()` 위치, A 전달 로컬 파일 범위와 통합 후 재검증 필요, F-14→F-30~32 우선 작업안을 기록함.

- 11-05 · B · F-12·13 검증 완료. 검색 필터·now의 날짜 덮어쓰기·점유 칸·4종 정렬·평점 뷰·인기 예약 제외·페이지 total·입력 오류·묶음 쿼리 5회 검증을 위해 `test_venues.py`에 8건 추가. 실제 MariaDB에서 `test_venues.py` 122건, 전체 `verify.ps1` pytest 161건·Ruff·프론트 단위 54건·린트·색 검사·빌드 통과. Chrome 실제 HTTP API 검색·4종 정렬 요청·입력 오류도 1건 통과. 임시 가상 데이터 롤백 확인, Starlette TestClient 사용 중단 예정 경고 1건. 테스트 안내·상태 갱신, 커밋 전 상태.

- 11-05 · B · F-12 `GET /venues` 검색과 F-13 정렬을 구현. q·유형·지역·날짜·인원·시설 전체 보유·시각 칸·now 필터, 활성 공간만, 필터 적용 후 total·페이지. 기본·인기(7일 결제, 취소·과거 예약 제외)·가격·평점 정렬, 시설·이미지·점유 칸 묶음 조회. FE 기본 page1·size10과 응답 계약을 따름. 테스트 전용 데이터는 모두 DB 트랜잭션 안에서 만들고 롤백. 구현 명세·폴더 구조·테스트 안내·상태 갱신. 커밋 전 상태.

- 11-05 · B · F-21 `GET /venues/{venue_id}/available-dates` 구현. F-22와 날짜 범위·활성 공간 조회 공유, 기간 점유 SQL 한 번으로 날짜별 free·연속 빈 칸 bookable 집계. 기본 14일·최대 31일·음수 offset·마지막 페이지 잘림·큰 offset 사전 검증·지난 빈 칸·완료 점유·재조회 반영. 기존 venues 라우터 확장으로 main.py 변경 없음. test_venues **114건**(48건 추가), verify.ps1 전체 pytest **153건**·프론트 단위 **54건**·린트·포맷·빌드 통과. 별도 Uvicorn + MariaDB + Chrome 검사 **1건 통과**(F-20~22 실제 200·과거/마지막 페이지·검증/범위 400·공간 404), 임시 서버 종료·가상 데이터 롤백 확인. Starlette 사용 중단 예정 경고 1건. 목업 화면 E2E 재실행 안 함. 실제 replica 장애·복제 지연·FE 전체 연결은 후속 검증. 구현 명세·구조·테스트 안내 갱신, 커밋 미실행.

- 11-05 · B · F-22 `GET /venues/{venue_id}/slots?date=YYYY-MM-DD` 구현. 필수 날짜의 형식·실제 날짜 검증, 한국 오늘 기준 설정 범위 양끝 포함·범위 밖 400 detail, 활성 공간의 영업시간과 해당 공간/날짜 점유 칸만 조회. F-20 시간 칸 조합·slot_repo 재사용, 완료 점유·지난 빈 칸 유지, 캐시 없음. 기존 main.py 변경 없이 venues 라우터 확장. test_venues 66건(38건 추가), verify.ps1 전체 pytest **105건**·프론트 단위 **54건**·린트·포맷·빌드 통과. 별도 임시 Uvicorn + MariaDB + Chrome 검증 **1건 통과**(상세/칸 200·오늘 일치·미래 날짜·날짜 400·없는 공간 404), 임시 서버 종료·가상 데이터 롤백 확인. Starlette 사용 중단 예정 경고 1건. 목업 화면 E2E 재실행 안 함, 실제 replica 장애·복제 지연과 FE 전체 연결은 후속 검증. 명세·구조·테스트 안내와 구현·검증 파일 11개를 `[B] F-22 날짜별 시간 칸 조회 구현` 커밋으로 정리.

- 11-05 · B · F-20 구현·검증·명세 변경 16개 파일을 한 커밋으로 정리. 커밋 전 verify.ps1 재실행: pytest 67건·프론트 54건·린트·포맷·빌드 모두 통과. A 로컬 main.py는 커밋에서 제외하며, A PR이 develop에 통합될 때 venues import·라우터 등록이 포함됐는지 확인해야 함. A 통합 후에는 해당 Git 버전을 가져와 연결을 재확인.

- 11-05 · B · 사용자 확인: 지금은 DB 한 대라 실제 primary·replica 구성을 연결할 수 없으므로 후속 검증 체크리스트를 명시. 별도 브라우저 검증기는 Python 실행기가 같은 이름의 `.mjs`를 호출하므로 두 파일을 함께 버전 관리해야 함을 확인. 상태 기록만 추가했으며 테스트는 다시 실행하지 않음.

- 11-05 · B · 사용자 요청으로 가능한 추가 검증 실행. 기존 Chrome 화면 E2E 66건 중 **59건 통과·7건 기기 조건 건너뜀**, 실패 0건(목업 기반). B의 `test_read_routing.py` 3건은 실제 A 읽기 의존성·실제 MariaDB로 주소 미설정·정상 읽기·loopback 연결 실패를 확인하고 실패 시에만 primary 대체와 카운터 +1 검증. `check_venue_browser.py`·`.mjs`는 임시 Uvicorn + 실제 DB + Chrome으로 F-20 200·응답 계약·본문·없는 공간 404를 확인해 **1건 통과**. 임시 서버·브라우저 종료 및 가상 공간 롤백 확인. 마지막 전체 pytest **67건 통과**, Ruff 린트·포맷 통과. 별도 Chrome에는 Starlette·pytest 캐시 권한 경고가 있으나 검사는 통과. 실제 replica 서버 장애·복제 지연 및 F-21·22·A 후기까지 연결한 화면은 미검증. 프론트·A 소스·실제 DB 설정은 변경하지 않음.

- 11-05 · B · F-20 `GET /venues/{venue_id}` 구현. 기존 DDL의 Venue·VenueFacility·VenueImage 모델, 상세/시설/이미지/점유 칸 리포지토리, 응답 스키마·서비스·라우터 추가. 평점은 기존 뷰로 조회하고, 이미지 누락은 group-0·NEW는 한국 날짜 오늘~13일 전 정책 적용. 없는 공간·비활성은 같은 404, ID 검증은 공통 400. A 로컬 main.py는 import·라우터 등록만 추가했고 Git 제외는 유지(통합 방법은 backend/tests/README). 가상 데이터는 롤백. 첫 검증에서 모델 FK의 잘못된 CASCADE와 FastAPI 지연 라우터의 접두사 검사 문제를 확인해 DDL·최종 URL 검사에 맞게 수정. 최종 verify.ps1 전체 통과: pytest **64건**, 프론트 **54건**, Ruff 린트·포맷·빌드. Starlette 경고 1건. 브라우저 E2E·실제 replica 장애·A 후기 목록·F-21·22 별도 API는 이번 완료 범위 밖이며 크롤러·스키마·프론트 코드는 변경하지 않음.

- 11-05 · B · 사용자 요청으로 로컬 MariaDB `spacecube_test`에 가상 공간 한 개를 트랜잭션 안에서 생성하는 DB 테스트 추가. 기존 유형·지역 seed를 참조하고 출처를 synthetic으로 표시. 이미지 없는 상태의 group-0 기본값, 실제 이미지 저장·정렬, DB DATETIME으로 오늘·13일 전·14일 전·미래 날짜의 NEW 판정을 확인. 테스트 종료 시 롤백하고 해당 공간이 남지 않았음을 검증. 전체 pytest **44건 통과**(사용 중단 예정 경고 1건). 상세 HTTP API는 아직 미구현이며 이번 시험은 DB와 공통 함수의 연결 검증임. 운영 DB·DDL·프론트·A 파일은 변경하지 않음.

- 11-05 · B · 사용자 지시에 따라 F-20 이미지 기본값·NEW 경계를 요구사항과 B 명세에 반영. `venue_service.py`에 이미지 조합·NEW 판정 함수만 추가하고 `test_venues.py`의 정책 단위 테스트 10건 통과. 이미지 누락 시 `image="art:group-0"`, `images=["art:group-0"]`; NEW는 오늘·13일 전 포함, 14일 전·미래 날짜 제외. verify.ps1 전체 통과(기존 DB 기반 33건 + 정책 단위 10건 = pytest 43건, 프론트 54건·린트·빌드), Starlette 사용 중단 예정 경고 1건. F-20 상세 엔드포인트·실제 갤러리 화면 연결은 아직 미구현이며 E2E는 미실행. 크롤러 관련 구현·담당 문서는 변경하지 않았고 다음 순서를 상세 → 시간 칸으로 수정.

- 11-05 · B · F-11 지역 조회와 시설 목록 구현(#6 일부): `GET /regions`는 활성 공간이 있는 시·도만, `?sido=`는 해당 시·군·구만, `GET /facilities`는 전체 시설을 반환. Region·Facility 모델은 기존 DDL에 맞추고 지역 조회는 EXISTS로 중복을 방지. 시·도·시·군·구가 불변 지역 스냅샷과 5분 캐시를 공유하며 시설 캐시는 별도 유지. 실제 MariaDB `localhost:3306/spacecube_test`에서 catalog 19건·예약 의존성 14건, 전체 pytest **33건 통과**. 기존 verify.ps1 전체 통과(Ruff 린트·포맷, 프론트 테스트 54건·린트·빌드 포함), Starlette TestClient 사용 중단 예정 경고 1건. E2E·실제 replica 장애 대체는 미검증. 테스트 데이터는 롤백했고 A 파일·DB 스키마·프론트 코드는 변경하지 않음. 다음은 공간 데이터 공급용 `/internal/venues`를 제안.

- 11-05 · B · 예약 모델·소유권 조회 이관 코드, 의존성 테스트, 상태·구조·테스트 문서 총 6개를 커밋 대상으로 확인. 설치된 pro_1·Node 경로를 현재 프로세스에서 지정해 기존 verify.ps1 전체 실행: Ruff 린트·포맷, MariaDB pytest 19건, 프론트 단위 테스트 54건·린트·빌드 모두 통과. E2E는 미실행. 다음 신규 구현은 F-11 지역 조회·시설 목록을 제안.

- 11-05 · B · `C:\Pro_1`의 `models/reservation.py`·`repositories/reservation_repo.py`·`tests/test_reservation_dependencies.py`를 현재 프로젝트에 복사하고 SHA-256으로 원본과 동일함을 확인. 현재 DDL·7개 값 반환 약속·A 후기 서비스와 호환되며 수정 없이 사용. 로컬 MariaDB `localhost:3306/spacecube_test`에서 pytest **19건 통과**(의존성 14 + F-10 5), Ruff 린트·포맷 통과. Starlette TestClient 사용 중단 예정 경고 1건. 테스트 행은 외부 트랜잭션으로 롤백. 접속 비밀번호는 테스트 프로세스에서만 사용하고 파일·영구 환경변수에 저장하지 않음. 이전 프로젝트와 A 파일·Git 제외 설정은 변경하지 않았고 커밋은 하지 않음. E2E·예약 생성 동시성·후기 목록은 이번 검증 범위 밖.

- 11-05 · B · 사용자 확인: `get_owned()`는 이미 구현해 A에게 전달함. 재구현을 다음 작업으로 잡지 않고, 다음 신규 기능을 F-11 지역 조회·시설 목록(#6)으로 수정. 기존 `get_owned()`의 검증·PR 반영은 통합 때 별도 확인. 상태 문서만 수정했으며 추가 테스트는 실행하지 않음.

- 11-05 · B · 현재 브랜치·직접 전달받은 A 파일·기준 문서·GitHub 이슈를 대조해 남은 구현 순서를 검토. 다음 작업은 A 후기 작성을 여는 `get_owned()` 연결(#3), 이어 지역·시설 조회(#6)와 공간 데이터 공급용 `/internal/venues`를 제안(설계 결정 변경 없음). `pro_1`에서 Ruff 린트·포맷 통과, pytest 1건 통과·4건 준비 오류(`CHECK_DB_URL` 없음). 프론트는 설치된 Node 24.22.0을 직접 사용해 verify 통과(단위 테스트 54건·빌드 포함). E2E·DDL·실제 API 통합 시험은 이번에 실행하지 않음. A 파일과 Git 제외 설정은 수정하지 않음.

- 11-05 · 공동 · 로그아웃 서버 API 유지(PM 승인)에 맞춰 `산출물_01` F-02와 결정 기록을 고침. 이슈 #2 댓글도 수정
- 11-05 · A · 이슈 #1 변경을 `C:\mlo-03-p1-team4` 클론에 반영하고 경로 독립 테스트 실행 스크립트를 추가. 인증된 `POST /auth/logout` 204 및 Swagger Bearer 계약을 문서·테스트에 반영. 로컬 MariaDB `spacecube_test`에서 pytest 40개, Ruff 검사·포맷 확인 통과. DB 세션 시간대·STRICT 모드와 replica 대체도 로컬 확인 통과. 이벤트 자유 문자열 개인정보 정책은 팀 합의 대기. 후기·탈퇴 B 연동 전 제한은 유지.
- 11-05 · 공동 · 1차 배포를 로컬 VM으로 바꿈: `docs/로컬_VM_구성.md`·`infra/vm/README.md` 추가, 아키텍처 그림을 노트북 4대 · VM 7대로 새로 그림(AWS C안 그림은 `architecture_aws.png`로 보관). README·산출물 01·02·04·05·AGENTS·STRUCTURE·infra·simulator 반영, AWS 문서·`infra/monitoring`·`db/README`에는 맨 위 안내만

- 11-05 · 공동 · PM 회의(노진산): ① 탈퇴 — 시작 전 예약이 있으면 409 `HAS_UPCOMING_RESERVATION`, B가 `reservation_repo.count_cancellable()` 제공(A·B 확인 필요) ② A6 — `X-Synthetic` + `X-Synthetic-Key`(`SYNTHETIC_API_KEY`), RDS 백업 7일·삭제 보호, `limit_req` 안 넣음, Nginx `max_fails=2` ③ A7 — 동시 50명에서 조회 300ms·예약 500ms·로그인 800ms·오류 1% 미만, 200명은 한계 찾기 ④ A8 보류. 반영: `오류코드.md`, `백엔드_A·B`, `산출물_01·02·05`, `인프라_트래픽_안정성_검토`, `AGENTS.md`, `backend/.env.example`, `backend/app/core/README.md`, `simulator/`, `infra/aws·nginx`, `프론트_변경목록` 4-1절, README, CI 환경 변수

- 11-04 · FE · 화면 이름을 다락큐브로 통일(헤더·푸터·로그인·약관·페이지 제목·`index.html`), 공통 푸터를 디자인 캔버스 SiteFooter 시안대로 바꿈(서비스 소개·바로가기·프로젝트·안내 + 캠프 표기, 발표 11-09). `npm run verify`·E2E 59개 통과, README 시연 화면 6장 다시 찍음
- 11-04 · 공동 · GitHub Project 보드 [팀 방조 · 다락큐브 1차](https://github.com/orgs/encore-ai-campus/projects/5) 만듦: 상태 5개(할 일·하는 중·리뷰·막힘·끝), 파트 필드, 보기 4개(전체 표·보드·내 일·목 11-05 통합), 이슈 23개 넣음. 이슈 템플릿이 보드에 자동으로 넣게 함. 사용법: CONTRIBUTING 1절
- 11-04 · 공동 · CI 확장(`.github/workflows/ci.yml`): 바뀐 폴더별로 프론트 verify·E2E, DB·백엔드 테스트(compose MariaDB·MongoDB로 seed 확인·`check_ddl.py`·`check_mongo_init.js`·pytest) + 결과를 모으는 `CI 결과` job. 루트 `pytest.ini` 추가, `check_ddl.py`는 `CHECK_DB_URL`이 있으면 `.env`를 읽지 않게 함. 설명: CONTRIBUTING 4-1절
- 11-04 · 공동 · 시스템 아키텍처 그림을 1차 구성(C안: EC2 3대 + RDS, MongoDB는 정문 EC2, Grafana Cloud) 아이콘 그림으로 새로 그림(`docs/figures/architecture.png`). 11-03 그림은 확장안(`architecture_expanded.png`)으로 이름을 바꿔 남김. README 3장의 mermaid를 이 그림으로 바꿈
- 11-04 · 공동 · `docs/산출물_05_구현_운영_계획.md`(강사님 고려사항 답변) 추가. README를 강사님 목차(주요 프로시저·수행결과·한 줄 회고)로 바꾸고 시연 화면 6장(`docs/figures/screens`) 넣음. 일정 확정: 11-05(목) 통합 → 11-06(금) 피드백·검토 → 11-07(토) 반영 → 11-08(일) 발표 자료 → 11-09(월) 발표
- 11-04 · FE·공동 · 프론트–명세 대조(가입 필드·이벤트 9종·`X-Session-Id`·오류 코드) 통과. 작은 차이 3건 고침: `오류코드.md` EMAIL_TAKEN에서 '(탈퇴 회원 포함)' 정정(A4), 500 토스트에 `request_id` 표시, 405 토스트 추가(`App.vue`, 단위 테스트 2개 추가 → 54개). `npm run verify` 통과
- 11-04 · 공동 · AWS 1차 배치를 C안으로: EC2 3대(정문 Nginx+MongoDB, FastAPI #1·#2), Docker 없이 직접 설치, 보안 그룹 4개, 월 약 $17(작업 시간). `AWS_프리티어_구성.md`·`infra/aws` 체크리스트·산출물_02·인프라 검토·캔버스 메모 반영
- 11-04 · DB(공동 대신 실행) · seed: `db/seed/*.csv`(유형 5·시설 20·지역 230·시도/시군구 별칭·유형 대응표)와 `db/loaders/load_seed.py`(→ `seed.sql`, 표본 주소 197/200 풀림). 로컬 compose `infra/local/docker-compose.yml`(MariaDB 11.4:3308, MongoDB 7) — 첫 실행 자동 초기화 확인, 11.4에서 `check_ddl.py` 29건 통과. HTTPS는 HTTP로 다 되면 검토로 결정
- 11-04 · DB(공동 대신 실행) · 검증한 DDL을 `db/migrations/0001_init.sql`로 옮김(`CREATE DATABASE`·`USE` 줄 뺌). `check_ddl.py`가 0001을 쓰도록 바꿔 다시 실행 → 29건 통과. 기준 문서·폴더 지침의 DDL 경로를 마이그레이션으로 바꾸고 `docs/db/spacecube_mariadb.sql`은 옮겼다는 안내만 남김
- 11-04 · DB(공동 대신 실행) · DDL 실행 검증: 로컬 MariaDB 11.8에서 표 12·뷰 1·CHECK 12 생성, 제약 시험 29건(동시 결제 포함) 통과, MongoDB 7 초기화 시험 13건 통과. 시험 스크립트 `db/tests/check_ddl.py`·`check_mongo_init.js` 추가. STRICT `sql_mode` 필수를 `backend/AGENTS.md`·`infra/aws`·산출물_04에 반영. 로컬 `backend/.env` 만듦(git 제외). Docker 시작 오류(남은 소켓 파일) 해결
- 11-04 · 공동 · AWS 프리 티어안 `docs/AWS_프리티어_구성.md` 추가(계정 종류별 무료 방식·비용, EC2 1대 + RDS 1대, replica는 측정하는 날만, Grafana Cloud 무료), 산출물_02 6절·인프라 검토·`infra/aws` 체크리스트에 연결. 폴더 정리(캐시·빌드 결과 삭제, 프론트 작업 메모 3개를 `docs/기록/`로), 디자인 캔버스 공통 푸터(캠프·프로젝트 표기)와 로그인 화면 다시 설계(헤더는 화면별 그대로 둠)
- 11-03 · FE · Claude 아티팩트 8개 화면 대조 후 상세 404/조회 장애·후기 독립 로딩, 홈 NEW 빈 상태, 검색 오래된 오류, 모바일 결제 버튼 겹침, 가입 필수/선택 동의를 수정. 아티팩트 댓글·`docs/기록/인계_2026-11-03_Codex_FE검토.md`로 공유. `npm run verify`(단위 52·린트·빌드), Chrome E2E 59 통과·기기별 7 제외. 실제 API 연결 전.
- 11-03 · FE · FE-1~9 확정안 반영: `/venues`, 한 번 결제·409 재선택·지난 예약, 가입 동의·14세 검증, 내 후기·탈퇴, 401 선택 복원, 세션·이벤트·공통 오류 처리. `npm run verify`(단위 52·린트·빌드) 통과, Chrome E2E 58 통과·기기별 6 제외. 실제 API 연결 전. 스킬·ZIP 점검은 `docs/기록/작업_2026-11-03_프론트_FE반영.md`·`점검_2026-11-03_FE스킬.md`. 다른 파트 코드 변경 없음.

- 11-03 · 공동 · A5~A8(협업·1차 배포 구성·측정 기준·발표 준비)을 추후 확정으로 미룸. 프론트 작업을 Codex로 하기 위한 작업 단위(FE-1~FE-9)를 `docs/프론트_변경목록_11-03.md` 7절에 정리
- 11-03 · 공동 · A4 API 세부 확정: 예약 트랜잭션 1062 뒤 분기(같은 요청 200 / 내 예약 겹침 409 `mine` / 남 409), 탈퇴 즉시 개인정보 지움·재가입 허용·후기 '탈퇴한 회원'. 백엔드 A·B(본문·테스트), 요구사항 F-04·F-30, DB 명세, 오류 코드, 프론트 변경 목록 반영
- 11-03 · 공동 · A3 기초 데이터 확정: 유형 영화관 → 강의실(`lectureroom`), 크롤링 3곳과 robots.txt 다시 확인, 사이트별 유형 대응표·지역 표기 맞춤(`sido_alias.csv`)·연습실 제외를 `db/seed/README.md`에, 크롤러 대상·규칙을 `crawler/AGENTS.md`에. 요구사항·DB 명세·DDL 주석·백엔드 B·아키텍처·서비스 흐름·생성기·프론트 변경 목록 반영. 프론트 코드는 그대로
- 11-03 · 공동 · A2 DB 스키마 확정: DDL에 시간 범위 CHECK 9~23(venues·reservations·reservation_slots), `users.terms_agreed_at`·`privacy_agreed_at` 추가. DB 명세·백엔드 A(가입 필수 동의·만 14세 미만 `under_14`)·B(`/internal/venues` 영업시간 검증)·오류 코드·프론트 변경 목록·생성기·DB 테스트 반영. DDL은 여전히 실행 검증 전
- 11-03 · 공동 · A1 파트 약속 확정: `get_owned()`에 `created_at`(후기 기한 계산), `log_event()`에 `category`, MongoDB 쓰기는 `BackgroundTasks` 대신 내부 스레드 풀, `get_now()`는 시간대 없는 한국 시각. 백엔드 A·B 문서, AGENTS(루트·backend), core·repositories README 반영
- 11-03 · 공동 · 방향 정리: '먼저 띄우고 재 본 뒤 조건을 넘는 것만 더한다'. 인프라 검토에 1-1절(1차 필수 / 잴 것과 합격선 / 나중에 추가할 것과 조건) 추가, 열린 질문을 A(지금 정할 것 8묶음)·B(나중에 추가 10개, 조건 포함)로 다시 나눔. 1차 정문은 지금 설계(Nginx) + 설정 보강
- 11-03 · 공동 · 인프라·트래픽·안정성 타당성 검토(`docs/인프라_트래픽_안정성_검토.md`): HAProxy는 필수 아님, 권장은 ALB + 앱 서버별 Nginx + Auto Scaling(대안 HAProxy), Playwright는 화면 흐름·Locust는 트래픽, 먼저 막힐 곳은 RDS 연결 수(약 35~40)와 t4g CPU 크레딧, AWS 서비스별 안정성 표, 배포 관여 15개 팀별 검토. `산출물_02` Nginx 헬스체크 문구 정정, 연결 풀·워커·시간 제한 값을 `backend/AGENTS.md`에, 안정성 체크리스트를 `infra/aws`에. 열린 질문을 '한 번에 검토할 목록' 19개로 합침
- 11-03 · 공동 · 날짜 결정(실제 날짜, 과거·미래 365일, 지난 시간 예약은 바로 완료)을 산출물 01·03·04, 백엔드 A·B, `.env.example`, 사용자 여정 그림에 반영, 팀원 제안 검토 기록. `docs/오류코드.md`(전체 오류 코드) 추가. UX 법칙 5개 적용 규칙과 화면별 바꿀 것 9줄(`docs/공간대여_04`). 문서 2차 검토(`docs/기록/`): 세션 id 끊김·인기순·TTL·`get_now`·로그 개인정보 규칙 고침, 결정 필요 9건을 열린 질문으로. 개인 스킬 저장소에 hallmark·impeccable·design-taste-frontend·design-motion-principles·ecc-security-review 설치(커밋, push 전)
- 11-03 · 공동 · 토큰 결정 반영: 액세스 토큰만(Bearer, 60분, 리프레시 없음). 백엔드_A 5-1에 토큰 표(클레임, 확인 순서, 로그아웃, 비밀번호 변경 뒤 한계), 프론트 변경 목록에 401 처리, 산출물_01 결정표·AGENTS·backend README 갱신
- 11-03 · 공동 · 이벤트 결정 반영: `unselect_slot`·`abandon` 제외(이탈은 `select_slot` 있고 `reserve_ok` 없는 세션으로 계산, `산출물_04` 8절), 모르는 이벤트는 그 건만 버림(백엔드_A 5-3·테스트). 프론트는 `room_id`를 payload에 넣고 있어 맨 위 `venue_id`로 옮기도록 변경 목록에 추가. 앞서 '프론트가 두 이벤트를 보내 400'이라고 한 것은 틀림(README 표에만 예정으로 있었음)
- 11-03 · 공동 · ORM 결정 반영: SQLAlchemy 2.1 동기 + PyMySQL + pymongo, SQL 파일 마이그레이션. `environment.yml`에 백엔드 패키지 11개 버전 고정(설치는 안 함), `backend/AGENTS.md` 'DB 접근 규칙'(def 엔드포인트, 세션 시간대 +09:00, commit/rollback, 1062만 409), `backend/app/models/` 폴더와 `test_models_match_db.py` 추가, 산출물 01·02·04와 백엔드 A·B 문서 갱신. bcrypt 5의 72바이트 제한을 가입 검증에 넣음
- 11-03 · 공동 · 폴더·지침 정리: `STRUCTURE.md`(폴더 지도·담당·기준 문서·큰 버그 방지 규칙) 추가. 루트·backend·db·crawler·frontend `AGENTS.md`와 backend·db·infra·simulator README를 11-03 확정안으로 고침(pending·`/rooms`·게시판·`v_room_rating`·옛 `log_event` 제거, primary/replica 세션 표, 오류 코드 표). 옛 설계 01~03은 `docs/지난설계/`, 회의·검토는 `docs/기록/`로 옮기고 링크 고침. `docs/프론트_변경목록_11-03.md`, `backend/.env.example`, `backend/scripts/README.md`, 루트 `.gitignore` 추가. Nginx 초안의 `/internal/` 차단 위치를 `/api/internal/`로 고침(원래는 막히지 않았음). 코드는 그대로

- 11-03 · 공동 · DB 설계 확정안: `docs/산출물_04_DB명세서.md`(MariaDB + MongoDB, master–slave vs 클러스터 비교, 팀원 변경 반영표, 3단계 스키마·정규화 다시, 표 12개·컬렉션 3개 명세, Loki·Prometheus 데이터, 데이터량), DDL 수정안 `docs/db/`(실행 검증 전). 그림 7장 `docs/figures/`(ERD, 아이콘 아키텍처, 서비스 흐름 5장)과 다시 만드는 스크립트. 산출물 01·02·03, 백엔드 A·B 문서를 이 명세에 맞춤. 팀원안과 다른 점: `min_hours` 복원, 결제수단 영문 코드, posts·comments 삭제. 아이콘 nginx·fastapi.svg의 중복 fill 속성 수정

- 11-03 · 공동 · 11-03 회의(MongoDB 필수·이벤트 저장, 홀딩 없음·결제순 확정, 자유게시판·댓글 삭제)와 팀원 의견(MySQL master–slave)을 반영해 산출물 5개 개정. 비판적 검토 기록 `docs/기록/검토_2026-11-03_산출물_비판적검토.md`(치명 3·중요 8·사소 4: 복제 지연 때문에 '내 것'·인증은 primary, MongoDB는 NAT가 없어 퍼블릭 서브넷 EC2 + 보안 그룹, 헬스체크 3단계 등). 제안(가상 공간 생성, 날짜 방식)은 권장안(표본 분포 + 생성, 실제 날짜 + 백필)으로 쓰고 회의 확정 전 표시. 백엔드 문서 이름을 `백엔드_A_회원_후기_이벤트.md`로 바꿈
- 11-02 · 공동 · 변경 ERD(14개 표, MySQL 8.0, rooms·user_events 삭제, 결제 대기 삭제) 기준 산출물 3개(`docs/산출물_01~03`: 요구사항명세서·시스템 아키텍처 흐름도·서비스 흐름도)와 백엔드 파트별 문서 2개(`docs/백엔드_A_…`, `docs/백엔드_B_…`) 작성. 기존 01~03 문서는 변경 전 기준으로 둠. 확인 필요 9개(status 값, min_hours, NEW 기준, 가상 날짜 위치, is_synthetic, DBMS, `/venues` 경로, 결제수단 코드, 생년월일 수집)는 회의 안건
- 11-02 · FE · 애니메이션 점검(emilkowalski/skills `review-animations`) 반영: 아코디언 닫힘 ease-in 제거, 호버 들림은 마우스에서만, 눌림 0.95~0.97, 툴팁은 버튼 쪽에서 125ms, 곡선·등장 300ms 토큰, 찜 하트 keyframe→transition, 창·드로어 닫힘 150ms(드로어는 닫힘 키프레임 이름을 따로 둬야 함), 스켈레톤을 transform으로, 움직임 줄이기는 '흐려짐만'으로 바꾸고 JS 스크롤도 따르게. `e2e/motion.spec.js` 추가. 전체 통과: 단위 28, E2E 56·6 의도적 skip
- 11-02 · 공동 · Ruff 도입(`ruff.toml`, `environment.yml`에 ruff 0.17.3)과 전체 검증 `verify.ps1`. 기존 파이썬 5개 파일 정리: 크롤러·글꼴 스크립트 포맷, `with open`, `contextlib.suppress`, 룸 유형 고르기를 `next()`로(결과 같음 확인). `docs/지난설계/research`는 일회성 보고서 생성기라 검사에서 뺌. E2E 접근성 검사를 창·카드 움직임이 끝난 뒤에 재도록 고침(움직이는 도중 반투명이라 대비를 낮게 재던 간헐 실패). 전체 통과: ruff, 단위 28, E2E 47·3 의도적 skip
- 11-01 · FE · 리뷰·QA 제안 1~6 반영(15건 완료, 1건 정정, 1건 보류). E2E 시계 고정·접근성 검사 6상태 추가(토스트 대비 문제 수정), 오늘·예약 가능한 날 계산(min_hours), 로그인 후 선택 유지, 예약 카드 바로 가기, 조회 더 보기·늦은 응답 무시, `beforeunload`, `.env.example`, 안 쓰는 글꼴 4종을 `design/fonts/web`으로(dist 2.8→0.9MB). verify(단위 28) 통과, E2E 47 통과·3 의도적 skip. **B 확인 필요**: API 03의 available-dates 규칙, 검색 page·size

- 11-01 · FE · 프론트 리뷰·탐색 QA(`docs/기록/리뷰_2026-11-01_프론트_QA.md`): 발견 17건. 높음 2건 = 밤 9시 이후 예약 E2E가 건너뛰어져도 통과로 나옴, 성공 토스트 대비 3.43:1. 코드 수정 없음(피드백 대기)

- 11-01 · FE · 토큰 밖 색 코드 61곳 정리(토큰 28개 추가), `lint:colors` 검사 추가. `npm run verify`·E2E 17개 통과

- 11-01 · FE · 팀 공유용 `docs/공간대여_05_프론트_현황.md` 작성. 프론트 문서 최신화(UI 패턴 문서 화면별 표를 구현 기준으로, 루트 README 현황·폴더 트리, `src/README.md`). 알게 된 것: 화면에 있지만 DB에 없는 값 6개(시설 설명·후기 태그·인기도 등), 토큰 밖 색 코드 61곳

- 11-01 · FE · 검증 도구 도입(create-vue 공식 구성): Oxlint + ESLint 10(eslint-plugin-vue, 접근성), Vitest + Vue Test Utils 단위 테스트 20개, Playwright E2E 9개 × 데스크톱·폰 + axe 접근성 검사. `npm run verify` 통과, E2E 17개 통과·1개 의도적 건너뜀. 린트 지적 3건 수정(GET 요청에도 body 키를 넣던 것, 쓰지 않는 props 변수, 삼항식을 문장처럼 쓴 것)

- 11-01 · 공동 · 이미 정한 내용과 어긋난 문서 정리: 일러스트 10종(01), MVP 수치 문서에 공간대여 전환 안내·이미지 풀 20장·5개 유형 결정, 10-30 회의 문서의 카테고리 범위·NEW 14일, Nginx `/api` 접두사, 크롤러 README(코드가 스터디룸 필터로 뒤처짐), backend 실행 환경 conda `pro_1`

- 11-01 · 공동 · 팀원 피드백(DB 구조·가상 날짜·크롤링) 검토 문서 추가, 회의에서 정할 제안 8개

- 11-01 · 공동 · API 문서 03을 프론트에 맞춤: `GET /rooms`에 people·facilities·now 파라미터와 항목별 `slots`, `GET /reviews`에 sort(recent·high·low). B·A는 이 이름으로 구현

- 11-01 · FE · 조회·상세·예약(모의 결제)·로그인·회원가입·내 예약(취소·후기)·후기 게시판 화면 완성(목업). 메인 히어로 제목 축소, 1280×650에서 유형 벤토까지 첫 화면에 들어오게 조정. 새 활동 로그 이벤트 8개(`frontend/src/composables/README.md`) → A가 허용 목록에 추가 필요. `npm run build` 통과, 1280·375px 확인

- 11-01 · FE · Vue 셋업, 공통 레이아웃·컴포넌트 12종, 메인 화면(히어로·오늘 남은 칸·유형 벤토·NEW 캐러셀·카드 그리드·시간대 차트·후기) 목업으로 완성. `npm run build` 통과, 375·800px 폭 확인
- 11-01 · 공동 · UI 패턴 결정 문서(`docs/공간대여_04`), 캔버스 화면별 패턴 메모와 '글꼴 시안' 페이지
- 11-01 · 공동 · conda `pro_1` 환경, 글꼴 5종 원본·Windows(내 계정) 설치·웹용 서브셋

- 10-30 · 공동 · `AGENTS.md`(루트·backend·frontend·db·crawler)와 `STATE.md` 추가
- 10-30 · 공동 · 4개 파트 스켈레톤 폴더와 폴더별 README 작성
- 10-30 · 공동 · 기능 정의·DB 정규화·FastAPI 분담 문서 작성, 디자인 화면을 공간대여 버전으로 수정
- 10-30 · DB · 스페이스클라우드 크롤러 시제품, 공간 200개 표본으로 유형별 개수 추정
