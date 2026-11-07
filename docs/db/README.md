# docs/db — DB 초기화 파일

**11-07 운영 기준:** [DB 운영·모니터링 현황](../DB_운영_모니터링_현황_2026-11-07.md). 실제 시험 서버는 MariaDB 10.11.14 / MongoDB 8.0.34, 원천 이벤트는 space_rental_analytics.events다. 이 작업 폴더의 초기화 코드는 이전 user_events 형식이므로 최신 배포 파일과 대조 없이 운영에 재적용하지 않는다. 아래 11-04 검증은 이력이다.

| 파일 | 내용 |
| --- | --- |
| `mongo_init.js` | MongoDB 7: `user_events`(검증 규칙·TTL 1년)·`event_daily`·`crawl_raw`, 인덱스, 계정 안내. **11-04 로컬 실행 검증 끝**(`db/tests/check_mongo_init.js`) |
| `spacecube_mariadb.sql` | 11-04에 [`db/migrations/0001_init.sql`](../../db/migrations/0001_init.sql)로 옮겼다는 안내만 남김. MariaDB 표는 마이그레이션이 기준 |

- 검증 기록: [`docs/기록/검증_2026-11-04_DDL실행.md`](../기록/검증_2026-11-04_DDL실행.md)
- 과거 AWS 참고안의 후속(현재 VM 완료 조건 아님): RDS 11.4에서 `db/tests/check_ddl.py`를 한 번 더 돌리기
- 비밀번호·접속 주소는 이 파일들에 적지 않습니다. `.env`에만 둡니다.
