# screens — 시연 화면 캡처

README '수행결과'에 넣는 화면입니다. 프론트 목업 데이터로 돌린 화면이라 실제 API·DB 연결 결과가 아닙니다.

| 파일 | 화면 | 크기 |
| --- | --- | --- |
| `main.png` | 메인(검색·유형 바로가기·NEW) | 1280×860 |
| `search.png` | 공간 찾기(필터·시간 칸) | 1280×860 |
| `venue.png` | 공간 상세(날짜·시간 칸·예약 카드) | 1280×860 |
| `venue_mobile.png` | 공간 상세(폰) | 390×844 |
| `login.png` | 로그인·회원가입 | 1280×860 |
| `reviews.png` | 후기 모아보기 | 1280×860 |

다시 찍는 법(`frontend/`에서 `npx vite` 실행 중):

```bash
npx playwright screenshot --channel chrome --viewport-size=1280,860 --wait-for-timeout=2500 http://localhost:5173/ ../docs/figures/screens/main.png
```
