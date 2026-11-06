# src — 프론트 소스 (Vue)

| 위치 | 내용 |
| --- | --- |
| `main.js`, `App.vue` | 앱 시작, 전역 스타일, 헤더·푸터·토스트, 본문 건너뛰기 링크 |
| `router/` | 라우트 7개 + `/ui` |
| `pages/` | 화면, 라우트 하나에 파일 하나 |
| `components/` | layout · ui · domain 부품 |
| `composables/` | 로그인 상태, 예약 신청 흐름(useBooking), 활동 로그, 스크롤 리빌 |
| `stores/` | Pinia 저장소 (auth) |
| `api/` | 백엔드 호출 함수와 목업 (페이지에서 경로를 직접 쓰지 않음) |
| `utils/` | 날짜·시간 범위·금액 표시 (`date.js`) |
| `styles/` | 토큰·글꼴·기본 스타일 |
| `assets/` | 정적 파일 자리 (공간 유형 일러스트는 `RoomArt.vue`가 대체 이미지로 표시) |
| `test/` | Vitest 공통 준비(`setup.js`) |
| `**/__tests__/` | 단위·컴포넌트 테스트. 테스트 대상 파일 옆 폴더에 둠 |

E2E 테스트는 `src` 밖 `frontend/e2e/`에 있습니다.
