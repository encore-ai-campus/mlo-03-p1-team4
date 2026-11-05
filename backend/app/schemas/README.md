# schemas — 요청·응답 모델 (Pydantic)

routers와 같은 이름으로 파일을 나눕니다(`auth.py`, `venues.py` …). 담당도 routers와 같습니다.

## 이름 규칙

| 접미사 | 용도 | 예 |
| --- | --- | --- |
| `XxxCreate` | 생성 요청 본문 | `ReservationCreate {venue_id, date, start_hour, hours, headcount, method}` |
| `XxxUpdate` | 수정 요청 (모든 필드 선택) | `ReviewUpdate {rating?, content?}` |
| `XxxRead` | 단건 응답 | `VenueRead {venue_id, name, category, region, capacity_max, price_per_hour, min_hours, …}` |
| `XxxListItem` | 목록 한 줄 (가볍게) | `VenueListItem {venue_id, name, category, region, price_per_hour, image, rating_avg, slots}` |
| `Page[T]` | 목록 응답 | `{"items": [T], "page", "size", "total"}` (core에서 제공) |

- 필드 이름은 [백엔드_A·B 5절](../../../docs/백엔드_B_공간_예약_결제_크롤링.md)의 JSON 예시를 그대로 씁니다. 프론트가 이 이름을 씁니다.
- 날짜는 `date`, 칸은 `int`(9~22), 금액은 원 단위 `int`, 결제수단 응답은 `Literal["transfer", "card", "phone"]`. 예약 요청은 `INVALID_METHOD` 오류를 보존하도록 수단을 먼저 문자열로 받아 서비스에서 검증합니다.
- 응답에 `password_hash`, 다른 사람의 이메일·휴대폰은 절대 넣지 않습니다. 후기 작성자는 `김**`처럼 가린 이름만 넣습니다.
