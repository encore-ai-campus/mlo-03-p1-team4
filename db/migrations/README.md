# migrations — 표 생성·변경 이력

**SQL 파일로 관리합니다**(11-03 결정, Alembic 안 씀). 번호 순서대로 손으로 실행하고, 백엔드 ORM 모델(`backend/app/models/`)은 이 파일에 맞춰 씁니다. 모델에서 표를 만들지 않습니다.

## 첫 버전 (0001_init) — 11-04 옮김

[`0001_init.sql`](0001_init.sql)은 11-03 수정안을 로컬 MariaDB 11.8에서 실행 검증(제약 시험 29건 통과, `db/tests/check_ddl.py`)한 뒤 그대로 옮긴 것입니다. `CREATE DATABASE`·`USE` 줄은 뺐습니다. 빈 스키마를 만들고 고른 다음 한 번만 실행합니다.

```bash
mariadb -h <호스트> -u <관리자> -p spacecube < db/migrations/0001_init.sql
```

외래키 때문에 만드는 순서가 정해져 있고, 파일이 이미 그 순서입니다.

1. regions, categories, facilities, users
2. venues → venue_facilities, venue_images
3. reservations → reservation_slots, payments, reviews
4. crawl_jobs
5. 뷰 v_venue_rating

## 처음 돌릴 때 확인할 것 (11-04 로컬에서 모두 확인, RDS 11.4에서 `check_ddl.py`로 한 번 더)

- [x] `reservation_slots`의 복합 외래키 `(reservation_id, venue_id, slot_date)` → `reservations(reservation_id, venue_id, reserve_date)`가 만들어지는지
- [x] `reservations` CHECK(시간 1~4칸, 끝 > 시작), `venues` CHECK(`min_hours` 1~4, 가격 > 0), `users` CHECK(birth 6자리, gender_digit 1~4)가 실제로 막는지
- [x] 시간 범위 CHECK(영업 open 9~22·close 10~23, 예약 시작 9~22·끝 ≤ 23, 칸 9~22)와 `users` 필수 동의 2칸 NOT NULL (11-03 A2)
- [x] `payments` CHECK `(status='refunded') = (refunded_at IS NOT NULL)`
- [x] `reviews.rating` CHECK 1~5, `reviews.reservation_id` UNIQUE

## 규칙

- 이미 다른 사람 DB에 적용된 마이그레이션 파일은 고치지 않고, 새 파일로 변경합니다.
- 파일 이름: `0002_add_xxx_index.sql`처럼 번호 + 무엇을 바꾸는지.
- 마이그레이션을 바꾸면 `docs/산출물_04_DB명세서.md`의 해당 표와 `backend/app/models/`의 모델도 같이 고칩니다(모델은 표 담당 파트에 요청). `test_models_match_db.py`가 어긋남을 잡습니다.
