# 공간대여 예약 시스템 — FastAPI 기능과 2파트 분담

2026-10-30 · 작성 노진산

FastAPI 담당 2명은 **도메인 기준**으로 나눕니다. A는 '사람과 글'(회원·인증·후기·게시판·활동 로그), B는 '공간과 예약'(공간·검색·예약·결제·크롤링 등록)입니다. B 쪽에 동시성 처리가 몰려 더 무거우므로, 공통 모듈과 인증은 A가 맡아 균형을 맞춥니다.

서버 2대(FastAPI #1, #2)는 같은 코드를 똑같이 띄운 것이라 이 분담과는 관계없습니다. 두 사람의 코드는 한 저장소, 한 앱으로 합쳐집니다.

## 나누는 기준

| 기준 | 기능별로 나누기 (채택) | 계층별로 나누기 (라우터 vs DB 로직) |
| --- | --- | --- |
| 충돌 | 각자 다른 파일을 고침 | 같은 기능을 둘이 함께 고쳐 충돌이 잦음 |
| 책임 | "예약 버그 = B"처럼 분명함 | 버그마다 누구 몫인지 따져야 함 |
| 테스트 | 각자 자기 기능 끝까지 테스트 | 한쪽이 끝나야 다른 쪽이 테스트 가능 |
| 단점 | 두 파트가 만나는 지점(후기 작성 자격, 마이페이지)에 약속이 필요 | — |

## API 목록

인증 열: `-` 누구나, `회원` 로그인 필요, `관리자`, `내부` 크롤러 전용 키.

### 파트 A — 회원·인증·후기·게시판·로그

| 메서드 | 경로 | 설명 | 인증 | 기능 |
| --- | --- | --- | --- | --- |
| POST | /auth/signup | 회원가입 | - | F-01 |
| GET | /auth/email-check?email= | 이메일 중복 확인 | - | F-01 |
| POST | /auth/login | 로그인, 액세스 토큰(JWT) 발급 | - | F-02 |
| GET | /users/me | 내 정보 | 회원 | F-03 |
| PATCH | /users/me | 내 정보 수정 | 회원 | F-03 |
| PATCH | /users/me/password | 비밀번호 변경 | 회원 | F-03 |
| DELETE | /users/me | 탈퇴 (소프트 삭제) | 회원 | F-04 |
| POST | /reservations/{reservation_id}/review | 후기 작성 (이용 완료한 내 예약만) | 회원 | F-50 |
| PATCH | /reviews/{review_id} | 후기 수정 | 회원 | F-50 |
| DELETE | /reviews/{review_id} | 후기 삭제 | 회원 | F-50 |
| GET | /rooms/{room_id}/reviews | 룸별 후기 | - | F-51 |
| GET | /reviews?category=&sort=&page= | 전체 후기 게시판. sort: recent(기본)·high(별점 높은 순)·low(별점 낮은 순) | - | F-51 |
| GET | /users/me/reviews | 내 후기 | 회원 | F-41 |
| GET | /posts?board=&q=&page= | 게시글 목록·검색 | - | F-52 |
| POST | /posts | 글쓰기 (notice는 관리자만) | 회원 | F-52, F-53 |
| GET | /posts/{post_id} | 글 상세 (조회수 +1) | - | F-52 |
| PATCH | /posts/{post_id} | 글 수정 | 회원 | F-52 |
| DELETE | /posts/{post_id} | 글 삭제 | 회원 | F-52 |
| POST | /posts/{post_id}/comments | 댓글 작성 | 회원 | F-52 |
| DELETE | /comments/{comment_id} | 댓글 삭제 | 회원 | F-52 |
| POST | /events | 활동 로그 묶음 전송 (최대 50건) | - | F-60 |

### 파트 B — 공간·검색·예약·결제·크롤링

| 메서드 | 경로 | 설명 | 인증 | 기능 |
| --- | --- | --- | --- | --- |
| GET | /categories | 유형 5개 | - | F-10 |
| GET | /regions?sido= | 시도 목록 / 시군구 목록 | - | F-11 |
| GET | /rooms | 검색: q, category, sido, sigungu, date, start_hour, hours, people(최소 수용 인원), facilities(쉼표로 구분, 모두 갖춘 곳), now(true면 오늘 지금 이후 빈 칸이 있는 곳만), sort, page, size(기본 10, 프론트는 '더 보기'로 다음 page를 붙임 — **B 확인 필요**). 각 항목에 그 date의 칸 상태 `slots: [{hour, taken, past}]`를 함께 담음 | - | F-12, F-13 |
| GET | /rooms/new | NEW 공간 | - | F-14 |
| GET | /rooms/{room_id} | 상세: 이미지, 설명, 홍보 문구, 가격, 시설, 공간, 평점 | - | F-20 |
| GET | /rooms/{room_id}/available-dates?days=14 | 예약할 수 있는 날짜: 그날 이어진 빈 칸(마감·지난 칸 제외)이 그 공간의 `min_hours` 이상인 날 (11-01 프론트 제안, **B 확인 필요**) | - | F-21 |
| GET | /rooms/{room_id}/slots?date= | 그 날짜의 1시간 칸 상태 | - | F-22 |
| POST | /reservations | 예약 신청: 결제 대기로 칸 선점. 칸 충돌이면 409 | 회원 | F-30, F-32 |
| POST | /reservations/{reservation_id}/confirm | 확정 = 모의 결제 성공 → confirmed + payments | 회원 | F-31 |
| POST | /reservations/{reservation_id}/cancel | 취소, 칸 반납, 결제 refunded | 회원 | F-34 |
| GET | /reservations/me?status= | 내 예약 내역 (예정·완료·취소) | 회원 | F-40 |
| GET | /reservations/{reservation_id} | 예약 상세 | 회원 | F-40 |
| POST | /internal/venues | 크롤러가 신규 공간·룸 등록 (upsert) | 내부 | F-61 |

### 공통

| 메서드 | 경로 | 설명 | 담당 |
| --- | --- | --- | --- |
| GET | /health | Nginx 헬스체크 (DB 연결 확인 포함) | A |

배치 작업 2개는 API가 아니라 주기 실행 스크립트로 B가 맡습니다.

- **결제 대기 만료(F-33):** 1분마다 `expires_at`이 지난 pending을 expired로 바꾸고 칸 삭제
- **이용 완료 처리:** 1시간마다 이용 종료 시각이 지난 confirmed를 completed로 변경. A의 후기 작성 자격이 이 값에 기댑니다.

## 예약 신청 흐름 (파트 B 핵심)

```
POST /reservations {room_id, date, start_hour, hours, headcount}
  1. 검증: 로그인, 14일 안, 영업시간 안, 최소·최대 시간, 인원 범위
  2. BEGIN
  3. INSERT reservations (status=pending, expires_at=NOW()+10분, total_price=가격×시간)
  4. INSERT reservation_slots × hours   ← 같은 칸이 있으면 중복 키 오류
  5. 오류면 ROLLBACK → 409 {"code": "SLOT_TAKEN", "slots": [13]}
     성공이면 COMMIT → 201 {reservation_id, expires_at, total_price}
  6. user_events에 reserve_try / reserve_ok / reserve_conflict 기록
```

같은 칸에 동시 요청 50개를 보내 정확히 1개만 201을 받는지가 MVP 통과 조건입니다(`MVP_시뮬레이션_크롤링_수치.md`).

## 두 파트가 만나는 곳 (약속)

| 지점 | 제공 | 사용 | 약속 내용 |
| --- | --- | --- | --- |
| 로그인 사용자 | A | B | `get_current_user()` 의존성 → `{user_id, role}`. 토큰 없거나 틀리면 401 |
| 후기 작성 자격 | B | A | `reservations.get_owned(user_id, reservation_id)` 함수 → status가 completed인지 A가 확인 |
| 룸 평점 | A | B | 룸별 평균 별점·후기 수는 DB 뷰 `v_room_rating`(DB 담당이 생성)으로 B가 조회 |
| 마이페이지 | A, B | 프론트 | 프론트가 `/users/me`(A)와 `/reservations/me`(B)를 각각 호출해 한 화면에 합침 |
| 활동 로그 | A | B, 프론트 | 서버 쪽 이벤트(reserve_ok 등)도 A가 만든 `log_event()` 함수로 기록 |

## 공통 규칙 (A가 먼저 만듦)

- **폴더 구조:** 기존 수업 코드처럼 `routers/` 아래 파일을 파트별로 둡니다.

```
app/
  main.py                # 라우터 등록, CORS, 예외 처리기
  core/                  # [A] 설정, DB 세션, 보안(JWT·비밀번호 해시), 공통 오류, 페이지네이션
  routers/
    auth.py users.py reviews.py posts.py events.py      # [A]
    catalog.py rooms.py reservations.py internal.py     # [B]
  schemas/  services/  repositories/                     # 같은 이름 규칙으로 파트별 파일
  jobs/
    expire_pending.py complete_reservations.py           # [B]
tests/
```

- **오류 응답:** `{"code": "SLOT_TAKEN", "message": "...", "detail": {...}}` 한 가지 형식. 400 검증 실패, 401 인증, 403 권한, 404 없음, 409 충돌(칸 선점·이메일 중복·후기 중복).
- **목록:** `?page=1&size=20` → `{"items": [...], "page": 1, "size": 20, "total": 132}`
- **시간:** DB와 API 모두 Asia/Seoul. 날짜는 `YYYY-MM-DD`, 칸은 정수 시(9~22).
- **가상 데이터:** 요청 헤더 `X-Synthetic: 1`이 있으면 저장할 때 `is_synthetic = true` (Locust·생성기 전용).

## 작업 순서

| 주차 | 파트 A | 파트 B |
| --- | --- | --- |
| 1주 | core(설정·DB 세션·JWT·오류 형식), 회원가입·로그인 | categories·regions·rooms 조회(DB 담당의 기초 데이터 사용) |
| 2주 | 내 정보·탈퇴, 게시판·댓글 | 칸 조회, 예약 신청(트랜잭션·409), 동시성 테스트 |
| 3주 | 후기(작성 자격은 B 함수 사용), 활동 로그 /events | 확정·취소·내 예약, 만료·완료 배치 |
| 4주 | 통합 테스트, Locust 시나리오 지원 | 검색 필터·정렬·NEW, /internal/venues와 크롤러 연결 |

1주차 끝에 A의 `get_current_user()`가 나와야 B가 회원 전용 API를 만들 수 있으므로, 그 전까지 B는 공개 API부터 만듭니다.

## 정해야 할 것

- [ ] 토큰 방식: 액세스 토큰만(만료 1시간) 쓸지, 리프레시 토큰을 둘지
- [ ] ORM: SQLAlchemy 2.0 + Alembic으로 갈지 (DB 담당과 함께 결정)
- [ ] `/internal/venues` 보호 방식: 내부 API 키 헤더 vs 사설 IP만 허용(Nginx)
