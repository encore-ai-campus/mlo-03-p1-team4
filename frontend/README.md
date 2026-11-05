# frontend — 화면 (담당: 프론트엔드)

**11-03 확정안 반영:** 공간 `/venues`, 홀딩 없는 결제 한 번, 과거 예약, 후기 모아보기, 가입 동의·나이 검증을 적용했습니다. 백엔드는 아직 연결 전이며 목업으로 실행합니다. 상세 작업 기록은 [docs/기록/작업_2026-11-03_프론트_FE반영.md](../docs/기록/작업_2026-11-03_프론트_FE반영.md).

Vue 3 + Vite 화면 7개, 기존 Noto Sans KR·CSS 토큰·reka UI 래퍼를 유지했습니다.

## 실행

```bash
npm install
```

```bash
npm run dev
```

- 주소: http://localhost:5173 (컴포넌트 모음은 `/ui`)
- 빌드: `npm run build` → `dist/` (배포 때 Nginx가 이 폴더를 내보냄)
- 백엔드 연결: `.env.example`을 `.env`로 복사하고 `VITE_USE_MOCK=false`. 개발 서버는 `/api` 요청을 `http://localhost:8000`으로 넘깁니다(`vite.config.js`).

## 스택

| 쓰임 | 패키지 |
| --- | --- |
| 화면 | Vue 3.5 (`<script setup>`, JavaScript), Vue Router 5, Pinia 4 |
| 접근성 있는 컴포넌트 바탕 | reka-ui 2 (탭·아코디언·다이얼로그·드로어·선택 상자·메뉴·툴팁) |
| 토스트 | vue-sonner |
| 스크롤·움직임 줄이기 감지 | @vueuse/core |
| 아이콘 | @lucide/vue |

캐러셀은 라이브러리 없이 CSS 스크롤 스냅, 애니메이션은 CSS 전환만 씁니다(GSAP 없음).

## 구성

| 폴더 | 내용 |
| --- | --- |
| `src/pages/` | 라우트별 화면 7개 + `PlaceholderPage.vue`(없는 주소), `UiShowcasePage.vue`(/ui) |
| `src/components/layout/` | AppHeader(스티키), AppFooter, SplitLayout, SidebarLayout |
| `src/components/ui/` | BaseButton, UiChip, UiTabs, UiAccordion, UiDialog, UiDrawer, UiSelect, UiMenu, UiTooltip, UiSkeleton, UiCarousel, UiInput, UiPagination, AppToaster |
| `src/components/domain/` | RoomArt(공간 일러스트 9종), RoomCard(+Skeleton), CategoryBento, SlotStrip, SlotGrid, DateStrip, ReviewCard, SearchFilters, HourlyChart |
| `src/composables/` | useAuth, useBooking(예약 신청 흐름), useReveal(스크롤 리빌), useEventLogger(활동 로그) |
| `src/api/` | client(오류 형식·목업 지연), catalog·venues·reservations(B), auth·users·reviews(A), mock/ |
| `src/utils/` | date.js: 날짜(YYYY-MM-DD)·시간 범위·금액 표시 |
| `src/stores/` | Pinia: auth (목업 로그인) |
| `src/styles/` | tokens.css(색·크기·간격·움직임), fonts.css(글꼴 5종, `--font-sans`), base.css |
| `public/fonts/` | 웹용 글꼴 서브셋, Noto Sans KR만 (`design/fonts/make_webfonts.py`로 생성. 비교용 후보는 `design/fonts/web/`) |

어떤 패턴을 어느 화면에 쓰는지는 [UI 패턴 문서](../docs/공간대여_04_UI패턴_글꼴.md)를 따릅니다.

## 검증 (린트 · 테스트)

Vue 공식 스캐폴드(`create-vue`)의 구성을 그대로 따릅니다. 커밋 전에 `npm run verify`, 화면 흐름을 바꿨으면 `npm run test:e2e`.

| 단계 | 도구 | 무엇을 보나 | 명령 |
| --- | --- | --- | --- |
| 린트 1차 | Oxlint | 확실한 버그(쓰지 않는 식, GET에 body 등). 아주 빠름 | `npm run lint` |
| 린트 2차 | ESLint 10 (flat config) + eslint-plugin-vue + eslint-plugin-vuejs-accessibility | Vue 템플릿 실수(v-for key, props 직접 변경), 접근성(라벨 없는 입력, 키보드로 못 누르는 클릭 등 20개 규칙), 테스트 파일 규칙 | (위와 같이) |
| 단위·컴포넌트 | Vitest + Vue Test Utils | 계약 목업·날짜·칸·오류·인증·후기 | `npm run test:unit` |
| 화면 흐름 (E2E) | Playwright | 가입·로그인·결제·409 재선택·지난 예약·후기·취소·탈퇴·반응형·움직임. 데스크톱 1280, 폰 375 | `npm run test:e2e` |
| 자동 접근성 | @axe-core/playwright | 화면 5개와 폼·오류·다이얼로그 상태의 WCAG 2 A·AA 심각·치명 검사 | E2E 포함 |
| 빌드 | Vite | 번들이 만들어지는지 | `npm run build` |

| 파일 | 내용 |
| --- | --- |
| `.oxlintrc.json`, `eslint.config.js` | 린트 설정 (oxlint가 본 규칙은 ESLint에서 끔) |
| `vitest.config.js`, `src/test/setup.js` | 단위 테스트 설정. 목업 지연(`mockDelay`)은 테스트에서 0초 |
| `src/**/__tests__/*.spec.js` | 단위·컴포넌트 테스트 (date, slots, SlotGrid, reservationsApi, availability, authApi, auth 스토어) |
| `playwright.config.js`, `e2e/*.spec.js` | E2E (booking · pages · a11y · review-fixes · motion). 개발 서버를 알아서 띄우고(이미 떠 있으면 재사용) 목업 데이터로 돈다. 시계는 `e2e/helpers.js`의 `fixClock` |

- 처음 E2E를 돌리는 PC는 `npx playwright install chromium`을 한 번 합니다.
- 결과 보고서: `playwright-report/index.html` (git에 올리지 않음)
- 실제 서버로 돌리기(VM 배포 뒤): `E2E_BASE_URL=http://gw`이면 개발 서버를 띄우지 않고 그 주소로 갑니다. `E2E_SYNTHETIC_KEY`(= 서버 `.env`의 `SYNTHETIC_API_KEY`, 저장소에 넣지 않음)를 주면 모든 요청에 `X-Synthetic: 1`·`X-Synthetic-Key`가 붙어 가상 데이터로 저장됩니다. 지금 시나리오는 목업 시연 계정·고정 시계를 전제로 하므로, 실제 서버용 시나리오는 #9에서 따로 맞춥니다.
- 아직 없는 것: 시각 회귀(스크린샷 비교), 커버리지 기준, CI(git 저장소가 생기면 GitHub Actions에서 루트 `verify.ps1 -E2E`와 같은 순서로)
- 저장소 전체(파이썬 포함)를 한 번에 볼 때는 루트의 `verify.ps1` ([AGENTS.md](../AGENTS.md) 검증)

## 백엔드와의 약속

- 모든 요청은 `src/api/`의 함수로. 로그인 후 `Authorization: Bearer <토큰>`
- 오류 응답 `{"code","message","detail"}` → `ApiError`. 예약 신청이 `409 SLOT_TAKEN`이면 시간표를 다시 불러오고 토스트로 알림
- 목록 응답 `{"items","page","size","total"}`
- 활동 로그는 `useEventLogger`가 모아서 `POST /events`로 보냄(목업에서는 외부로 보내지 않음)

기준 문서: [요구사항명세서](../docs/산출물_01_요구사항명세서.md), [백엔드 A](../docs/백엔드_A_회원_후기_이벤트.md)·[B](../docs/백엔드_B_공간_예약_결제_크롤링.md) API, [프론트 변경 목록](../docs/프론트_변경목록_11-03.md)

## 이번 PC의 브라우저 검증

번들 Chromium이 없는 경우 설치된 Chrome을 사용할 수 있습니다(새 패키지 추가 없음).

```powershell
$env:PLAYWRIGHT_CHANNEL='chrome'
npm run test:e2e -- --workers=2
```

기본은 기존 Playwright Chromium입니다. 새로고침하면 목업 데이터·목업 토큰이 초기화되어 다시 로그인합니다. 실제 API·DB·배포 검증은 별도로 남아 있습니다.
