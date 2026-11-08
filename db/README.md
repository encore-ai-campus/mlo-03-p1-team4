# db — MariaDB·MongoDB 스키마와 데이터 (담당: DB)

> **11-05 결정:** 1차 배포는 로컬 VM입니다. MariaDB primary는 `db1`(노트북 1), replica는 `db2`(노트북 3, GTID 복제), MongoDB는 `mongo`(노트북 1) VM입니다([로컬 VM 구성](../docs/로컬_VM_구성.md)). 아래의 RDS·EC2 내용은 AWS 참고안입니다. (DB 담당 파일: 안내 한 줄만 더함)

기준은 [DB 명세서](../docs/산출물_04_DB명세서.md)입니다. MariaDB 표는 이 폴더 [`migrations/0001_init.sql`](migrations/0001_init.sql)이 기준입니다(11-04 실행 검증 뒤 옮김). MongoDB 초기화는 [docs/db/mongo_init.js](../docs/db/mongo_init.js).

| 저장소 | 무엇 | 위치 |
| --- | --- | --- |
| MariaDB 11.4 (RDS primary + read replica) | 표 12개(regions, categories, facilities, users, venues, venue_facilities, venue_images, reservations, reservation_slots, payments, reviews, crawl_jobs) + 뷰 `v_venue_rating` | `migrations/0001_init.sql` |
| MongoDB 7 | `space_rental_analytics.events`(TTL 365일), `event_daily`, `crawl.crawl_raw` (11-06 F-60 새 구조) | `docs/db/mongo_init.js` |

| 폴더 | 내용 |
| --- | --- |
| `migrations/` | 표 생성·변경 이력 |
| `seed/` | 유형 5개, 시설, 지역 기초 데이터 |
| `views/` | 백엔드가 읽는 뷰 (`v_venue_rating`) |
| `loaders/` | 기초 데이터·가상 데이터 대량 적재 |
| `tests/` | 중복 예약 차단·외래키·CHECK 검증 |

## 환경

- 로컬: `infra/local`의 docker compose로 MariaDB·MongoDB 실행
- 배포: RDS for MariaDB primary(2a) + read replica(2c), 프라이빗 서브넷 / MongoDB는 퍼블릭 서브넷 EC2 + 보안 그룹 + 인증
- 문자셋 `utf8mb4_unicode_ci`, 엔진 InnoDB, 시간대 Asia/Seoul (MongoDB는 UTC 저장)
- 계정: `app_rw`(primary), `app_ro`(replica), `exporter` / Mongo `app`·`analyst`·`exporter` (명세 13절)

## 다른 파트에 주는 것

| 무엇 | 받는 쪽 | 언제 |
| --- | --- | --- |
| DDL 실행 검증 → `migrations/0001_init.sql` | A, B | 1일차 오전 |
| 유형·시설·지역 seed | B, 프론트 | 1일차 |
| `v_venue_rating` 뷰 | A, B | 0001에 포함 |
| `mongo_init.js` 실행(인덱스·TTL·검증 규칙) | A | 1일차 |
| 크롤링 공간(→ `/internal/venues`), 가상 과거 예약·이벤트 | B, 프론트, 분석 | 2~3일차 |

표·컬럼 이름을 바꾸면 A·B 코드가 깨지므로, 바꾸기 전에 두 사람에게 알리고 문서도 같이 고칩니다.
