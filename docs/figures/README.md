# docs/figures — 산출물 그림

설계 문서에 넣는 그림과 그 원본입니다. 그림을 고칠 때는 `src/`의 원본을 고치고 아래 명령으로 다시 만듭니다. PNG만 직접 고치지 않습니다.

| 그림 | 원본 | 쓰는 문서 |
| --- | --- | --- |
| `erd_mariadb.png` / `.svg` | `src/erd_mariadb.mmd` | `산출물_04_DB명세서.md` |
| `architecture.png` | `src/architecture.html` (아이콘 `../architecture/icons/`) | `산출물_02_시스템아키텍처_흐름도.md` |
| `service_screen_map.png` | `src/service_screen_map.mmd` | `산출물_03_서비스흐름도.md` |
| `service_user_journey.png` | `src/service_user_journey.mmd` | 같음 |
| `service_reservation.png` | `src/service_reservation.mmd` | 같음 |
| `service_review.png` | `src/service_review.mmd` | 같음 |
| `service_crawl_register.png` | `src/service_crawl_register.mmd` | 같음 |

## 다시 만들기

프론트에 설치된 Playwright(Chromium)를 씁니다. 처음이면 `frontend`에서 `npm install`과 `npx playwright install chromium`을 한 번 합니다. mermaid는 CDN(jsdelivr, 11.4.1)에서 받으므로 인터넷이 필요합니다.

저장소 루트(`Pro_1`)에서:

```bash
node docs/figures/tools/render_mermaid.cjs docs/figures docs/figures/src/erd_mariadb.mmd docs/figures/src/service_screen_map.mmd docs/figures/src/service_user_journey.mmd docs/figures/src/service_reservation.mmd docs/figures/src/service_review.mmd docs/figures/src/service_crawl_register.mmd
```

```bash
node docs/figures/tools/render_html.cjs docs/figures/src/architecture.html docs/figures/architecture.png 1800 1040
```

- 글꼴은 Noto Sans KR(설치돼 있지 않으면 맑은 고딕)로 그립니다.
- `render_html.cjs`는 깨진 아이콘이 있으면 파일 이름을 알려 줍니다.
- 그림 초안은 `pretty-mermaid` 스킬로도 그려 봤지만, 한글 대비와 배치 때문에 공식 mermaid 렌더를 최종으로 씁니다.
