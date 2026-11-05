# routers — 엔드포인트

파일 단위로 A·B가 나뉘어, 서로 다른 파일만 고칩니다. DB 열: W `get_db_write`(primary), R `get_db_read`(replica).

| 파일 (예정) | 담당 | 엔드포인트 | DB |
| --- | --- | --- | --- |
| `health.py` | A | `GET /health` (primary·replica·MongoDB 3단계) | — |
| `auth.py` | A | `GET /auth/email-check`, `POST /auth/signup`, `POST /auth/login` | W |
| `users.py` | A | `GET·PATCH·DELETE /users/me`, `PATCH /users/me/password`, `GET /users/me/reviews` | W |
| `reviews.py` | A | `POST /reservations/{id}/review`, `PATCH·DELETE /reviews/{id}` | W |
| `reviews.py` | A | `GET /venues/{id}/reviews`, `GET /reviews` | R |
| `events.py` | A | `POST /events` (최대 50건 묶음, 202) | — (로그 파일 + MongoDB) |
| `catalog.py` | B | `GET /categories`, `GET /regions`, `GET /facilities` | R |
| `venues.py` | B | `GET /venues`(검색), `GET /venues/new`, `GET /venues/{id}`, `GET /venues/{id}/available-dates`, `GET /venues/{id}/slots` | R |
| `reservations.py` | B | `POST /reservations`(F-30~32 예약+결제 구현), `POST /reservations/{id}/cancel`(F-34 예정) | W |
| `reservations.py` | B | `GET /reservations/me`, `GET /reservations/{id}` | W |
| `internal.py` | B | `POST /internal/venues` (크롤러 전용, `X-Internal-Key`) | W |

- 경로가 겹치는 곳 주의: `/reservations/{id}/review`와 `/venues/{id}/reviews`는 A(`reviews.py`)입니다. 나머지 `/reservations/*`, `/venues/*`는 B입니다.
- 회원 전용 엔드포인트는 `Depends(get_current_user)`를 붙입니다.
- 없는 것: `/rooms/*`, `/posts`, `/comments`, `/reservations/{id}/confirm` (11-03에 삭제).
- 요청·응답 모양: [백엔드_A 5절](../../../docs/백엔드_A_회원_후기_이벤트.md), [백엔드_B 5절](../../../docs/백엔드_B_공간_예약_결제_크롤링.md)
