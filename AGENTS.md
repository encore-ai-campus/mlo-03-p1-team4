# AGENTS.md — PRO_1 공간대여 예약 시스템

Codex와 Claude Code가 함께 읽는 작업 지침입니다. 사람이 채팅에서 직접 지시한 내용이 이 파일보다 우선합니다. 하위 폴더의 `AGENTS.md`는 그 폴더 안에서 이 파일보다 우선합니다.

## 프로젝트

스터디룸·스튜디오·카페·강의실·파티룸을 전국에서 1시간 단위로 예약하는 서비스(공간큐브, 가칭). 4명이 프론트 1, FastAPI 2(A·B), DB 1로 나눠 만든다. 설계는 **2026-11-03 확정안**(`docs/산출물_01~04`, `docs/백엔드_A·B`)이 기준이다. 코드는 크롤러와 프론트(Vue: 화면 7개, 목업 데이터)까지 있고, 프론트는 11-03 확정안(`/venues`·한 번 결제·후기 모아보기)을 목업에 반영했다. 실제 API 연결은 아직이다. 각 파트는 따로 진행하고 git으로 합친다.

## 작업 시작 순서

1. `STATE.md`에서 지금 상태, 담당, 다음 할 일, 열린 질문을 확인한다.
2. `STRUCTURE.md`에서 내가 고칠 폴더·파일이 누구 담당인지, 어느 문서가 기준인지 확인한다.
3. 작업할 폴더의 `README.md`와 `AGENTS.md`를 읽는다.
4. 아래 기준 문서 중 필요한 것만 읽는다. `docs/지난설계/`와 `docs/기록/`은 이력이라 구현 기준으로 쓰지 않는다.

## 기준 문서

| 무엇 | 기준 | 비고 |
| --- | --- | --- |
| 기능 ID(F-xx), 예약 규칙, 비기능 요구 | `docs/산출물_01_요구사항명세서.md` | 코드·테스트·커밋에 F-ID를 쓴다 |
| 표·컬럼·제약·인덱스, MongoDB 컬렉션 | `docs/산출물_04_DB명세서.md` + `db/migrations/0001_init.sql`(11-04부터 기준)·`docs/db/mongo_init.js` | 표를 바꿀 때는 `0002_…` 새 마이그레이션 + 명세서 같이 |
| API 경로·요청·응답, 파트 약속 | `docs/백엔드_A_회원_후기_이벤트.md`, `docs/백엔드_B_공간_예약_결제_크롤링.md` | 프론트도 이 응답 모양을 따른다 |
| 오류 코드·문구·프론트 처리 | `docs/오류코드.md` | 여기 없는 코드는 쓰지 않는다 |
| 구성·primary/replica 경로·네트워크·포트 | `docs/산출물_02_시스템아키텍처_흐름도.md` | IP 번호 규칙은 `docs/AWS_네트워크_설계.md`, 1차 AWS 배치·비용은 `docs/AWS_프리티어_구성.md`(프리 티어) |
| 화면 흐름·시퀀스 | `docs/산출물_03_서비스흐름도.md` | |
| 프론트가 고칠 것(11-03 변경) | `docs/프론트_변경목록_11-03.md` | |
| 화면 패턴·움직임·글꼴 | `docs/공간대여_04_UI패턴_글꼴.md` | |
| 수치(공간 수·사용자 수·크롤링 범위) | `docs/MVP_시뮬레이션_크롤링_수치.md` | 10-30 수치, 11-03 안내 참고 |

코드와 기준 문서가 다르면 둘 중 하나를 마음대로 고치지 말고, 차이를 사람에게 알린다. 기준 문서끼리 다르면 위 표의 문서가 이긴다.

## 폴더와 담당

| 폴더 | 담당 |
| --- | --- |
| `frontend/` | 프론트 |
| `backend/app/core/`, `backend/app/main.py`, A 파일(`auth`·`users`·`reviews`·`events`·`health`), `backend/scripts/`, `infra/monitoring/` | FastAPI A |
| B 파일(`catalog`·`venues`·`reservations`·`internal`, `slot_repo`·`payment_repo`), `backend/app/jobs/`, `simulator/locust/`, `infra/nginx/` | FastAPI B |
| `db/`, `docs/db/`, `crawler/`, `simulator/generator/`, `infra/local/` | DB |
| `docs/`(위 제외), `infra/aws/`, `STATE.md`, `STRUCTURE.md` | 공동 |

- 요청받은 파트의 파일만 고친다. 다른 파트 파일을 고쳐야 하면 멈추고 무엇을 왜 고쳐야 하는지 알린다.
- 아래 **약속**은 여러 파트가 같이 쓴다. 이름·인자·반환 형태를 바꾸지 말고, 바꿔야 하면 사람에게 먼저 묻는다. 자세한 형태는 `docs/백엔드_A` 3절, `docs/백엔드_B` 3절.
  - `get_db_write()` primary 세션 / `get_db_read()` replica 세션(실패하면 primary로 대체) (A 제공)
  - `get_current_user()` → `CurrentUser(user_id)`, primary에서 확인 (A 제공)
  - `log_event(session_id, user_id, event_type, venue_id=None, category=None, payload=None, is_synthetic=False)` — MongoDB는 내부 스레드 풀로, 부르는 쪽은 기다리지 않음 (A 제공)
  - `get_today()`·`get_now()` → Asia/Seoul 오늘·지금. `get_now()`는 **시간대 없는 한국 시각**(MariaDB `DATETIME`과 같음), `TODAY_OVERRIDE`는 테스트 전용 (A 제공)
  - `AppError(code, message, status, detail=None)`, `paginate()`, `is_synthetic_request()`, `get_session_id()`(헤더 `X-Session-Id`), `reservation_counter` (A 제공)
  - `reservation_repo.get_owned(db, user_id, reservation_id)` → `(reservation_id, venue_id, reserve_date, start_hour, end_hour, status, created_at)` 또는 `None` (B 제공)
  - `reservation_repo.count_cancellable(db, user_id)` → `int`: 시작 전 `confirmed` 예약 수, 탈퇴 전 확인용 (B 제공, 11-05)
  - 뷰 `v_venue_rating(venue_id, rating_avg, review_count)` (DB 제공)
  - 표·컬럼 이름, API 경로와 응답 형식

## 바꾸면 안 되는 도메인 규칙

- 예약 단위는 `venues`(공간) 하나다. `rooms`·`room_id`는 없다.
- 날짜는 **실제 날짜, 가상 날짜 없음**. 예약은 1시간 칸, 연속 `venues.min_hours`(기본 1)~4칸, 영업시간 안, 오늘 기준 과거·미래 각 `BOOKING_PAST_DAYS`·`BOOKING_FUTURE_DAYS`(기본 365일) 안. **지난 날짜·시간도 예약 가능**하고 끝나는 시각이 지났으면 만들 때 바로 `completed`. 칸은 정수 시(9~22).
- 결제 화면에 들어올 때는 아무것도 잡지 않는다. 결제 버튼 한 번 = `reservations`·`reservation_slots`·`payments`를 **한 트랜잭션**으로 INSERT. 먼저 커밋한 요청이 이긴다.
- 중복 예약은 `reservation_slots` 기본키 `(venue_id, slot_date, slot_hour)`가 막는다. 중복 키 오류(1062)를 409 `SLOT_TAKEN`으로 바꾸고 `detail.slots`에 겹친 칸을 담는다. '빈 칸인지 먼저 SELECT'로 막으려 하지 않는다.
- 예약 상태는 `confirmed` → `completed`(끝나는 시각이 지나면, 1시간 배치) 또는 `cancelled`(이용 시작 전, 칸 삭제, 결제 `refunded`). `pending`·`expired`·결제 대기 10분·`/confirm`은 없다.
- 결제는 모의 결제만. 결제수단은 `transfer`·`card`·`phone`(API 값 = DB 값). 실제 결제 연동 코드를 만들지 않는다.
- 회원이 쓰는 글은 후기만(예약당 1개, `completed`일 때만). 자유게시판·댓글·공지·관리자 역할은 없다.
- 사용자 이벤트는 `events.log`(→ Alloy → Loki)에 먼저 쓰고 MongoDB `user_events`에는 응답 뒤 백그라운드로 쓴다. MongoDB가 꺼져도 예약·이벤트 API는 성공해야 한다.
- 공간 이미지는 일러스트 풀(`art:<종류>-<색>`, `frontend/src/components/domain/RoomArt.vue`)을 돌려 쓴다. 크롤링한 사진·업체 실명·원문 소개를 저장하지 않는다.
- 가상 데이터는 `is_synthetic = true`. API로 넣을 때 헤더 `X-Synthetic: 1` + `X-Synthetic-Key`(= `.env` `SYNTHETIC_API_KEY`). 키가 없거나 틀리면 401 `UNAUTHORIZED` (11-05 A6)
- 시간대 Asia/Seoul(MongoDB 저장은 UTC), 날짜 `YYYY-MM-DD`, 금액은 원 단위 정수. 오늘·지금은 `get_today()`·`get_now()`로만 읽는다(`date.today()`·`datetime.now()` 직접 호출 금지).
- 오류 응답 `{"code","message","detail"}`, 목록 응답 `{"items","page","size","total"}`.

## 큰 버그를 막는 규칙

- **읽기 경로:** 쓰기, 인증, '내 것'(`/users/me`, `/reservations/me`, `/reservations/{id}`, `/users/me/reviews`), 409 뒤 겹친 칸 다시 읽기는 `get_db_write()`. 공개 조회만 `get_db_read()`. 헷갈리면 primary.
- **계층:** 라우터는 검증과 서비스 호출만, 트랜잭션은 서비스, SQL은 리포지토리. 남의 파트 표는 그 파트 함수로만 읽는다.
- **기준 문서에 없는 표·컬럼·API·오류 코드·이벤트 이름을 새로 만들지 않는다.** 필요하면 문서부터 고치자고 사람에게 말한다.
- **DB 접근은 SQLAlchemy 2.1 동기 + PyMySQL, MongoDB는 pymongo**(11-03 결정). 엔드포인트는 `def`, 표는 `db/migrations/*.sql`로만 만들고 모델은 그 DDL과 같게. 자세한 규칙은 `backend/AGENTS.md` 'DB 접근 규칙'.
- **로그인은 액세스 토큰만**(JWT 60분, `Authorization: Bearer`, 리프레시·쿠키 없음, `sub`는 문자열). `docs/백엔드_A` 5-1.
- **정해지지 않은 것은 고르지 않는다:** `STATE.md` 열린 질문. 정해지기 전에 코드가 필요하면 묻는다.
- 패키지 버전은 `environment.yml`에 고정한다. 새 패키지는 묻고 더한다.
- 테스트 DB는 로컬 MariaDB `spacecube_test`. SQLite로 대신하지 않는다(제약 동작이 다름).

## 명령

이 PC들은 Windows이고 시스템 `python` 명령이 없다(Microsoft Store 별칭). Python은 이 프로젝트 전용 conda 환경 **`pro_1`**(Python 3.12, `environment.yml`)로 실행한다. 다른 conda 환경은 쓰지 않는다.

```bash
conda env create -f environment.yml
```

```bash
conda run -n pro_1 --no-capture-output python crawler/spacecloud_crawler.py fetch 53074
```

- Anaconda Prompt에서는 `conda activate pro_1` 후 `python …`
- 셸에 conda가 없으면 `%USERPROFILE%\anaconda3\envs\pro_1\python.exe`를 직접 부른다.
- 패키지를 더하면 `environment.yml`도 고친다.

프론트(Vue)는 `frontend/`에서 `npm install` 후 `npm run dev` / `npm run verify`(린트·단위 테스트·빌드) / `npm run test:e2e`. 백엔드·DB 실행 명령은 각 폴더의 `AGENTS.md`에 있다(코드 전이면 '예정').

### 검증 (커밋 전)

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1
```

- 한 번에 돈다: ruff 린트 → ruff 포맷 확인 → pytest(`backend/tests`·`db/tests`에 테스트 파일이 있을 때) → 프론트 `npm run verify`. `-E2E`를 붙이면 Playwright까지, `-Fix`는 고칠 수 있는 것을 먼저 고친다.
- 파이썬 린트·포맷은 **Ruff 하나**로 한다(flake8·isort·black을 따로 두지 않는다). 규칙은 루트 `ruff.toml`. 폴더마다 다르게 해야 하면 그 폴더에 `ruff.toml`을 두고 `extend = "../ruff.toml"`로 이어 쓴다.
- 따로 돌릴 때: `conda run -n pro_1 ruff check .` / `conda run -n pro_1 ruff format .`
- 규칙을 끄려면 줄 끝 `# noqa: 코드 이유`로 그 줄만 끄고 이유를 적는다. 통과시키려고 `ruff.toml`에서 규칙을 통째로 빼지 않는다.

## 금지

- `.env`, 비밀번호, JWT 키, AWS 키를 파일에 쓰거나 커밋하지 않는다. 예시는 `.env.example`에 이름만.
- 로그(`app.log`·`events.log`·Nginx)에 이메일·비밀번호·토큰·휴대폰·생년월일을 남기지 않는다. 사람은 `user_id`로만 가리킨다.
- AWS 리소스 생성·변경·삭제, 요금이 나가는 명령은 실행하지 않는다. 사람이 한다. AWS 구성은 프리 티어 안에서 정한다(`docs/AWS_프리티어_구성.md`).
- Docker 등 무거운 프로그램을 사람에게 묻지 않고 켜지 않는다.
- DB `DROP`·`TRUNCATE`·대량 `DELETE`는 로컬 테스트 스키마(`spacecube_test`) 외에는 하지 않는다.
- 외부 사이트 크롤링은 `crawler/AGENTS.md` 규칙 안에서만. 실행당 상세 페이지 20건을 넘기려면 사람 승인을 받는다.
- 테스트를 통과시키려고 테스트나 제약 조건을 약하게 고치지 않는다.

## 쓰는 방식

- 문서·주석·커밋 메시지는 한국어, 코드 식별자는 영어.
- 새 폴더를 만들면 그 폴더 역할을 적은 `README.md`를 같이 만들고 `STRUCTURE.md` 트리에도 한 줄 더한다.
- 커밋 메시지: `[파트] F-ID 요약` (예: `[B] F-30 예약·결제 트랜잭션`). 파트는 FE, A, B, DB, 공동.
- GitHub 규칙: 이슈 → `develop`에서 브랜치 `feat/<파트>-<F-ID>` → `develop`으로 PR → 리뷰 1명 → Squash 머지. `main`·`develop`에 바로 푸시 금지, 검증이 같은 원인으로 2번 실패하면 멈추고 사람에게. 자세한 것은 [`CONTRIBUTING.md`](CONTRIBUTING.md). 작업 전 `gh issue view <번호>`로 완료 조건·기준 문서를 읽고, 진행 상태는 Project 보드(`gh project item-list 5 --owner encore-ai-campus`)에서 본다.

## 작업을 끝낼 때

1. 돌린 테스트와 결과를 그대로 보고한다. 못 돌렸으면 못 돌렸다고 쓴다.
2. `STATE.md`의 담당 파트 줄, 기능 진행표, '최근 변경'을 고친다.
3. 새로 정한 것이 있으면 `STATE.md` '결정 기록'에 한 줄 쓰고, 해당 기준 문서도 고친다.
