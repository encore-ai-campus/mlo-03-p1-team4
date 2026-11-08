# 크롤러 — F-61 두 수집원

담당: DB. spacecloud_crawler.py의 요청·상세 파서를 재사용하고 shareit_crawler.py, preprocess.py, crawl_venues.py로 F-61 파이프라인을 구성한다. 크롤러는 api1에서 실행한다. 두 사이트의 속성만 참고해 시연용 공간을 만들며, 실제 업체 예약 상품으로 표시하지 않는다.

## 실행 전

- 프로젝트 conda 환경 pro_1을 사용하고 docs/db/mongo_init.js, db/migrations/0001_init.sql, seed를 먼저 적용한다.
- backend/.env의 DB_WRITE_URL, MONGO_URL, INTERNAL_API_KEY를 설정한다. 키와 주소의 실제 값은 저장소에 쓰지 않는다. API는 기본적으로 api1 로컬의 http://127.0.0.1:8000/internal/venues로 호출한다.
- 11-07 PM 결정에 따라 11-05 기준을 적용해 비영리 수업 시연에서 쉐어잇의 공간 속성만 참고한다. 이는 법률 자문이나 플랫폼의 명시적 라이선스가 아니다. 공식 약관 2026-07-08 시행본을 확인했으며, 실제 실행 직전에 시행일이 같은지 다시 확인하고 바뀌었으면 중단한다. 실행 때마다 각 사이트 robots.txt를 읽고 요청 간격 3초 이상·실행 상세 20건 이하·식별 가능한 User-Agent·로그인/검색/예약 경로 미접근을 지킨다. 쉐어잇 측에서 중단·삭제 요청이 있으면 즉시 수집을 멈추고 해당 출처 데이터를 식별해 삭제 범위를 담당자와 확인한다. 운영 DB 삭제는 프로젝트의 DB 보호 규칙에 따라 처리한다.
- 실행당 상세 페이지 합계 20건 이하. 처음 채우기는 bootstrap, 주간 비교는 baseline 이후 weekly를 쓴다. 시연용 공간의 부족분은 생성기 이슈 #19 범위다.

    conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues fetch --site spacecloud 53074
    conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues fetch --site shareit 1321
    conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues run --mode bootstrap --max-detail 20
    # 11-07 PM 승인 시험 (api1에서만 실행)
    conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues run --site shareit --mode bootstrap --max-detail 20
    conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues baseline
    conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues run --mode weekly --max-detail 20

- fetch: 파서 점검용 단건. 허용한 속성만 출력하며 저장하지 않는다. 파서 수정 후에는 스페이스클라우드 53074 한 건만 확인한다. 쉐어잇은 실제 실행 전 약관·robots 확인이 먼저다.
- bootstrap: 현재 사이트맵에서 아직 처리하지 않은 ID를 살펴 초기 후보를 쌓는다. 여러 번 실행해도 출처와 ID로 중복을 피하며 매번 상세 상한 20건을 지킨다. #10의 11-07 PM 결정에 따른 쉐어잇 `ok` 후보 시험은 api1에서 위 명령으로 실행한다. 현재 두 경로 모두 예전 200건 표본 파일이 없어 자동 재사용은 불가능하다.
- baseline: 두 사이트의 현재 사이트맵 ID를 data/sitemap_ids.json에 보관한다. 기존 목록 형식도 읽지만 저장할 때는 사이트별 형식으로 바꾼다. 등록은 하지 않는다.
- weekly: baseline 당시의 전체 ID와 이후 처리 완료 ID를 새 사이트맵과 비교한다. weekly 실행 중 실패·미처리 ID는 다음 실행에 남는다. crawl_raw의 미등록 ok 후보도 재시도하고 유형별 최대 1개씩 등록한다. 적합한 후보가 없으면 0건도 정상이다.
- run: MongoDB crawl.crawl_raw에 이름·사진·후기·연락처·상세 주소·HTML을 뺀 추출값과 제외 이유를 남긴다. 전처리한 공간은 B의 POST /internal/venues로만 등록하고 응답 venue_id를 기록한다. MariaDB crawl_jobs에는 출처별 조회·등록 건수와 실행 상태를 남긴다. API 등록 뒤 Mongo 기록이 실패해도 같은 출처로 재전송하면 기존 공간을 갱신한다.
- 실행 결과의 `jobs.<site>.fetched`와 `registered`는 각각 상세 조회·공간 등록 건수다. 전체 시연 공간 수는 등록 뒤 공개 `GET /venues?page=1&size=1`의 `total`을 따로 확인한다. 읽기 복제 지연이 있으면 값이 반영될 때 다시 조회한다.

## 통합 실행기 연동 (#100)

B 실행기는 CLI 프로세스를 파싱하지 않고 아래 Python 진입점을 직접 호출할 수 있다. 설정·MariaDB·MongoDB 연결과 HTTP 클라이언트 수명은 크롤러가 관리한다.

```python
from crawler.crawl_venues import CrawlerRunError, run_configured

try:
    result = run_configured(mode="weekly", max_detail=20, max_register=5)
except CrawlerRunError as error:
    result = error.result  # 실패 시에도 확인된 부분 결과와 실패 정보를 받는다.
```

초기 등록을 반복하는 회차에서는 `mode="bootstrap", max_detail=20, max_register=20`을 전달한다. `weekly`는 baseline 이후 새 ID 비교에 쓰며 등록 상한이 5건이다. B 통합 실행기는 모드에 맞는 등록 상한을 전달하고, 어떤 모드에서도 상세 조회 20건 제한을 지킨다.

`result`는 성공과 실패에 같은 키를 사용한다. 기존 `jobs`와 `registered_by_category`는 유지한다.

- `ok`: 실행 성공 여부
- `job_ids`: 출처별 MariaDB `crawl_jobs.job_id`
- `jobs.<site>`: `new_ids`, `fetched`, `registered` 실행 건수
- `registered_by_category`: HTTP 200/201 후 MongoDB 상태 기록까지 끝난 유형별 건수
- `newly_registered_by_category`: **HTTP 201만** 세는 유형별 신규 등록 수. 다섯 유형을 모두 포함하고 0도 반환한다. HTTP 200 갱신은 포함하지 않는다.
- `confirmed_registrations`: API가 확인 응답한 출처 ID·유형·상태 코드·공간 ID. HTTP 201 응답은 본문 해석이나 MongoDB 기록이 뒤이어 실패해도 남으며, 이 경우 `venue_id`는 `null`일 수 있다.
- `uncertain_registrations`: 요청 무응답 또는 API 5xx로 등록 여부를 단정할 수 없는 출처. 이런 건을 신규 0건으로 간주해 보충하지 않도록 표시한다.
- `failure`: `stage`, `kind`(`external`/`internal`), `error_type`, 고정된 안전 요약과 선택적 출처 ID. 응답 본문·URL·예외 원문은 넣지 않는다. 초기화 실패도 `runtime_init` 단계의 같은 형식이다.

실패한 경우 CLI는 이 결과 JSON을 출력하고 종료 코드 1을 반환한다. B 실행기는 #99의 유형별 회차 목표 6개에서 `newly_registered_by_category`만 빼서 부족분을 계산하고, 재개 때는 이전 회차 입력을 이어 쓴다. `failure.kind == "external"`이고 `uncertain_registrations`가 비어 있을 때는 확인된 신규 건수로 보충할 수 있다. 내부 실패나 불확실 등록이 있으면 보충을 진행하지 않는다. 부족분 계산·생성·재개는 B 담당이며, 이 DB 진입점은 크롤러 결과만 전달한다. venue API 요청 필드와 반환 형식은 바꾸지 않는다.

#96의 `topup.py`는 #19 백필을 위한 활성 공간 수 기준 등록 요청 JSON 준비 도구다. #99/#100의 운영 보충은 B가 #103과 통합하는 보충기를 사용한다. 두 도구의 synthetic `source_id` 체계와 부족분 계산 기준이 다르므로 같은 운영 회차에 함께 적용하지 않는다.

유형은 db/seed/category_map.csv 한 곳에서 대응시킨다. 지역은 `addressRegion`+`addressLocality`를 `db/seed/legal_dong.csv` 또는 기존 별칭표와 `db/seed/regions.csv`로 매핑하고, 모호·누락 이유를 구분해 기록한다. 쉐어잇의 ruleType 1·2 단위가 확정되지 않았으므로 명시적으로 timeUnitMinute=60인 요금만 시간당 가격 후보로 쓴다. API 요청의 이름·소개·안내는 생성 문구이고, 공간당 art: 이미지 코드 3개를 보낸다.

sample_categories.py는 새 표본을 꼭 확인해야 할 때만 사용하며 상세 20건 상한을 강제한다. analyze_sample.py는 기존 표본의 분포를 읽는 도구다. data/의 기존 결과 파일은 삭제하지 않는다.

## 검증

    conda run -n pro_1 --no-capture-output python -m pytest db/tests/test_crawler.py -q
    powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1

서버 연동은 로컬 테스트 MariaDB spacecube_test와 MongoDB 테스트 구성에서 확인한다. 실제 출처로 등록한 공간은 시연용이며 공간 이름·소개는 생성한다.
