# generator — 과거 행동 데이터 백필

기준은 [#75 PM 결정](https://github.com/encore-ai-campus/mlo-03-p1-team4/issues/75#issuecomment-6684120999)입니다. B가 본체·세션·예약을 구현하고, A가 회원·후기 서비스와 이벤트 빌더 사용을 확인하며, DB가 공간 보충·집계·정리·CSV를 담당합니다.

## 실행 조건

- api1의 **별도 Python 프로세스**에서 저장소 루트를 작업 폴더로 실행합니다. API 서버 프로세스 안에 import해 실행하지 않습니다.
- 기존 `pro_1` 환경만 사용합니다. 새 패키지·DDL·HTTP API 변경은 없습니다.
- `backend/.env` 또는 기존 환경변수의 `DB_WRITE_URL`, `MONGO_URL`, `MONGO_DB`를 사용합니다. 실제 비밀값은 실행 기록에 저장하지 않습니다.
- DB 담당이 크롤링 공간을 등록한 뒤 부족한 유형을 `/internal/venues`로 보충합니다. 실제 적재는 **유형별 최소 6개**가 있어야 시작합니다. 이미 목표 이상인 공간은 삭제하지 않습니다.
- MongoDB `events`에는 공식 `docs/db/mongo_init.js`의 strict/error validator, `uq_event_id`, `received_at` 기준 365일 TTL이 먼저 적용돼 있어야 합니다. 생성기는 스키마·인덱스를 만들지 않습니다.

## 명령

아래는 **구현된 명령**입니다. 기준일을 생략하면 실제 실행일 KST를 사용합니다. 미래 기준일은 거부합니다.

```powershell
# 읽기 전용 미리보기: 업무 데이터·실행 기록을 쓰지 않음
conda run -n pro_1 --no-capture-output python -m simulator.generator --seed 75 --base-date 2026-11-07 --dry-run

# api1에서 수동 파일럿 적재
conda run -n pro_1 --no-capture-output python -m simulator.generator --seed 75 --base-date 2026-11-07 --apply

# 중단 후 원래 기준일·설정·코드로 재개
conda run -n pro_1 --no-capture-output python -m simulator.generator --seed 75 --base-date 2026-11-07 --apply --resume
```

DB 연결 없이 계획만 확인하려면 `--dry-run --snapshot <공간 JSON 경로>`를 사용합니다. JSON은 `manifest.json`의 `venues` 배열과 같은 구조입니다. 이 옵션은 `--apply`와 함께 사용할 수 없습니다.

기본값은 `--users 100 --days 30 --sessions-per-day 42`입니다. 규모 변경은 새 실행에만 적용하며, 1,000명 확대는 PM이 파일럿 결과를 확인한 뒤 결정합니다. `--output-root`로 실행 기록 위치를 바꿀 수 있습니다(기본: 저장소 루트 `logs/`).

## 생성 규칙

- 기간: `[기준일-30일, 기준일-1일]`, 하루 42세션·총 1,260세션. 공간 점유가 늘어도 방문량을 줄이지 않습니다.
- 회원 비율: Student 35%, Worker 25%, Gathering 20%, Explorer 20%. 기본 세션 수에도 같은 비율을 적용하며 회원을 유형 안에서 순환 배정합니다.
- Student는 평일 오후 스터디룸, Worker는 평일 19시 이후·주말 오전, Gathering은 주말 오후 파티룸·카페·강의실을 선택합니다. Explorer는 예약하지 않습니다.
- 영업시간·최소 이용시간·인원에 맞는 후보를 고르고, 실제 점유 충돌은 B 예약 서비스와 DB 기본키가 판정합니다. 충돌 후 다른 후보 재시도는 최대 한 번입니다. 같은 요청의 200 재응답은 신규 성공으로 세지 않습니다.
- 성공 예약 열 건마다 한 건을 이용 시작 전에 취소합니다(`floor(성공 수 × 0.10)`).
- 취소되지 않은 예약은 이번 실행 소유의 예약만 이용 종료 시각에 완료 처리합니다. 다른 회원의 예약은 갱신하지 않습니다.
- 완료 예약의 `floor(완료 수 × 0.25)`에 후기를 만듭니다. 같은 회원에게 이미 배정된 이용 종료 뒤·7일 기한 안의 세션에 연결해 세션 총량을 유지합니다. 가능한 후속 세션이 목표보다 부족하면 실행을 중단하고 기록을 보존합니다.
- 별점 수량은 5점 40%·4점 30%·3점 15%·2점 10%·1점 5%를 최대 나머지 방식으로 정수 배분합니다. 회원·세션 비율의 소수 수량도 같은 방식을 씁니다.
- 후기 문구는 유형별 고정 템플릿입니다. 실제 업체 정보나 개인정보를 포함하지 않습니다.

## 서비스·시각·관측 경계

회원 생성은 실제 구현 함수인 A `auth_service.signup`을 호출합니다(PM 댓글의 `user_service` 역할에 해당). 예약·결제·취소는 B `reservation_service`, 후기는 A `review_service`를 사용합니다. 서비스가 트랜잭션을 커밋합니다. 생성기에서 회원·예약·결제·후기를 직접 INSERT하지 않습니다.

`HistoricalRuntime`은 생성기 프로세스에서 이미 import된 앱의 `get_now/get_today` 참조를 과거 시각으로 치환하고, B 예약 서비스의 운영 이벤트 호출과 Prometheus 카운터를 억제합니다. 종료·예외 시 원래 참조를 복원합니다. 별도 실행 중인 API 서버에는 영향을 주지 않습니다.

`get_event_time`은 실제 수신 시각을 유지합니다. 과거 행동 시각은 `build_document(occurred_at=...)`에 명시적으로 전달합니다. 따라서 MariaDB `created_at/paid_at/refunded_at`과 이벤트 `occurred_at`은 과거, `received_at`은 실제 적재 시각입니다.

서비스 결과가 확정된 뒤 공식 `build_document`로 문서를 만들고 `is_synthetic=true`, `server="generator"`로 저장합니다. `session_id`는 UUID이며 세션별 `session_sequence`는 1부터 연속입니다. 이벤트 ID는 실행 namespace와 세션·순서로 만든 UUID5입니다. 모든 업무 결과와 후기 배치가 확정된 다음 이벤트를 순서대로 적재합니다.

예약·회원의 가상 플래그는 서비스를 통해 저장합니다. 현재 DDL에 `reviews.is_synthetic` 컬럼은 없으므로 후기는 가상 회원·예약과의 관계로 구분합니다.

## 중단·재개

`logs/generator-<run_id>/`에 아래 파일을 남깁니다.

| 파일 | 내용 |
| --- | --- |
| `manifest.json` | seed·기준일·설정, 고정 공간 스냅샷, Git 커밋·앱/생성기 코드 해시, 비밀값 없는 대상 식별 해시 |
| `state.json` | 회원 번호·예약/후기 ID·작업별 결과. 원자적 교체와 fsync로 기록 |
| `report.json` | 완료 후 회원·세션·시도·성공·충돌·취소·완료·후기·별점·이벤트 수량 |

이메일·비밀번호·접속 URL을 기록 파일에 저장하지 않습니다. 가상 회원 이메일은 메모리에서 `gen-<seed>-<n>@example.invalid`로 구성하고 비밀번호는 A의 기존 bcrypt 경로로 처리합니다.

- 같은 seed는 MariaDB 연결 단위 `GET_LOCK`으로 동시 실행을 막습니다.
- 같은 실행의 설정·코드·대상·공간 스냅샷이 달라지면 재개를 거부합니다. 실행 중 배포 코드를 변경하지 않습니다.
- 예약은 회원·공간·이용 조건·정확한 생성 시각·결제를 대조합니다. 완료·취소 상태도 포함하므로 슬롯이 삭제된 취소 예약도 찾습니다.
- 커밋됐지만 `state.json`에 쓰기 전에 중단된 회원·예약·취소·후기는 DB 결과를 찾아 이어갑니다. 기록이 있는데 DB 결과가 없어졌다면 중단합니다.
- MongoDB는 `insert_many(ordered=False)`로 넣습니다. `uq_event_id` 중복의 기존 문서가 수신 시각 외에는 같을 때만 건너뜁니다. 다른 UNIQUE·validator·연결 오류는 중단합니다.
- 재개에 필요한 manifest와 state를 삭제하지 않습니다. 같은 seed를 다른 기준일에 새로 쓰면 기존 회원의 생성 시각과 충돌하므로 새 실험은 다른 seed를 사용합니다.

생성기는 데이터를 자동 삭제하지 않습니다. DB 담당 정리 스크립트는 먼저 `spacecube_test`에서 검증해야 하며, 현재 FK는 회원·예약 삭제만으로 결제·후기까지 모두 CASCADE하지 않습니다. 운영 데이터 정리는 기존 프로젝트 규칙에 따라 사람이 실행합니다.

## DB·FE 후속 연결

실행 후 `report.json`과 `manifest.json`을 DB 담당에게 전달합니다. 원본 운영 이벤트를 삭제하거나 API 전달 성공률에 생성기 데이터를 포함하지 않습니다. 가상 데이터 정리는 별도 작업이며 운영 DB에서 자동 실행하지 않습니다.

집계 키는 KST `occurred_at` 날짜, `event_type=event_name`, 공간별 문자열 `products[].product_id`(공간 없으면 null), `is_synthetic`입니다. CSV 컬럼은 #75 PM 댓글의 목록을 따릅니다. DB 산출물 이후 FE가 그래프를 확인합니다.

### 일별 집계와 CSV (DB 담당)

api1의 저장소 루트에서 별도 Python 프로세스로 실행합니다. `backend/.env`의 `MONGO_URL`·`MONGO_DB`를 읽으며, 동시 실행은 `logs/analytics/.event_daily.lock`으로 막습니다. 기간은 `[기준일-일수, 기준일)`의 KST 달력 날짜이며 기본값은 오늘 기준 직전 30일입니다.

```powershell
conda run -n pro_1 --no-capture-output python -m simulator.generator.analytics --base-date 2026-11-07 --days 30 --output-root logs/analytics
```

같은 기간을 다시 실행하면 `db/aggregate/event_daily.py`의 기존 집계기를 호출해 `event_daily`를 원천 `events`에서 재계산합니다. 집계기와 CSV 래퍼 모두 컬렉션·인덱스를 만들지 않습니다. 공식 `mongo_init.js`의 `event_daily` 복합 UNIQUE 인덱스가 없으면 쓰기 전에 중단합니다. 같은 기간의 중복 실행은 이 래퍼의 파일 잠금으로 막고, 실패 시 같은 명령을 재실행합니다.

109 api1의 100명·30일 파일럿과 `event_daily` 재집계는 11-07 이미 실행·기록됐습니다(`STATE.md` #19·#75 행). 위 명령은 해당 결과의 원천 이벤트 CSV가 필요할 때 사용합니다. 최종 배치의 일별 스케줄은 현재 109 api1에 등록된 집계 타이머와 중복되지 않도록 A가 실제 구성을 먼저 확인합니다.

실행 결과는 다음 두 CSV를 원자적으로 교체합니다.

- `events-<시작일>-<기준일>-synthetic.csv`: 가상 원천 이벤트. CSV 한 행은 이벤트와 각 `products[]` 상품 ID 조합이며 상품이 없는 이벤트도 한 행을 냅니다. 같은 이벤트에 상품이 여러 개면 `event_id`가 여러 행에 나타납니다.
- `events-<시작일>-<기준일>-event-daily.csv`: `date,event_type,venue_id,is_synthetic,count` 집계. 발표 그래프는 이벤트 건수로 표시합니다.

최종 api1의 일별 스케줄 등록은 A 담당입니다. 아래 형태는 후보 명령이며, 109 api1에는 `event_daily` :20 타이머가 이미 있다는 진행 기록을 확인하고 **동일 작업을 두 번 등록하지 않습니다**. A가 실제 서비스 계정, exit code, 로그 회전을 연결합니다.

```text
python -m simulator.generator.analytics --days 1 --output-root /var/lib/spacecube/analytics
```

세션 전환율·이탈률 CSV는 전환 이벤트·세션 판정 기준이 정해진 뒤 추가합니다.

### 부족한 공간 요청 만들기 (DB 담당)

검증된 원천 공간만 담은 JSON 스냅샷을 준비합니다. `venues` 배열의 각 행에는 `category_code`, `source_site`, `source_id`, `is_active`, `verified`, `sido`, `sigungu`, `capacity_max`, `price_per_hour`, `min_hours`, `open_hour`, `close_hour`, `facilities`가 필요합니다. `verified`는 DB 담당이 속성·요금 단위를 확인한 공간에만 `true`로 지정합니다. 전체 활성 공간도 포함해야 유형별 부족 수가 정확합니다. 업체명·원문·사진·주소 상세는 넣지 않습니다.

```powershell
conda run -n pro_1 --no-capture-output python -m simulator.generator.topup --snapshot vetted_venues.json --output logs/topup-requests.json --seed 75
```

출력의 `requests` 배열은 B의 `POST /internal/venues` 본문으로 검증됩니다. 기존 활성 공간이 6개 이상인 유형은 생성하지 않습니다. `source_id`는 시드·유형·번호에서 고정되며, 부분 등록 뒤 새 스냅샷으로 다시 생성할 때 이미 등록된 ID는 건너뜁니다. 결과를 검토한 뒤 api1의 내부 API로 등록합니다. 이 도구는 HTTP 요청이나 DB 쓰기를 하지 않습니다. `verified` 원천이 없는 유형은 임의 가격을 만들지 않고 중단합니다.

### 파일럿 결과 오프라인 점검 (DB 담당)

생성기 `report.json`과 위 두 CSV를 받으면 다음 명령으로 이벤트 고유 ID 수, 세션 수, 집계 수, 기간을 비교합니다. 종료 코드 0은 모든 파일 비교 통과, 1은 불일치입니다. 이 검사는 MariaDB 예약·결제 행 및 슬롯 중복을 조회하지 않으므로 파일럿 완료 판정 전에 DB 담당이 해당 수량을 별도 확인해야 합니다.

```powershell
conda run -n pro_1 --no-capture-output python -m simulator.generator.audit --report logs/generator-<run_id>/report.json --events-csv logs/analytics/events-2026-10-08-2026-11-07-synthetic.csv --daily-csv logs/analytics/events-2026-10-08-2026-11-07-event-daily.csv
```

### api1 일별 스케줄 인계 (A 담당)

api1에서 `timedatectl`로 OS 시간이 Asia/Seoul인지 확인합니다. 서비스 계정에 저장소 읽기, `backend/.env` 읽기, 분석 출력 폴더 쓰기 권한을 부여합니다. `pro_1`을 활성화해 `command -v python`으로 절대 경로를 기록한 뒤 `crontab -e`에서 다음 한 줄의 경로를 실제 값으로 바꿉니다. `.env` 비밀값은 crontab이나 로그에 적지 않습니다.

```cron
0 4 * * * cd /실제/저장소/경로 && /pro_1/python/절대경로 -m simulator.generator.analytics --days 1 --output-root /실제/분석/출력경로 >> /실제/로그/경로/event-daily.log 2>&1
```

등록 후 `crontab -l` 또는 기존 systemd timer 목록으로 중복 여부를 확인하고, 같은 서비스 계정에서 `--base-date YYYY-MM-DD --days 1`을 수동 실행해 종료 코드 0과 CSV 두 파일을 확인합니다. 같은 날짜 재실행 결과가 같아야 합니다. 실행 실패나 종료 코드가 0이 아니면 해당 날짜를 수동 재실행하고 로그를 확인합니다. 로그 파일 회전과 실행 감시는 A 운영 설정에서 연결합니다.

## 검증

```powershell
conda run -n pro_1 --no-capture-output python -m pytest simulator/generator/tests -q
```

[tests/README.md](tests/README.md)의 로컬 MariaDB 조건을 따릅니다. 테스트는 DB 트랜잭션을 롤백하며, api1 파일럿을 자동 실행하지 않습니다.
