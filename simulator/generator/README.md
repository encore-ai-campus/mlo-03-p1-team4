# generator — 행동 데이터 백필·공간 보충

과거 행동 데이터 생성 기준은 [#75 PM 결정](https://github.com/encore-ai-campus/mlo-03-p1-team4/issues/75#issuecomment-6684120999), 공간 보충 기준은 [#99](https://github.com/encore-ai-campus/mlo-03-p1-team4/issues/99)입니다. B가 예약 흐름과 공간 보충기를 구현하고, A가 회원·후기 서비스와 이벤트 빌더 사용을 확인하며, DB가 기초 프로필 검수·집계·정리·CSV를 담당합니다.

## 실행 조건

- api1의 **별도 Python 프로세스**에서 저장소 루트를 작업 폴더로 실행합니다. API 서버 프로세스 안에 import해 실행하지 않습니다.
- 기존 `pro_1` 환경만 사용합니다. 새 패키지·DDL·HTTP API 변경은 없습니다.
- 과거 행동 백필은 `backend/.env` 또는 기존 환경변수의 `DB_WRITE_URL`, `MONGO_URL`, `MONGO_DB`를 사용합니다. 공간 보충은 `DB_WRITE_URL`·`INTERNAL_API_KEY`를 사용합니다. 실제 비밀값은 실행 기록에 저장하지 않습니다.
- 크롤링이 끝난 뒤 B의 공간 보충기가 primary에서 활성 공간 수를 다시 세고, **유형별 최소 6개**까지 필요한 수만 `/internal/venues`로 등록합니다. 크롤러가 등록한 양은 부족분 계산에 쓰지 않습니다. 이미 목표 이상인 공간은 삭제하지 않습니다.
- 과거 행동 백필 전에는 MongoDB `events`에 공식 `docs/db/mongo_init.js`의 strict/error validator, `uq_event_id`, `received_at` 기준 365일 TTL이 먼저 적용돼 있어야 합니다. 생성기는 스키마·인덱스를 만들지 않습니다.

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

실행 후 `report.json`과 `manifest.json`을 DB 담당에게 전달합니다. `event_daily` 기간 재집계·CSV·정리 스크립트는 DB 담당 작업으로 남겨 둡니다. 원본 운영 이벤트를 삭제하거나 API 전달 성공률에 생성기 데이터를 포함하지 않습니다.

집계 키는 KST `occurred_at` 날짜, `event_type=event_name`, 공간별 문자열 `products[].product_id`(공간 없으면 null), `is_synthetic`입니다. CSV 컬럼은 #75 PM 댓글의 목록을 따릅니다. DB 산출물 이후 FE가 그래프를 확인합니다.

## 유형별 공간 보충 (#99)

보충기는 회원·예약 백필 CLI와 분리된 `venue_supplement` 명령입니다. 기본 프로필은 버전 관리되는 `venue_profiles.json`이며, 기본 목표는 유형별 활성 6곳입니다. 같은 유형의 활성·검증된 크롤링 공간이 있으면 한 공간의 지역·가격·인원·시간·시설 속성을 함께 사용합니다. 사용할 공간이 없으면 해당 유형의 기본 프로필을 적용합니다. 이름·소개는 생성하고 이미지는 유형별 `art:` 코드를 씁니다.

api1 또는 개발 환경의 저장소 루트에서 실행합니다. DB 연결은 `backend/.env` 또는 실행 환경의 `DB_WRITE_URL`·`INTERNAL_API_KEY`를 사용합니다. 비밀값은 명령 인자나 실행 기록에 넣지 않습니다.

```powershell
# primary 기준 미리보기: 기본은 화면에만 출력하고 DB·크롤러 상태를 쓰지 않음
conda run -n pro_1 --no-capture-output python -m simulator.generator.venue_supplement --dry-run

# 승인된 설정으로 계획을 보존한 뒤 검토
conda run -n pro_1 --no-capture-output python -m simulator.generator.venue_supplement --dry-run --save-plan --seed 9901

# 실제 등록: 새 작업은 매번 다른 seed를 사용
conda run -n pro_1 --no-capture-output python -m simulator.generator.venue_supplement --apply --seed 9902

# 중단된 작업: 출력된 run_id로 같은 계획을 재개
conda run -n pro_1 --no-capture-output python -m simulator.generator.venue_supplement --apply --resume <run_id>
```

`--target`은 기본값 6을 덮어쓸 때, `--profiles`는 별도 JSON 프로필을 검토할 때 사용합니다. `--resume`은 저장된 seed·목표·프로필·코드·DB·API 대상을 확인하고, 기존 계획에 남은 요청만 처리합니다. 응답이 유실된 요청은 primary에서 출처 ID와 속성을 대조합니다. 이미 활성 바닥선을 채웠으면 남은 요청은 건너뜁니다.

`logs/venue-supplement-<run_id>/`에 `manifest.json`, `plan.json`, `state.json`, `report.json`을 기록합니다. 계획에는 실행 시점의 유형별 활성 수와 부족분, 선택한 참고 속성, 실제 요청 JSON을 담고, 업체명·원문 소개·사진은 담지 않습니다. 기록은 재개를 위해 보존합니다. 보충 단독 실행과 #100 통합 실행은 `logs/.venue-pipeline.lock`을 공유합니다.

기존 DB 스냅샷으로 요청만 만들 때는 아래 오프라인 명령을 쓸 수 있습니다. HTTP 요청이나 DB 변경은 하지 않습니다.

```powershell
conda run -n pro_1 --no-capture-output python -m simulator.generator.topup --snapshot vetted_venues.json --output logs/topup-requests.json --seed 9903 --target 6
```

사전 계획·검증은 끝났지만 운영 MariaDB 등록과 api1 재개 확인은 아직 수행하지 않았습니다.

## 검증

```powershell
conda run -n pro_1 --no-capture-output python -m pytest simulator/generator/tests -q
```

[tests/README.md](tests/README.md)의 로컬 MariaDB 조건을 따릅니다. 테스트는 DB 트랜잭션을 롤백하며, api1 파일럿을 자동 실행하지 않습니다.
