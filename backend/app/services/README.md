# services — 업무 규칙과 트랜잭션

| 파일 (예정) | 담당 | 핵심 규칙 |
| --- | --- | --- |
| `auth_service.py` | A | 이메일 중복(탈퇴 회원 포함), bcrypt, 토큰 발급. birth 6자리 실제 날짜, gender_digit 1~4 |
| `user_service.py` | A | 탈퇴 = `deleted_at` 기록(예약·후기는 보존) |
| `review_service.py` | A | 자격 4단계: 내 예약(`get_owned`) → `completed` → 기한 안(`max(이용일, 예약한 날)`부터 7일) → 아직 안 씀 |
| `venue_service.py` | B | 검색 조건 → 공간 + 그날 칸(`slots`는 한 번에 읽어 붙임), 예약 가능 날짜(이어진 빈 칸 ≥ `min_hours`) |
| `reservation_service.py` | B | F-30~32 예약+모의 결제, F-34 취소·칸 반납·전액 환불 한 트랜잭션, F-35 종료 예약 일괄 완료, F-40 내 예약 목록·상세 조회 |
| `internal_service.py` | B | F-61 크롤러·생성 공간 등록/갱신: 신규 201·같은 출처 재전송/갱신 200, 최상위 ID·무시한 시설, 공간·시설·그림 한 트랜잭션, 모르는 지역·유형은 400 |

F-40의 `_as_owned_read`는 `review_id`를 명시적으로 전달받아 null 또는 후기 ID를 그대로 응답합니다. 목록은 소유권 확인과 페이지 조회 뒤 현재 페이지 ID만 A `get_review_ids`에 한 번 전달하고, 상세는 본인 예약 확인 뒤 해당 ID를 전달합니다. 삭제된 후기 ID도 유지하며 빈 목록은 A 함수가 SQL 없이 처리합니다.

## 예약 + 모의 결제 트랜잭션 (B, primary)

```
1. 검증: 오늘−BOOKING_PAST_DAYS ≤ date ≤ 오늘+BOOKING_FUTURE_DAYS(지난 시간도 허용), min_hours ≤ hours ≤ 4, 영업시간 안,
         1 ≤ headcount ≤ capacity_max, is_active, method ∈ {transfer, card, phone}
2. BEGIN
3. reservations INSERT (끝나는 시각이 지났으면 status = completed, 아니면 confirmed / total_price = price_per_hour × hours)
4. reservation_slots INSERT × hours   ← 중복 키(1062)면 IntegrityError
5. payments INSERT (status = paid, paid_at = NOW())
6. COMMIT → 201, log_event(reservation_complete, products=...), reservation_total{result="ok"} +1
   슬롯 1062 → ROLLBACK → primary에서 재시도 예약·겹친 칸 확인
      같은 요청 10분 안: 200 + 기존 예약(추가 이벤트·카운터 없음)
      모두 본인 예약과 충돌: 409 + mine, reservation_id는 겹친 예약 ID 최솟값
      그 밖의 충돌: 409 + 슬롯 목록, reservation_conflict 이벤트·충돌 카운터 +1
```

- 결제 화면에 들어올 때는 아무것도 잡지 않습니다. 먼저 커밋한 요청이 이깁니다.
- 3 전에 '빈 칸인지 SELECT'로 막지 않습니다(두 서버가 동시에 '비었음'을 볼 수 있음).
- 취소: `SELECT … FOR UPDATE` → 시작 전인지 → status = cancelled, 칸 DELETE, payments = refunded(전액) → COMMIT.
- 자세한 순서: [백엔드_B 6절](../../../docs/백엔드_B_공간_예약_결제_크롤링.md)

F-60(#60·#72): 서버 결과 3종은 primary에서 읽은 공간명과 확정된 예약 조건으로 `products`를 전달합니다. 상품 스냅샷은 `_log_reservation_event` 안에서 지연 생성해, 조립이나 기록 실패가 이미 커밋된 예약·취소·충돌 결과를 바꾸지 않게 합니다. 충돌에는 검증한 시도 조건과 `reason=SLOT_TAKEN`을 기록합니다. 취소는 비활성 공간도 처리하고 시간당 요금은 저장된 총액/이용시간으로 복원합니다. 공간명은 이벤트 시점 DB 값이며 과거 이름을 새로 저장하지 않습니다. 선택적 `event_context`는 기록할 때만 A `ClientEventContext`에 설정하고 `finally`에서 복원합니다. A PR #72의 새 함수·문맥 계약이 필요하므로 두 변경을 함께 검증·배포해야 합니다.
