# generator — 오프라인 대량 생성기 (담당: DB)

공간이 부족하면 먼저 시연용 공간을 생성해 `POST /internal/venues`로 등록합니다(공간 등록 경로는 한 곳). 그다음 과거 사용자 행동 데이터는 API를 거치지 않고 MariaDB·MongoDB에 씁니다. 날짜는 실제 날짜 기준이고(가상 시계 없음, 11-03), 오늘 이전만 만듭니다.

## 입력

| 설정 | 예 |
| --- | --- |
| 기간 | 오늘 이전 N일 (1차 30일, 필요할 때 90일. **365일 넘기지 않음**: `user_events` TTL이 `ts` 기준 365일이라 더 오래된 이벤트는 넣자마자 지워짐) |
| 공간 | 속성 기반 공간의 최종 등록 수를 먼저 확인. 생성기 공간을 `/internal/venues`에 등록해 합계 30개 목표로 채운 뒤 DB의 venues 전체를 사용 |
| 사용자 풀 | 하루 방문 × 2.5명 |
| 시드 | 고정 (같은 시드면 같은 결과) |

## 하루를 만드는 순서

1. 그날 예약 가능한 칸 수를 센다 → 하루 방문 수로 쓴다.
2. 방문마다 사용자를 뽑고 유형별 규칙(`../README.md`)으로 행동한다: 검색 → 상세 → 칸 선택 → 예약 시도 / 포기.
3. 예약은 `reservations`+`reservation_slots`+`payments`를 함께 넣고, 칸은 기본키를 거친다. 막히면 대안을 1~2번 찾는다.
4. 상태는 `completed`(지난 이용) 또는 `cancelled`, 후기는 completed 예약에만 일정 비율로 만든다.
5. 모든 행동을 MongoDB `user_events`에 세션 단위로 남긴다. 이벤트 이름은 `docs/백엔드_A` 5-3 목록만, `event_id`는 UUID.

가상 회원은 만 14세 이상 생년월일로 만들고, `terms_agreed_at`·`privacy_agreed_at`은 가입 시각과 같게 넣습니다. 예약 시간은 9~23시 안(DB CHECK).

## 출력

| 대상 | 내용 |
| --- | --- |
| `/internal/venues` | 부족한 시연용 공간(`source_site = "synthetic"`, `source_id`는 재실행 시에도 같은 값) |
| MariaDB | users, reservations, reservation_slots, payments, reviews (`is_synthetic = true`) |
| MongoDB | user_events (`is_synthetic = true`, `server = "generator"`), event_daily |

데이터량 추정은 `docs/산출물_04_DB명세서.md` 10절을 따릅니다.

1차 백필은 과거 30일분을 목표로 하며, 실제 방문·예약 수요의 관측치가 아니라 구조와 집계 흐름을 검증하는 가상 데이터입니다. 공간 속성을 외부 사이트에서 참고했더라도 실제 업체의 예약 가능 여부를 뜻하지 않습니다. 모든 생성 회원·예약·이벤트는 `is_synthetic = true`로 구분합니다.
