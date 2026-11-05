# repositories — SQL 접근

표에 직접 닿는 코드는 여기만 둡니다. 표 담당은 아래와 같고, 남의 표는 그 파트가 만든 함수로만 읽습니다. 세션(primary/replica)은 호출하는 쪽이 넘깁니다.

| 파일 (예정) | 담당 | 표 |
| --- | --- | --- |
| `user_repo.py` | A | users |
| `review_repo.py` | A | reviews, `v_venue_rating`(읽기) |
| `catalog_repo.py` | B | categories, regions, facilities |
| `venue_repo.py` | B | venues, venue_facilities, venue_images(조회·F-61 출처별 등록/갱신·시설/그림 전체 교체), `v_venue_rating`(읽기) |
| `slot_repo.py` | B | reservation_slots (조회·예약 INSERT·충돌 조회) |
| `reservation_repo.py` | B | reservations (생성·10분 재시도 조회·`get_owned`) |
| `payment_repo.py` | B | payments (모의 결제 INSERT) |

- 사용자 이벤트는 표가 아니라 `core/events.py`(로그 파일 + MongoDB)가 씁니다. `crawl_jobs`·MongoDB `crawl_raw`는 크롤러(DB 담당)가 씁니다.

## 파트끼리 쓰는 함수 (약속)

| 함수 | 제공 | 사용 | 반환 |
| --- | --- | --- | --- |
| `reservation_repo.get_owned(db, user_id, reservation_id)` | B | A (후기 작성 자격, primary 세션) | `Reservation(reservation_id, venue_id, reserve_date, start_hour, end_hour, status, created_at)` 또는 `None` |
| `reservation_repo.count_cancellable(db, user_id)` | B | A (탈퇴 전 확인, 같은 primary 세션) | 시작 전 `confirmed` 예약 수(`int`), 시작 정각·이용 중·완료·취소 제외. 커밋은 호출자가 관리 |

표·컬럼 이름은 `docs/산출물_04_DB명세서.md`(검증 후 `db/migrations`)가 기준입니다. 바꾸고 싶으면 DB 담당에게 요청합니다.
