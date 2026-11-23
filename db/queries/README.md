# 판매·이용·취소·행동 분석 쿼리 (#119)

이 폴더는 **조회만** 한다. `db/migrations/0001_init.sql`의 공간·예약·결제 테이블과 `space_rental_analytics.events` v1을 기준으로 작성했다. 운영 DB에서 실행할 때는 읽기 전용 계정을 사용하고, 날짜·합성 데이터 포함 여부를 각 파일 맨 위에서 정한다. 종료일은 포함하지 않는다. 결과에는 업체 실명이나 개인정보를 넣지 않는다.

| 파일 | 기간 기준 | 결과의 뜻 |
| --- | --- | --- |
| `sales_by_venue.sql` | `payments.paid_at` | 결제된 예약의 당시 금액, 현재 환불액과 현재 순액 |
| `usage_by_venue.sql` | `reservations.reserve_date` | 완료·확정·취소 건과 예약된 시간·인원. 실제 출입 인원은 아님 |
| `cancellations_by_venue.sql` | `reservations.created_at` | 해당 기간 생성 예약 중 현재 취소 비율. 취소일별 비율은 아님 |
| `reservation_quality.sql` | 전체 | 예약·결제·칸 정합성 오류 수. 각 결과가 0이어야 함 |
| `event_behavior.js` | `events.occurred_at` | 상품별 행동 건수와 행동별 고유 세션 수 |

MariaDB 셸에서 `SOURCE db/queries/sales_by_venue.sql;`처럼 실행한다. 상대 경로는 저장소 루트에서 셸을 시작한 경우다. `usage_by_venue.sql`, `cancellations_by_venue.sql`, `reservation_quality.sql`도 같은 방식으로 실행한다. 결과를 저장할 때에는 실행 시각·DB 환경·쿼리 커밋·기간·`include_synthetic`·원본 건수를 함께 적는다. 계정 정보와 개인 정보는 결과 파일에 넣지 않는다.

`event_behavior.js`는 `mongosh`에서 `--file`로 실행한다. `product_id`는 공간 ID의 문자열이고 SQL의 `venue_id`와 대응한다. 이벤트 단계별 `session_count`는 각 행동을 한 세션의 수이며, 단계 간 순서·동일 세션의 실제 전환을 검증하지 않는다. `event_daily`의 `count`도 이벤트·상품 행 수이지 고유 세션 수가 아니다. 서버 이벤트에 브라우저 세션 ID가 전달되지 않으면 `server-<request_id>`가 쓰일 수 있으므로, **이 결과를 전환율로 표시하지 않는다**. 합성 이벤트는 기본 포함이며 실제 사용자 행동을 보려면 `includeSynthetic = false`로 바꾼다.

판매액은 실제 결제 정산액이 아닌 **모의 결제 예약 금액**이다. 환불 시점이 아니라 결제 기간에 묶인 예약의 현재 환불 상태로 순액을 계산한다. `venues.price_per_hour`는 바뀔 수 있으므로 과거 판매액 계산에 쓰지 않는다. 취소된 예약의 칸은 삭제되므로 `reservation_slots`에서 취소 이용시간을 추정하지 않는다.

현재 브랜치는 로컬 SQL 실행 결과나 운영 수치를 포함하지 않는다. 서버에 접근할 수 있을 때 `reservation_quality.sql`부터 실행해 0건인지 확인하고, 같은 기간의 SQL·이벤트 결과를 기록한다. 운영 실행과 정식 부하 대사는 #120에서 추적한다.
