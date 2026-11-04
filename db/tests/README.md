# tests — 제약 조건 검증

백엔드 코드 없이 SQL만으로 DB가 막아야 할 것을 막는지 확인합니다. `spacecube_test`에서 돌립니다.

## 지금 있는 시험 (11-04, 모두 통과)

| 파일 | 하는 일 | 실행 |
| --- | --- | --- |
| `check_ddl.py` | `migrations/0001_init.sql`로 `spacecube_test`를 새로 만들고, 아래 표의 01~06과 같은 칸 동시 결제까지 29건을 시험 | `conda run -n pro_1 --no-capture-output python db/tests/check_ddl.py` |
| `check_mongo_init.js` | `mongo_init.js` 뒤에 붙여 검증기·고유 인덱스·TTL 13건(아래 07) | `mongosh "mongodb://127.0.0.1:27017" docs/db/mongo_init.js db/tests/check_mongo_init.js` (Docker면 두 파일을 컨테이너로 복사해 `docker exec … mongosh`) |

- `check_ddl.py`는 `backend/.env`의 `DB_WRITE_URL`(DB 이름이 `spacecube_test`여야 함)로 접속하고, 비밀번호는 환경 변수로만 클라이언트에 넘깁니다. MariaDB 클라이언트 경로가 다르면 `MARIADB_BIN`을 줍니다.
- 이름이 `test_`로 시작하지 않아 `verify.ps1`의 pytest가 자동으로 돌리지 않습니다(로컬 DB가 있어야 하므로). 결과 기록: `docs/기록/검증_2026-11-04_DDL실행.md`.

## 처음 계획한 항목

| 파일 (계획, 위 두 파일이 01~07을 대신함) | 확인하는 것 | 기대 결과 |
| --- | --- | --- |
| `01_slot_unique.sql` | 같은 (venue_id, slot_date, slot_hour)에 두 번째 INSERT | 1062 Duplicate entry |
| `02_slot_fk_match.sql` | 예약과 다른 공간·날짜로 칸 INSERT | 외래키 오류 |
| `03_hours_check.sql` | 5시간 예약, 끝 시각 ≤ 시작 시각, `min_hours` 0·5 | CHECK 오류 |
| `04_review_once.sql` | 같은 예약에 후기 두 번 | 1062 Duplicate entry |
| `05_cancel_frees_slots.sql` | 칸 DELETE 후 같은 칸 다시 INSERT | 성공 |
| `03b_hour_range.sql` | 영업 8시 시작 공간, 23시 시작 예약, 칸 23 | CHECK 오류 (9~23 밖) |
| `03c_users_consent.sql` | `terms_agreed_at`·`privacy_agreed_at` 없이 회원 INSERT | NOT NULL 오류 |
| `06_payment_refund_check.sql` | `refunded`인데 `refunded_at` 없음 | CHECK 오류 |
| `07_mongo_validator.js` | 필수 필드 빠진 이벤트, 같은 `event_id` 두 번 | 거절 / 1건만 |
| `test_concurrent_insert.py` | 50개 연결에서 같은 칸 동시 INSERT | 1건만 성공 |

- 이 검사가 통과해야 FastAPI B의 동시성 테스트(50건 중 1건만 성공)도 의미가 있습니다.
- 파이썬 테스트 파일이 생기면 루트 `verify.ps1`이 pytest로 같이 돌립니다.
