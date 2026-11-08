# F-65 / #15 로컬 VM 모니터링

## 수집 방식

현재 7대 VM 배포 방식에 맞춰 **Prometheus가 exporter와 FastAPI `/metrics`를 직접 pull**하고, **Alloy는 시스템·앱 로그를 Loki로 전송**한다. Prometheus remote-write receiver는 켜지 않는다. Prometheus와 Alloy가 같은 지표를 중복 수집하지 않게 한다.

```text
node / FastAPI / HAProxy / Nginx / MariaDB / MongoDB / Alloy 지표 ─▶ mon Prometheus ─▶ Grafana
각 VM의 journal·app.log·events.log·Nginx 접근 로그 ─▶ Alloy ─▶ mon Loki ─▶ Grafana
```

`prometheus.yml`은 IP 대신 `gw`, `api1`, `api2`, `mon`, `db1`, `db2`, `mongo` 이름을 사용한다. IP 주소는 `/etc/hosts`의 환경별 이름 매핑에서 한 번만 관리하고 VM에 배포한다. 109 시험망(`192.168.219.x`)과 최종 노트북망(`192.168.0.211`~`.217`)의 주소가 달라도 Prometheus·Alloy 설정 파일은 바꾸지 않는다. 현재 배포 스크립트의 기본 매핑은 [`infra/vm/lab/install-role.sh`](../vm/lab/install-role.sh)에서 관리하고, 109 배포 묶음은 [`infra/vm/remote109/build_config.py`](../vm/remote109/build_config.py)가 시험망 주소로 렌더링한다.

| Scrape job | 대상 이름·포트 | 내용 |
| --- | --- | --- |
| `node` | 7대 VM `:9100` | 호스트 자원. Mongo VM node exporter 설치 상태 확인 필요 |
| `api` | `api1`, `api2`: `:8000/metrics` | FastAPI 요청·예약·이벤트 지표 |
| `haproxy` | `gw:8404/metrics` | HAProxy 백엔드 상태·분산 요청 |
| `nginx` | `api1`, `api2`: `:9113/metrics` | Nginx exporter |
| `mysql` | `db1`, `db2`: `:9104/metrics` | MariaDB exporter |
| `mongodb` | `mongo:9216/metrics` | MongoDB exporter. 109에는 아직 설치되지 않아 DB 담당 확인 필요 |
| `alloy` | 7대 VM `:12345/metrics` | Alloy 에이전트 상태 |
| `prometheus`, `loki` | mon loopback `:9090`, `:3100` | 모니터링 서버 자체 상태 |

Prometheus의 모든 원격 대상에는 `vm` 라벨을 붙인다. HAProxy 자체 시계열의 `server` 라벨은 API 백엔드 이름(`api1`, `api2`)을 보존하므로 scrape 대상에도 `server` 라벨을 덮어 씌우지 않는다.

## Alloy 로그

각 `alloy-<VM>.alloy`는 journal을 읽는다. `api1`·`api2`는 아래 세 로그도 추가한다.

| 라벨 `source` | 경로 | `job` |
| --- | --- | --- |
| `app` | `/opt/spacecube/backend/logs/app.log` | `api` |
| `events` | `/opt/spacecube/backend/logs/events.log` | `api` |
| `nginx_access` | `/var/log/nginx/spacecube-access.log` | `nginx` |

경로는 현재 109 배포의 [`install-role.sh`](../vm/lab/install-role.sh)·[`nginx.conf`](../vm/lab/nginx.conf)와 맞췄다. Loki 라벨은 낮은 고정값인 `server`, `vm`, `job`, `source`만 쓴다. IP·개인정보·토큰·사용자 ID·세션 ID는 라벨에 넣지 않는다.

Grafana Explore에서 예를 들어 `{server="api1",source="events"}` 또는 `{server="mongo",source="journal"}`로 검색한다. 실제 적용 확인은 각 VM에서 `logger "monitor-probe-<VM>"`를 발생시키고 같은 라벨로 검색한다. 시험 데이터가 Loki에 보이는지와 7대 각각을 구분할 수 있는지를 기록한다.

## 보관·경보·대시보드

- Prometheus: [`prometheus.service.example`](prometheus.service.example)의 `--storage.tsdb.retention.time=15d`. remote-write receiver 플래그 없음.
- Loki: [`loki.yml`](loki.yml)의 `retention_period: 336h`, TSDB 24시간 인덱스, retention을 켠 Compactor, `delete_request_store: filesystem`.
- 경보: [`alerts.yml`](alerts.yml). node exporter scrape 실패, Mongo 이벤트 저장 실패, 정상 예약 충돌 409를 분모에서 제외한 FastAPI 5xx 비율을 감시한다. 복제 지연 경보는 실제 exporter 이름을 확인한 뒤 추가한다.
- 규칙 예제: [`alerts.test.yml`](alerts.test.yml)은 409만 발생, 5xx 기준 초과, 충돌이 많아도 5xx 기준 초과인 경우를 확인한다.
- 대시보드: [서비스](dashboard-service.json), [예약](dashboard-reservation.json), [DB](dashboard-db.json), [이벤트](dashboard-events.json). DB 연결 수·복제 지연과 Mongo 연결 수는 exporter의 실제 지표 이름을 확인하기 전까지 안내 패널로 둔다.
- MongoDB용 공식 Grafana 데이터 소스는 Grafana Enterprise 플러그인이므로 OSS 대시보드에 사용하지 않는다. 30일 `event_daily` 분석은 PM·DB가 CSV 표/그래프 또는 MariaDB 분석용 표 중 정한 방식을 별도로 준비한다.

`alerts.yml`의 5xx는 `http_requests_total`에서 5xx를 세고 전체 요청에서 `reservation_total{result="conflict"}`를 뺀 비율이다. VM에서 HTTP 409 수와 conflict counter가 실제로 맞는지 확인해야 한다. 경보 시험은 승인된 시험 환경에서 정상 충돌만 발생할 때 경보가 울리지 않고, 5xx 비율이 기준을 넘을 때 울리는지 본다.

## 설치 확인 순서

VM 소유자와 작업 시간을 맞춘 뒤 진행한다. 109 부하 시험 등 다른 서버 작업이 진행 중이면 설정을 바꾸지 않는다.

1. 7대 모두 `mon` 이름을 해석하고 Alloy가 `mon:3100`에 연결되는지 확인한다.
2. `mon`에서 Prometheus `/api/v1/targets`를 열어 job과 VM별 `up` 상태를 확인한다. 7개 node exporter 및 Mongo exporter가 아직 설치되지 않은 대상은 설치 후 다시 검사한다.
3. Grafana Explore에서 7대 probe 로그를 각각 검색한다. `api1`·`api2`는 app, events, Nginx 접근 로그도 확인한다.
4. Prometheus 실행 인자에서 15일 보관, Loki `/config`와 상태에서 14일 보관·Compactor 활성화를 확인한다.
5. DB 담당과 테스트 replica에서만 5초 초과 지연을 안전하게 재현해 복제 상태·exporter 지표·경보를 대조한다. 실제 운영 복제를 임의로 멈추지 않는다.
6. 최종 노트북 7대 배치 후 같은 확인을 반복하고 결과·시각·누락 대상을 기록한다.

## 이 브랜치에서 로컬로 검사

- Alloy 7개 설정을 `alloy validate`로 검사한다.
- Prometheus 설정·경보를 `promtool check config` 및 `promtool check rules`로 검사하고 `promtool test rules`를 실행한다.
- Loki는 `-verify-config`로 검사하고, 대시보드 JSON·provisioning YAML을 파싱한다.
- `git diff --check`를 확인한다.

이 검사는 문법과 파일 연결만 보장한다. 실제 exporter 출력, 7대 Loki 검색, 보관 삭제 동작, 패널 표시, 경보 발화는 VM에서 확인해야 한다.
