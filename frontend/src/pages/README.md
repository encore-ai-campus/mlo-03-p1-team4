# pages — 화면 7개

11-03 확정안의 목업과 실제 API 호출 경로를 적용했다. 기존 Vue 화면과 스타일을 유지한다.

| 파일 | 경로 | 역할 |
| --- | --- | --- |
| MainPage.vue | / | 유형·지역 검색, 시간 칸, NEW, 공간 목록·후기 |
| SearchPage.vue | /search | 필터·날짜 ±365일·시간 선택, 모바일 필터 드로어 |
| RoomPage.vue | /venues/:venueId | 상세·시설·후기·날짜 14일 넘김·최소 이용시간 |
| ReservePage.vue | /reserve?venue=&date=&start=&hours=&people= | 선택값 확인 → 결제 POST 한 번 → 완료. 409 재선택·내 예약 안내 |
| AuthPage.vue | /login | 로그인·회원가입·필수 동의·14세 검증, 선택값 유지 |
| MyPage.vue | /me | 이용 예정·완료·취소, 후기 작성·내 후기·회원 정보·탈퇴 |
| BoardPage.vue | /reviews | 후기 모아보기만. 유형·정렬·페이지 |

- 이전 `/rooms/:roomId`는 `/venues/:venueId`, `/board`는 `/reviews`로 이동한다. 옛 예약 id 결제 주소는 내 예약으로 보낸다.
- 지난 시간의 결제는 completed. `바로 후기 쓰기`는 `/me?tab=completed&review=<예약번호>`로 연결된다.
- `/me?section=reviews`는 내 후기, `section=account`는 내 정보·탈퇴다. 회원정보 수정·비밀번호 변경 UI는 아직 없다.
- 시연 로그인: study@example.com + 8자 이상 비밀번호. 목업만 쓰는 예시 계정이다.
- 예약·회원·토큰 목업은 메모리에서만 유지된다. 새로고침은 초기 상태로 돌아간다.
- `/ui`는 공통 컴포넌트 모음, 없는 경로는 PlaceholderPage다.
