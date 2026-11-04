# loaders — 대량 적재

| 스크립트 | 입력 | 넣는 곳 | 언제 |
| --- | --- | --- | --- |
| `load_seed.py` (11-04) | `seed/*.csv` | `seed/seed.sql`을 만듦 → categories, facilities, regions | CSV를 고칠 때. `--check`로 표본 주소 확인 |
| `load_synthetic.py` (예정) | `simulator/generator` 출력 | MariaDB users, reservations, reservation_slots, payments, reviews / MongoDB user_events | 과거 데이터 백필 |

## 공간은 여기서 넣지 않는다

크롤링 공간(3곳)과 생성 공간은 모두 B의 `POST /internal/venues`로 넣습니다. 처음 표본 후보도 같은 API를 반복 호출합니다. 길을 하나로 두어야 upsert 규칙·검증·그림 배정이 한 곳에 있습니다.

- 같은 공간을 두 번 넣지 않음: `venues (source_site, source_id)` UNIQUE
- 이미지: 사진은 받지 않고 일러스트 값 `art:<종류>-<색>`(예: `art:group-0`)을 `venue_images.url`에 넣음. 프론트 `RoomArt.vue`가 이 값을 풀어 그림을 그림
- 주소는 시·도, 시·군·구까지만

## 가상 데이터

- 모든 행에 `is_synthetic = true`, 이벤트에는 `server = "generator"`
- 예약은 `reservation_slots` 기본키를 거쳐 넣어, 가상 데이터에도 중복 예약이 생기지 않게 합니다.
- 과거 예약은 처음부터 `completed`(또는 `cancelled`)로 넣어도 됩니다.
