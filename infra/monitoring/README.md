# F-65 / #15 로컬 VM 모니터링

## 수집 방식

현재 7대 VM 배포 방식에 맞춰 **Prometheus가 exporter와 FastAPI `/metrics`를 직접 pull**하고, **Alloy는 시스템·앱 로그를 Loki로 전송**한다. Prometheus remote-write receiver는 켜지 않는다. Prometheus와 Alloy가 같은 지표를 중복 수집하지 않게 한다.

```text
node / FastAPI / HAProxy / Nginx / MariaDB / MongoDB / Alloy 지표 ─▶ mon Prometheus ─▶ Grafana
각 VM의 journal·app.log·events.log·Nginx 접근 로그 ─▶ Alloy ─▶ mon Loki ─▶ Grafana
```

`prometheus.yml`은 주소 대신 `gw`, `api1`, `api2`, `mon`, `db1`, `db2`, `mongo` 이름을 사용한다. 실제 주소는 환경별 이름 매핑에서 관리한다. 109 시험망과 최종 노트북망의 주소가 달라도 Prometheus·Alloy 설정 파일을 바꾸지 않도록 [`infra/vm/lab/install-role.sh`](../vm/lab/install-role.sh)와 [`infra/vm/remote109/build_config.py`](../vm/remote109/build_config.py)의 렌더링 결과를 확인한다.

| Scrape job | 대상 이름·포트 | 내용 |
| --- | --- | --- |
| `nodes` | 7대 VM `:9100` | 호스트 자원. Mongo VM node exporter 설치 상태 확인 필요 |
| `api` | `api1`, `api2`: `:8000/metrics` | FastAPI 요청·예약·이벤트 지표 |
| `haproxy` | `gw:8404/metrics` | HAProxy 백엔드 상태·분산 요청 |
| `nginx` | `api1`, `api2`: `:9113/metrics` | Nginx exporter |
| `mariadb` | `db1`, `db2`: `:9104/metrics` | MariaDB exporter |
| `mongodb` | `mongo:9216/metrics` | MongoDB exporter. 109에는 아직 설치되지 않아 DB 담당 확인 필요 |
| `alloy` | 7대 VM `:12345/metrics` | Alloy 에이전트 상태 |
| `prometheus`, `loki` | mon loopback `:9090`, `:3100` | 모니터링 서버 자체 상태 |

109의 기존 Prometheus job 이름(`nodes`, `api`, `mariadb` 등)과 서버 식별 라벨 `server`를 사용한다. HAProxy 자체 시계열의 `server`는 API 백엔드 이름(`api1`, `api2`)이므로 HAProxy scrape 대상에는 정적 `server` 라벨을 추가하지 않는다. Grafana 데이터소스 UID도 기존 `prometheus`·`loki`를 사용한다.

## Alloy 로그

각 `alloy-<VM>.alloy`는 journal을 읽는다. `api1`·`api2`는 아래 세 로그도 추가한다.

| 라벨 `source` | 경로 | `job` |
| --- | --- | --- |
| `app` | `/opt/spacecube/backend/logs/app.log` | `api` |
| `events` | `/opt/spacecube/backend/logs/events.log` | `api` |
| `nginx_access` | `/var/log/nginx/spacecube-access.log` | `nginx` |

경로는 현재 109 배포의 [`install-role.sh`](../vm/lab/install-role.sh)·[`nginx.conf`](../vm/lab/nginx.conf)와 맞췄다. Loki 라벨은 낮은 고정값인 `server`, `vm`, `job`, `source`만 쓴다. IP·개인정보·토큰·사용자 ID·세션 ID는 라벨에 넣지 않는다.

Grafana Explore에서 예를 들어 `{server="api1",source="events"}` 또는 `{server="mongo",source="journal"}`로 검색한다. 읽기 전용 점검에서는 기존 로그의 최근 유입 시각만 확인하고 시험 로그를 새로 발생시키지 않는다.

## 보관·경보·대시보드

- Prometheus: [`prometheus.service.example`](prometheus.service.example)의 `--storage.tsdb.retention.time=15d`. remote-write receiver 플래그 없음.
- Loki: [`loki.yml`](loki.yml)의 `retention_period: 336h`, TSDB 24시간 인덱스, retention을 켠 Compactor, `delete_request_store: filesystem`.
- 경보: [`alerts.yml`](alerts.yml). node exporter scrape 실패, Mongo 이벤트 저장 실패, 정상 예약 충돌 409를 분모에서 제외한 FastAPI 5xx 비율을 감시한다. 복제 지연 경보는 실제 exporter 이름을 확인한 뒤 추가한다.
- 이벤트 지표: `event_accepted_total`은 허용 이벤트의 문서 검증이 끝나 파일 기록을 시도할 때, `event_file_written_total`은 `events.log` append 성공 직후 증가한다. `mongo_event_written_total`은 백그라운드 writer의 새 저장 건수, `mongo_event_duplicates_total`은 `event_id` 중복으로 건너뛴 건수다. `mongo_event_write_failures_total`은 실패·대기열 포화/종료 건수이며 기존 `event_file_write_failures_total{stage,reason}`은 파일 실패 단계·원인을 구분한다. 이 값들은 이벤트 건수이며 HTTP 요청 수가 아니다. 이벤트 API 202는 파일 기록 성공을 뜻하며 Mongo 저장 완료를 뜻하지 않는다.
- `event_writer_queue_size`는 현재 writer 대기 문서 수의 근삿값이다. 두 작업자가 이미 꺼낸 처리 중 문서는 제외한다. `health_dependency_up{dependency="primary|replica|mongo"}`는 마지막 `/health` 확인 결과(1 정상, 0 장애)다. 지표가 아직 없거나 오래됐다면 상태를 알 수 없으므로 `up{job="api"}`로 앱 scrape 상태도 함께 확인한다. primary 장애 503, replica/Mongo 장애 degraded인 API 계약은 유지한다.
- 현재 Uvicorn은 서버당 worker 2개다. Python client의 일반 카운터·게이지는 프로세스별 메모리인데 Prometheus는 해당 주소의 한 worker에만 닿을 수 있다. 따라서 대시보드의 이벤트 합계·대기열·health 값은 전체 worker의 정확한 합계/상태가 아니다. `events.log`의 Loki 유입도 함께 보고, VM에서 실제 scrape와 worker별 수집 방식을 검증하기 전에는 전체 건수로 해석하지 않는다.
- 규칙 예제: [`alerts.test.yml`](alerts.test.yml)은 409만 발생, 5xx 기준 초과, 충돌이 많아도 5xx 기준 초과인 경우를 확인한다.
- 대시보드: [서비스](dashboard-service.json), [예약](dashboard-reservation.json), [DB](dashboard-db.json), [이벤트](dashboard-events.json). DB 연결 수·복제 지연과 Mongo 연결 수는 exporter의 실제 지표 이름을 확인하기 전까지 안내 패널로 둔다.
- MongoDB 원천은 `space_rental_analytics.events`, 일별 집계는 `event_daily`다. 기존 `db/aggregate/event_daily.py`의 CSV와 발표용 그래프를 우선한다. `crawl.crawl_raw`는 별도 DB의 크롤링 자료다. MongoDB 직접 Grafana 조회 경로는 미결정이다. MongoDB exporter 설치 여부와 실제 지표 이름은 DB 담당 확인 후 대시보드에 연결한다.
- 이 저장소의 Prometheus service 예시는 15일, Loki 설정 예시는 14일이다. 109 시험 VM의 `infra/vm/lab/install-role.sh`에는 별도 2일/2GB Prometheus 설정과 로그 회전(3개)이 있다. 실제 실행 인자·Loki 설정·로그 회전 적용 여부와 디스크 여유는 VM 소유자가 확인해야 한다. 디스크 부족의 현재 직접 신호는 파일 실패의 `reason="disk_full"`이다. 새 디스크 임계값은 정하지 않았다.

`alerts.yml`의 5xx는 `http_requests_total`에서 5xx를 세고 전체 요청에서 `reservation_total{result="conflict"}`를 뺀 비율이다. VM에서 HTTP 409 수와 conflict counter가 실제로 맞는지 확인해야 한다. 경보 시험은 승인된 시험 환경에서 정상 충돌만 발생할 때 경보가 울리지 않고, 5xx 비율이 기준을 넘을 때 울리는지 본다.

## 읽기 전용 조회 기준

작업판·잠금 상태와 실제 배포 커밋을 먼저 확인한다. PR의 이벤트 지표가 배포되지 않았다면 기존 수집 상태만 기록하고 새 지표는 배포 후 대기로 둔다. 조회 결과에는 이벤트 원문·사용자·세션 식별자를 넣지 않는다.

| 확인 대상 | 조회식 또는 API | 판정 시 주의 |
| --- | --- | --- |
| Prometheus target | `/api/v1/targets`의 `health`, `lastError`, `lastScrape` | `api`·`nodes`·`mariadb`·`mongodb`를 구분하고 설치 전 Mongo exporter를 앱 장애로 분류하지 않는다 |
| 앱과 저장소 | `up{job="api"}`, `health_dependency_up{job="api"}` | `/health`가 호출되지 않았거나 지표 미배포면 후자는 No data일 수 있다 |
| 이벤트 단계 | `event_accepted_total{job="api"}`, `event_file_written_total{job="api"}`, `mongo_event_written_total{job="api"}` | 2-worker 지표는 전체 건수의 정확한 합계가 아니다 |
| 파일·Mongo 실패 | `event_file_write_failures_total{job="api"}`, `mongo_event_write_failures_total{job="api"}` | 0과 지표 부재를 구분한다 |
| Loki 기존 로그 | `sum by (server) (count_over_time({server=~"api1|api2",source="app"}[5m]))`, `sum by (server) (count_over_time({server=~"api1|api2",source="events"}[5m]))` | 최근 이벤트가 없으면 events 로그 0건도 가능하며 로그 본문은 출력하지 않는다 |

Grafana에서는 기존 데이터소스 `prometheus`·`loki`의 연결 상태와 서비스·이벤트 패널의 실제 데이터/No data를 분리해 기록한다. 설정 파일의 보관값과 실행 중인 서비스 설정도 구분한다.

## 설치 확인 순서

VM 소유자와 작업 시간을 맞춘 뒤 진행한다. 109 부하 시험 등 다른 서버 작업이 진행 중이면 설정을 바꾸지 않는다.

1. 공용 작업판과 잠금 상태를 확인하고, api1·api2 배포 커밋이 PR 변경을 포함하는지 대조한다. 미배포면 새 지표는 배포 후 대기로 둔다.
2. `mon`의 Prometheus `/api/v1/targets`에서 job·서버별 `up`과 마지막 scrape 오류를 확인한다. MongoDB exporter가 없으면 DB 담당 확인 항목으로 남긴다.
3. Grafana의 기존 `prometheus`·`loki` 데이터소스와 이벤트·서비스 대시보드의 No data 여부를 확인한다. Loki에서는 api1·api2의 기존 app·events 로그 최근 유입 시각만 조회한다.
4. Prometheus 실행 인자·Loki 실행 설정·logrotate 설정과 디스크 여유를 읽어 저장소별 실제 보관 상태를 기록한다. 예시 설정 기간을 운영 적용값으로 간주하지 않는다.
5. 최종 노트북 7대 배치 후 같은 읽기 전용 확인을 반복하고 시각·누락 대상을 기록한다. 복제 지연 재현·경보 발화 시험은 별도 승인된 작업에서만 한다.

## 이 브랜치에서 로컬로 검사

- Alloy 7개 설정을 `alloy validate`로 검사한다.
- Prometheus 설정·경보를 `promtool check config` 및 `promtool check rules`로 검사하고 `promtool test rules`를 실행한다.
- Loki는 `-verify-config`로 검사하고, 대시보드 JSON·provisioning YAML을 파싱한다.
- `git diff --check`를 확인한다.

이 검사는 문법과 파일 연결만 보장한다. 실제 exporter 출력, 7대 Loki 검색, 보관 삭제 동작, 패널 표시, 경보 발화는 VM에서 확인해야 한다.
