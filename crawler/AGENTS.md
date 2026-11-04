# AGENTS.md — crawler

외부 사이트에 요청을 보내는 유일한 폴더다. 아래 규칙은 사람이 바꾸라고 하기 전까지 고치지 않는다.

- 대상은 **3곳**(11-03 A3): ① 스페이스클라우드 `/space/<id>`·`sitemap.xml`(지금 코드) ② 쉐어잇 `/venue/<id>`·`sitemap.xml` ③ 루북 `/ko/space/…`·`/sitemap/index.xml`. ②③은 **이용약관 확인과 상세 20건 표본 승인이 끝나기 전에는 요청하지 않는다.** 루북의 `/api`·`/graphql`은 robots.txt가 막으므로 쓰지 않는다. 이 밖의 사이트를 추가하려면 먼저 사람에게 묻는다.
- 사이트마다 robots.txt를 실행할 때마다 다시 읽고 따른다(2026-11-03 확인: 스페이스클라우드 `*`는 `/search*`·`/reserve/`·`/my/`·`/space/zzim`·`/auth/login` 차단, 쉐어잇 `*`는 `/partneruniv`·`/examsuper`·`/corp`·`/spacelog/template`·`/spacelog/img` 차단, 루북 `*`는 `/api`·`/graphql`·관리·회원 경로 차단).
- `PoliteClient`를 거치지 않는 요청을 만들지 않는다. robots.txt 확인과 요청 간격 3초(`REQUEST_DELAY_SEC`)를 줄이지 않는다.
- 실행당 상세 페이지 20건(`MAX_DETAIL_PER_RUN`)을 넘기는 실행은 사람 승인 후에만. 전체 14,137개를 도는 실행은 하지 않는다.
- 저장하지 않는 것: 사진(이미지 파일·URL), 후기 본문, 전화번호, 상세 주소(시·구까지만), 원본 HTML.
- 파서를 고쳤으면 `fetch 53074`로 한 건만 확인한다. 테스트하려고 `diff`나 표본 수집을 반복해서 돌리지 않는다.
- `data/`의 결과 파일은 지우지 않는다(기준선·표본 기록).

```bash
conda run -n pro_1 --no-capture-output python spacecloud_crawler.py fetch 53074
```

## 11-03 확정 흐름 (코드는 아직 이전 방식)

```
sitemap diff → 상세 조회(실행당 20건 이하) → MongoDB crawl_raw(추출값, 이름 없음) → 전처리(유형·지역·가격, 생성 이름·소개)
  → POST /internal/venues (X-Internal-Key) → 응답 venue_id를 crawl_raw에 기록, 실행 기록은 MariaDB crawl_jobs
```

- 기준: `docs/산출물_02_시스템아키텍처_흐름도.md` 4-2, `docs/산출물_04_DB명세서.md` 8절 `crawl_raw`, `docs/백엔드_B_공간_예약_결제_크롤링.md` 7절(요청 JSON).
- 필터(`is_target`)를 유형 5개(스터디룸·스튜디오·카페·강의실·파티룸, `db/seed/README.md` 대응표, 연습실 계열 제외)로 바꾸고, 지역은 `sido_alias.csv`·`sigungu_alias.csv`로 맞추고(세종은 둘째 칸과 상관없이 `세종시`, 나뉜 옛 구는 `exclude_reason`에 남기고 제외 — 규칙은 `db/loaders/load_seed.py`의 `resolve()`와 같게), 업체 이름(`name`)은 저장·전송하지 않는다. 지금 코드의 스터디룸·서울·10명 필터와 룸 번호 방식은 지난 설계다.
- `/internal/venues`가 생기기 전에는 `data/`에 jsonl로만 쓴다. MongoDB·API 주소와 키는 `.env`에서 읽는다(파일에 쓰지 않는다).
