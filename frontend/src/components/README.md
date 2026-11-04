# components — 화면 조각

| 폴더 | 무엇 | 예 |
| --- | --- | --- |
| `layout/` | 페이지 뼈대 | AppHeader(스티키 헤더·모바일 드로어 메뉴), AppFooter, SplitLayout(두 칸), SidebarLayout(사이드바 + 본문) |
| `ui/` | 서비스와 상관없는 공통 부품 | BaseButton(로딩), UiChip, UiTabs(밑줄 이동), UiAccordion, UiDialog, UiDrawer, UiSelect, UiMenu, UiTooltip, UiSkeleton, UiCarousel(스크롤 스냅), UiInput(라벨·오류·textarea), UiPagination, AppToaster |
| `domain/` | 공간 예약에만 있는 부품 | RoomArt, RoomCard, RoomCardSkeleton, CategoryBento, SlotStrip(메인 오늘 남은 칸), SlotGrid(1시간 칸 표, 이어진 칸 최대 4), DateStrip(과거·미래 365일, 14일씩 넘기는 날짜 띠), ReviewCard, SearchFilters(조회 필터), HourlyChart |

- 두 화면 이상에서 쓰는 것만 여기 둡니다. 한 화면에서만 쓰면 그 페이지 파일 안에 둡니다.
- `ui/`의 탭·다이얼로그 등은 reka-ui 위에 우리 토큰으로 모양을 입힌 래퍼입니다. 페이지에서 reka-ui를 직접 쓰지 않습니다.
- 다이얼로그·드로어·선택 상자·메뉴·툴팁은 `body`로 옮겨 그려지므로(포털) 스타일이 scoped가 아닙니다. 클래스 이름이 겹치지 않게 주의합니다.
- 모든 컴포넌트는 `/ui` 페이지에서 모양과 동작을 확인할 수 있습니다.

## 앞으로 필요할 수 있는 것

| 컴포넌트 | 쓰는 화면 |
| --- | --- |
| `ErrorBanner` | 백엔드가 붙은 뒤 목록·상세를 못 불러왔을 때 `{"code","message"}`를 문장 + 다시 시도 버튼으로 (지금은 토스트) |
