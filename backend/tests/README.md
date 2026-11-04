# tests — pytest (담당: A·B 각자)

자기가 만든 라우터 파일과 같은 이름으로 테스트를 둡니다. 파일별 확인 항목은 [백엔드_A 7절](../../docs/백엔드_A_회원_후기_이벤트.md), [백엔드_B 8절](../../docs/백엔드_B_공간_예약_결제_크롤링.md).

| 파일 | 담당 | 꼭 확인할 것 |
| --- | --- | --- |
| `test_auth.py` | A | 이메일 중복 409 `EMAIL_TAKEN`, 가입 직후 로그인 성공, 토큰 없이 회원 전용 API 401 |
| `test_users.py`, `test_reviews.py` | A | `password_hash` 없음, 후기 자격 404·403·403·409, 작성 직후 내 후기에 보임 |
| `test_events.py` | A | 51건 400, MongoDB가 꺼져도 202이고 `events.log`에는 남음, replay해도 중복 없음 |
| `test_models_match_db.py` | A | `app/models`의 표·컬럼 이름·NULL 여부가 `spacecube_test`의 실제 표와 같은지 (SQLAlchemy `inspect`) |
| `test_health.py`, `test_db_routing.py`, `test_metrics.py` | A | primary 끊김 503 / replica·MongoDB 끊김 200 degraded, replica 주소가 틀려도 공개 조회 성공 |
| `test_catalog.py`, `test_venues.py` | B | 필터·정렬, 칸 상태(taken·past), 예약 가능 날짜(`min_hours`) |
| `test_reservations.py` | B | 성공 201(표 3개 모두 생김), 범위 밖 400, 취소 후 칸 반납·환불, 예약 직후 `/reservations/me`에 보임 |
| `test_concurrency.py` | B | **같은 칸 동시 50건 → 201 정확히 1건, 409 49건** (MVP 통과 조건), `detail.slots` 정확 |
| `test_jobs.py`, `test_internal.py`, `test_read_routing.py` | B | 완료 배치 멱등, upsert 201·200·400, 공개 조회만 `get_db_read` |

- 테스트 DB는 로컬 MariaDB(`infra/local`)의 `spacecube_test`. SQLite는 제약 동작이 달라 쓰지 않습니다.
- 동시성 테스트는 스레드 50개로 요청을 한꺼번에 보냅니다.
