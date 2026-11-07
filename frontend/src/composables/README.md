# composables — 로그인·예약 이동·이벤트·움직임

| 파일 | 역할 |
| --- | --- |
| useAuth.js | Pinia 로그인 상태, 로그인 필요 시 next 주소 유지 |
| useBooking.js | 날짜·연속 칸·인원을 확인하고 선택값만 결제 주소로 이동. 예약 쓰기 없음 |
| useEventLogger.js | 이벤트를 최대 20건 또는 10초 간격으로 전송, pagehide에는 keepalive |
| useReveal.js | 첫 등장, 움직임 줄이기 설정 반영 |

프론트 이벤트는 11-06 채택 구조(`docs/db/events_event_daily_컬렉션_속성정리_v1.md`, 대응표 PR #58 코멘트)의 12개만 보낸다: `page_view`·`product_impression`·`product_view`·`product_section_click`·`search_submit`·`availability_view`·`rental_slot_select`·`reservation_start`·`reservation_cancel_attempt`·`review_create`·`login`·`signup`. 예약 완료·충돌·취소 완료는 서버(B)가 보낸다. 화면이 12개를 모두 보낸다(11-07): `page_view`는 경로가 바뀔 때(router afterEach), `product_impression`은 공간 카드가 절반 이상 보일 때 카드마다 한 번, `product_section_click`은 상세의 소개·시설·이용 안내·후기 이동 링크를 누를 때. `reserve_ok`, `reserve_conflict`, `reserve_cancel_ok`는 서버 이벤트다.

공간은 `products[].product_id`(문자열), 나머지는 허용된 `properties` 필드만 쓴다. 주소는 쿼리를 빼고 보낸다. 이름·이메일·휴대폰·비밀번호·검색 자유문은 보내지 않는다. `client.getSessionId()`의 같은 UUID를 모든 API의 X-Session-Id와 이벤트 본문에 사용한다. 실패한 이벤트 전송은 예약 화면·로그인 상태를 바꾸지 않는다.
