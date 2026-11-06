# AGENTS.md — frontend (Vue)

루트 `AGENTS.md`에 더해 이 폴더에서 지킨다.

> **11-03 확정안 반영 완료:** 화면·API 목업은 `/venues`, 한 번 결제, 과거 예약·후기 모아보기 기준이다. `docs/프론트_변경목록_11-03.md`의 규칙을 유지하고, 다음 작업은 실제 A·B API 연결 검증이다. 실제 서버는 아직 미구현이다.

- Vue 3 `<script setup>` + JavaScript, 스타일은 컴포넌트별 `<style scoped>`. TypeScript·Tailwind를 들이지 않는다.
- 색·글자 크기·간격·반경·움직임 시간은 `src/styles/tokens.css`의 변수만 쓴다. 컴포넌트에 새 hex를 쓰지 않는다.
- 글꼴은 `src/styles/fonts.css`의 `--font-sans` 한 곳에서만 바꾼다. 시간·가격 숫자에는 `.num`(tabular-nums)을 붙인다.
- 탭·아코디언·다이얼로그·드로어·선택 상자·메뉴·툴팁은 `src/components/ui/`의 래퍼를 쓴다(reka-ui 직접 사용 금지). 새로 필요하면 래퍼를 먼저 만든다.
- 어떤 패턴을 어디에 쓰는지는 `docs/공간대여_04_UI패턴_글꼴.md`를 따른다. 패럴랙스는 쓰지 않고, 스크롤 리빌·스태거는 문서에 적힌 곳에만.
- 움직임은 `transform`·`opacity`만, UI는 300ms 이하, `ease-in` 금지, 닫힘은 열림보다 빠르게, 호버 들림은 마우스에서만. `prefers-reduced-motion`이면 이동을 흐려짐으로 바꾼다. 자세한 값은 `docs/공간대여_04` 움직임 규칙, 검사는 `e2e/motion.spec.js`. 새 애니메이션도 이 규칙을 따른다.
- 백엔드 호출은 `src/api/`의 함수로만. 백엔드가 없으면 같은 이름의 목업(`src/api/mock/`)을 쓰고, 응답 모양은 `docs/백엔드_A_회원_후기_이벤트.md`·`docs/백엔드_B_공간_예약_결제_크롤링.md` 5절을 따른다.
- 활동 로그 이벤트 이름과 시점은 `src/composables/README.md` 표를 따른다. 백엔드 허용 목록(`docs/백엔드_A` 5-3)에 없는 이벤트는 서버가 버리니, 새 이벤트는 A와 먼저 맞춘다. 공간은 `payload`가 아니라 이벤트 맨 위 `venue_id`에 넣는다.
- UX 법칙(힉·피츠·제이콥·근접성·폰 레스토프)은 `docs/공간대여_04_UI패턴_글꼴.md` 'UX 법칙 5가지 적용'을 따른다: 보이는 영역마다 채운 버튼 하나, 선택지 7개 안팎(넘으면 '더 보기'), 누르는 것 44px·간격 8px 이상, 관련 요소는 붙이고 묶음 사이는 띄우기, 강조는 색만으로 하지 않기.
- 디자인 스킬: 점검·다듬기는 `impeccable`, 움직임 점검은 `design-motion-principles`. `hallmark`는 기존 화면에 쓰지 않는다. `design-taste-frontend`는 11-05 강사님 코멘트(AI 티 빼기)로 PM이 한 번 적용했다(올리브 on 뼈색, 알약 배지·그림자·빗금 없음). 11-06 PM 결정으로 C안(흰 바탕 + 검은 글자 + 주칠 `#a8441e` 한 색)을 적용했다. 공간 이미지는 `assets/art`의 유형별 일러스트를 기본·대체 이미지로 두고, `public/photos/`의 CCL 분위기 참고 사진은 공간 유형·ID로 안정 선택한다. 실제 공간 사진이 아님을 표시하고 공개 크레딧에 저작자·원본·라이선스·변경 사실을 유지한다. 이미지 API 계약은 그대로 둔다. 그 뒤로는 `tokens.css`가 기준이고, 화풍을 다시 바꿀 때만 PM 승인 후 쓴다.
- 접근성: 클릭되는 것은 `<button>`/`<a>`/`RouterLink`, 터치 영역 44px 이상(`--tap`), 아이콘만 있는 버튼에는 `aria-label`, 라벨이 보이는 입력.
- 코드를 고쳤으면 `npm run verify`(린트 + 단위 테스트 + 빌드)를 통과시킨다. 화면·흐름을 고쳤으면 `npm run test:e2e`도 돌린다(데스크톱 1280 · 폰 375 두 폭).
- 테스트를 통과시키려고 테스트나 린트 규칙을 약하게 고치지 않는다. 규칙을 끄거나 낮춰야 하면 `eslint.config.js`에 이유를 주석으로 남긴다.
- 테스트에서 요소는 화면에 보이는 이름으로 찾는다(`getByRole`, `getByLabel`). CSS 클래스로 찾지 않는다. 그래야 접근성이 깨지면 테스트도 깨진다.
- 도메인 규칙(칸 선택, 409, `min_hours` 등)을 바꾸면 `src/**/__tests__/`의 해당 테스트를 같이 고친다.

## 명령

```bash
npm run dev
```

```bash
npm run verify
```

```bash
npm run test:e2e
```

- `npm run lint`: oxlint → ESLint(Vue·접근성·테스트 규칙) → 색 코드 검사(`lint:colors`, `tokens.css` 밖 색 코드 금지). `npm run fix`: 자동으로 고칠 수 있는 것 고침
- `npm run test:unit`: Vitest 감시 모드(저장할 때마다 다시 돎)
- E2E를 처음 돌리는 PC는 브라우저를 한 번 받는다: `npx playwright install chromium`
