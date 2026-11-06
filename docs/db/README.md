# docs/db — DB 초기화 파일

| 파일 | 내용 |
| --- | --- |
| `mongo_init.js` | MongoDB 7 (11-06 F-60 새 구조, #68): `space_rental_analytics.events`(이벤트 15종 strict 검증, 서버 결과 3종만 화면 문맥 null, `uq_event_id`, `received_at` TTL 365일)·`event_daily`(고유 인덱스)·`crawl.crawl_raw`. 옛 `spacecube.user_events` 초기화는 삭제(이미 만든 DB의 문서는 지우지 않음). 검증 `db/tests/check_mongo_init.js` |
| `spacecube_mariadb.sql` | 11-04에 [`db/migrations/0001_init.sql`](../../db/migrations/0001_init.sql)로 옮겼다는 안내만 남김. MariaDB 표는 마이그레이션이 기준 |

- 검증 기록: [`docs/기록/검증_2026-11-04_DDL실행.md`](../기록/검증_2026-11-04_DDL실행.md)
- 남은 것: RDS 11.4에서 `db/tests/check_ddl.py`를 한 번 더 돌리기
- 비밀번호·접속 주소는 이 파일들에 적지 않습니다. `.env`에만 둡니다.
