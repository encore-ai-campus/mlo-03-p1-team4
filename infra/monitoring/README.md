# F-65 / #15: 로컬 VM 모니터링 (A)

1차 대상은 `gw`, `db1`, `mongo`, `api1`, `mon`, `api2`, `db2` 7대다. 각 VM의 `alloy-<VM>.alloy`를 Grafana Alloy에 적용하고, `mon`에서 Prometheus·Loki·Grafana OSS를 apt·systemd로 운영한다. 이 파일들은 설치 전 초안이며 VM에는 적용하지 않았다. Docker·AWS 설정은 1차안이 아니다.

## 환경 구분: 109 시험과 최종 7대 VM

| 구분 | 109 시험 환경 (PM의 11-06 기록) | 이 저장소의 최종 배포 설정 |
| --- | --- | --- |
| 위치·방식 | `ssh playdata`의 VMware 시험 서버, `gw .218`·`api1 .214`·`api2 .215`·`mon .217`·`db1 .212`·`db2 .213`; `mongo .216`은 주소만 예약 | 팀 노트북 4대에 VM 7대, 주소는 `docs/로컬_VM_구성.md`의 예시를 실제 배치 때 확정 |
| 지표·로그 | PM 기록상 Prometheus 대상 15개 UP, Nginx 2/2, Loki 로그 4대 확인. DB exporter 지표는 미확인 | 7대 각각의 Alloy가 로컬 exporter를 수집해 mon으로 전송; 7대 로그 검색·exporter·보관 동작은 아직 검증하지 않음 |
| MongoDB | 당시 미설치, `/api/health` degraded 및 이벤트 저장 실패 경고 발생 | MongoDB 설치·exporter·이벤트 저장 확인 대기 |
| 수집 포트 | 시험 서버의 exporter는 mon에서 접근하는 기존 방식. 9104 등 실제 개방·접근 제어를 DB/B와 확인해야 함 | 아래 Alloy 파일은 같은 VM의 loopback exporter를 긁어 mon으로 밀어 보내는 방식. 기존 시험 서버에 그대로 덮어쓰지 않음 |

109의 `15개 UP`과 `4대 로그`는 **PM이 제공한 시험 기록**이며 이 브랜치의 새 설정을 적용해 검증했다는 뜻이 아니다. 109의 부하 수치도 GET 시험과 뒤이은 쓰기 시험을 구분한다. 저녁 시험은 Locust HTML·CSV가 없어 Nginx 접근 로그·Prometheus 기반이며 가상 사용자 수와 Locust 실패율은 알 수 없다. 기존 `docs/로컬_VM_구성.md`의 VirtualBox·IP는 계획 예시이므로 109 주소로 치환하지 않는다.

**11-07 PM 후속 결정(#15 댓글):** 109 시험 서버에서 먼저 검증하고, 11-09 오전 팀 노트북 4대로 옮긴 뒤 최종 7대 수집을 다시 확인한다. 109 네트워크는 `192.168.219.0/24`로 변경됐다. 당시 시험 주소는 `gw .218`, `api1 .214`, `api2 .215`, `mon .217`, `db1 .212`, `db2 .213`, `mongo .216`이다(각 주소 앞에 `192.168.219`를 붙임). 이 값은 **109 시험 시점의 주소**이며 최종 노트북 배치 주소가 아니다. 이전 `192.168.0.x`는 현재 109에 쓰지 않는다. PM 댓글 당시 API 두 대는 DB 연결 미완료로 `/health` 503이었고, DB 재연결·재배포 후 상태는 다시 확인해야 한다. 사용자 제공 16:40 KST 진행 파일은 MongoDB 8.0.34 인증 사용·db2 지연 0초를 보고하므로, 두 기록의 시각 차이를 유의하고 실제 서비스에서 재확인한다.

이 브랜치 Alloy 설정은 수집 대상이 모두 `127.0.0.1`이고 수신 서버는 `mon` 호스트명이다. **219 IP를 7개 Alloy 파일에 직접 넣지 않는다.** 시험·최종 배치 때 DNS 또는 배포 inventory에서 `mon` 이름의 실제 주소를 정하고, 각 VM의 이름 해석·연결을 검증한다. `/etc/hosts`를 수동으로 7대 각각 수정하면 '한 곳만 바꾸기'가 아니므로 최종 배치에는 DNS 또는 단일 inventory에서 `/etc/hosts`를 배포하는 절차가 필요하다. 현재 저장소에는 그 자동 배포 절차가 없으며 PM·VM 담당과 확정해야 한다. 기존 109 Prometheus pull 대상과 새 Alloy remote write를 동시에 켜면 중복 지표가 생길 수 있으므로 적용 전에 109의 실제 scrape 설정을 확인한다.

## 파일과 배치

| 파일 | 설치 위치 | 기능 |
| --- | --- | --- |
| `alloy-*.alloy` | 각 VM `/etc/alloy/config.alloy` | 호스트 지표·시스템 journal, 역할별 지표·로그 |
| `alloy.service.example` | 각 VM systemd override 참고 | Alloy 실행·재시작 |
| `prometheus.yml`, `alerts.yml` | mon `/etc/prometheus/` | 지표 설정·경보 |
| `alerts.test.yml` | 저장소의 로컬 검사 전용 | 409 집중·5xx 경보 Prometheus 규칙 시험. VM에는 복사하지 않음 |
| `prometheus.service.example` | mon systemd override 참고 | 15일 보관·remote write 수신 활성화 |
| `loki.yml`, `loki.service.example` | mon `/etc/loki/`, systemd override 참고 | 14일 보관·Compactor 활성화 |
| `grafana-*.yml` | mon `/etc/grafana/provisioning/datasources/`, `dashboards/` | 데이터 소스·대시보드 등록 |
| `dashboard-*.json` | mon `/var/lib/grafana/dashboards/` | 서비스·예약·DB·이벤트 4장 |

각 Alloy는 `mon:9090/api/v1/write`와 `mon:3100/loki/api/v1/push`로 전송한다. VM의 exporter는 loopback만 열고 mon의 9090·3100은 팀 VM 대역만 허용한다. Grafana 3000은 운영자만 접근한다. 중앙 pull 방식과 달리 서버 간 exporter 포트를 열지 않아도 된다. Prometheus remote write receiver는 기본값이 꺼져 있으므로 `--web.enable-remote-write-receiver`가 필수다. Loki는 `retention_period: 336h` 외에도 TSDB 24시간 인덱스·Compactor·`delete_request_store: filesystem`을 켜야 14일 보관이 실제 적용된다. 보관 기간은 디스크 용량 상한이 아니므로 `df -h`도 운영 중 본다.

## 설치·비밀값 절차 (VM 소유자 실행)

1. Ubuntu 24.04 VM에 apt 패키지로 Alloy·Prometheus·Loki·Grafana OSS 및 필요한 exporter를 설치하고 버전을 기록한다. `/etc/hosts` 또는 DNS에 `mon`을 등록한다. 패키지별 `systemctl cat`으로 실제 실행 파일·계정·데이터 경로를 확인한다. Alloy는 패키지 기본 unit과 `/etc/default/alloy`를 우선 사용하고, 필요한 설정만 drop-in으로 보완한다. Prometheus·Loki의 `.service.example`도 기존 unit과 대조한 뒤 적용한다.
2. `alloy` 계정에 `adm,systemd-journal` 그룹을 추가하고 서비스를 재시작한다. API 서비스의 `LOG_DIR=/var/log/spacecube`를 권한 파일/환경 파일로 지정해야 이 설정의 `app.log`·`events.log` 경로와 맞는다(앱 기본값은 `backend/logs`). Alloy에는 해당 로그와 Nginx 접근 로그 읽기 권한만 준다. 배포 경로가 다르면 Alloy의 경로를 바꾼다.
3. DB exporter의 계정·비밀번호·MongoDB URI는 root 소유 `0600` 권한 파일에 넣고 systemd `EnvironmentFile=`로 주입한다. 계정·URI·토큰을 저장소, Alloy 설정, 로그에 쓰지 않는다. Grafana 관리자 비밀번호는 `GF_SECURITY_ADMIN_PASSWORD`를 0600 환경 파일로 주입한다. Nginx 접근 로그의 토큰·쿼리·개인정보 제거는 B와 확인한다.
4. `systemctl status`/`journalctl -u`로 확인한다. mon의 `/api/v1/status/flags`에서 remote write receiver=true·retention.time=15d, Loki `/config`에서 Compactor retention=true·period=336h·delete store=filesystem을 확인한다. `/ready`와 Grafana `/api/health`, Prometheus `up{job="node"}` 7개를 확인한다. 109에서 먼저 시험할 때는 최종 7대 완료 판정과 분리한다. 14일 지난 시험 로그의 삭제는 Compactor 지연 후 관찰한다.

## 현재 연결된 것과 실제 출력 대기

모든 VM: Alloy 내장 unix exporter의 CPU·메모리·디스크·네트워크 지표 및 systemd journal. `api1`·`api2`: FastAPI `127.0.0.1:8000/metrics`, Nginx exporter `127.0.0.1:9113/metrics`, `app.log`·`events.log`·`/var/log/nginx/access.log`. `gw`: HAProxy `127.0.0.1:8404/metrics`. `db1`·`db2`: mysqld exporter `127.0.0.1:9104/metrics`. `mongo`: mongodb exporter `127.0.0.1:9216/metrics`. Nginx/HAProxy exporter 설정은 B, DB exporter 계정·설정은 DB 담당 제공 대기다. 미제공 exporter의 `up=0`은 예상 상태다.

코드에서 확인한 앱 지표는 `reservation_total{result="ok|conflict|cancel"}`, `mongo_event_write_failures_total`, `db_read_fallback_total`이다. 로컬 TestClient의 실제 `/metrics` 200 응답에서 `http_requests_total{status,handler,method}`와 `http_request_duration_highr_seconds_bucket`도 확인했다. 서비스 대시보드·경보의 5xx 오류율은 **5xx 요청 / (전체 HTTP 요청 − `reservation_total{result="conflict"}`)** 이다. B 코드에서 이 카운터는 `SLOT_TAKEN` 409 직전에 증가한다. 109 쓰기 ②처럼 409가 몰려 5xx 비율이 희석되는 문제를 줄인다. Prometheus 규칙 시험은 409만 발생, 5xx 10%, 충돌 90%와 5xx 동시 발생 세 경우를 통과했다. 실제 VM에서 HTTP 409 수와 conflict 카운터가 일대일인지 비교해야 하며, 불일치하면 쿼리를 다시 조정한다. 이 수치는 서버 오류율이며 모든 4xx 업무 오류를 포함한 총 오류율은 아니다. DB 연결·복제 지연·워커별 연결 수·DB 풀 대기·이벤트 수신은 실제 exporter/수집 출력의 이름과 라벨을 확인할 때까지 대기 패널이다. `alerts.yml`에는 node exporter 수집 실패·Mongo 쓰기 실패·5xx 오류율만 활성화했다. Alloy 자체가 죽으면 `up=0`도 전송되지 않으므로 VM별 `absent_over_time` 점검을 운영에서 별도로 추가해야 한다.

109 쓰기 ② 기록에는 업무 503 174건과 `/health` 503 8건이 별도로 있다. 운영 대시보드에서는 `handler`별 업무 요청과 헬스체크를 나눠 확인하고 HAProxy가 서버를 제외한 시각을 맞춰 봐야 한다. 당시 MongoDB 미설치로 저장 실패 경고가 20:22에만 분당 약 4,800건 발생했다는 PM 기록은 의도된 시험 조건이다. 실제 운영의 Mongo 실패 경보 검증과 섞지 않으며, 경고 로그의 CPU 영향이나 DB 병목 원인은 이 기록만으로 확정하지 않는다.

## 재현 가능한 VM 검증

- 로그: 7대 각각 `logger "monitor-probe-<VM>"`를 실행한 뒤 Grafana Explore에서 `{vm="<VM>",source="journal"} |= "monitor-probe-"`를 찾는다. VM 목록은 `gw db1 mongo api1 mon api2 db2`. 앱은 `{vm="api1",source="app"}`, `{vm="api1",source="events"}`, 접근 로그는 `{vm="api1",source="nginx_access"}`로 검색한다. `vm`·`source`는 고정 저카디널리티 라벨만 쓰며 개인정보·토큰·세션 ID·IP를 라벨로 넣지 않는다.
- 복제 지연: DB 담당과 **테스트 replica**에서 복제를 잠시 멈춰 `SHOW REPLICA STATUS`의 `Seconds_Behind_Master`와 exporter 실제 series를 비교한다. 지표명 확인 후 `ReplicaLagOver5Seconds`를 `> 5`, `for: 2m`로 경보에 추가하고 5초 초과를 2분 유지해 Alertmanager/Prometheus 규칙 상태를 확인한다. 시험 후 복제를 재개한다. 실제 VM·DB에서 임의 중단하지 않는다.
- 오류율: 허용된 테스트 환경에서 정상 2xx, 정상 `SLOT_TAKEN` 409, 의도한 5xx를 구분해 생성한다. 현재 경보는 5분 5xx 요청/(전체 요청−정상 충돌 카운터) > 5%가 5분 지속될 때 발생한다. 정상 충돌만 늘어난 구간은 경보가 없어야 하고, 충돌이 많아도 5xx가 기준을 넘으면 떠야 한다. 409 HTTP 응답 수와 예약 conflict 카운터가 일치하는지 검증한다. 업무 오류 4xx까지 포함하는 종합 오류율은 별도 분류가 필요하다.

## 담당자 요청·미결

| 담당 | 요청할 정확한 제공물 |
| --- | --- |
| DB | db1·db2 `127.0.0.1:9104/metrics`용 최소 권한 mysqld exporter 계정과 0600 자격 파일/systemd 주입 방식, 연결 수·복제 지연 실제 지표 샘플 및 `SHOW REPLICA STATUS` 대조. mongo `127.0.0.1:9216/metrics`용 최소 권한 monitor 계정·비밀 URI 주입 방식·샘플. 외부 포트 불필요. |
| B | gw `127.0.0.1:8404/metrics` HAProxy 실제 응답·접근 범위, api1/api2 Nginx 내부 `stub_status` 경로·`127.0.0.1:9113/metrics` exporter 응답, 접근 로그 실제 경로·민감정보 제거 방식, FastAPI HTTP `/metrics` 샘플. |
| DB·PM | `event_daily` 집계 실행 파일·인자·환경 파일·멱등성·잠금·완료 시각·재실행 절차와 30일 결과 CSV 형식 결정. 전달되면 A가 api1 **한 대**의 04:00 KST cron에 연결하고 exit code·로그 회전·중복 실행 방지를 확인한다. 집계 코드는 DB 범위다. |

공식 Grafana MongoDB 데이터 소스는 Enterprise 플러그인이라 Grafana OSS 1차안의 무료 기능으로 쓸 수 없다. PM·DB가 `event_daily` 30일 결과를 CSV로 내보내 표·그래프를 만들거나 MariaDB 분석용 표로 옮겨 기본 SQL 데이터 소스로 조회하는 안 중 선택한다. 원천 Mongo 이벤트·14일 운영 Loki 로그를 30일 집계로 취급하지 않는다.

참고: [Prometheus 수신 플래그](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/), [Loki 보관](https://grafana.com/docs/loki/latest/operations/storage/retention/), [Grafana MongoDB 플러그인](https://grafana.com/docs/plugins/grafana-mongodb-datasource/latest/).

## 로컬 설정 검사 (11-07, 실제 VM 검증 아님)

- 공식 Windows 실행 파일을 작업용 OS 임시 폴더에서만 사용: Alloy 1.21.3 `alloy validate`는 7개 파일 각각 통과, Prometheus 3.16.0 `promtool check rules`는 3개 규칙 통과. `promtool test rules alerts.test.yml`의 세 시나리오도 통과. `promtool check config --syntax-only` 통과. 전체 `check config`는 Linux의 `/etc/prometheus/alerts.yml` 경로를 Windows 검사본의 실제 경로로 바꾼 뒤 규칙 파일까지 통과했다. 저장소의 배포 경로는 바꾸지 않았다.
- Loki 3.7.9 `-config.file=... -verify-config` 통과. Grafana provisioning을 포함한 설정 YAML 5개와 시험 YAML 1개 파싱 및 대시보드 JSON 4개 파싱 통과. `git diff --check` 통과.
- 위 검사는 문법·파일 연결만 입증한다. VM의 apt 패키지 버전, exporter 응답, 파일 권한, 실제 remote write·Loki 적재, 보관 삭제, 패널·경보 동작은 별도로 확인해야 한다.

## PM 부하시험 자료와 #15 남은 작업 (11-07)

PM 제공 자료 `read-high-20261107-183052`·`write-high-20261107-191153`는 당시 시험 중 지표가 수집됐다는 **보조 증거**다. 읽기 400명은 378건 실패(약 1.78%)로 중단됐다. 쓰기 100명은 오류 없이 끝났고, 200명 예약 POST p95는 약 1,022ms였다. 쓰기 400명 목표 단계는 로그인·워밍업 문제로 실제 398명만 측정했고 기존 예약 재응답도 있어 실패 처리됐다. 이전 읽기와 쓰기는 배포·공간 수·설정이 달라 성능 개선의 직접 비교로 쓰지 않는다. 해당 시험은 이 브랜치 설정을 배포한 시험이 아니므로 #15 VM 완료 증거로 대체할 수 없다.

두 자료에는 Prometheus 19/19 대상 UP 확인, MariaDB exporter 연결·복제 지연 시계열 및 Grafana 대시보드 상태가 포함된다. 복제 지연은 관측 구간에서 0초였다. 다만 5초 초과 경보 발화, 오류율 경보가 실제로 울린 기록, 본 브랜치의 Loki에서 7대 로그를 각각 검색한 결과, 15일/14일 보관의 실제 적용은 확인되지 않았다. 쓰기 시험의 DB 풀 획득 대기도 미계측이다.

PR 리뷰 후 남은 작업은 순서대로 진행한다.

1. DB 담당에게 MariaDB·MongoDB exporter 최소 권한 계정/환경 파일 방식과 실제 `/metrics` 샘플, 복제 지연 series를 받고 B 담당에게 HAProxy·Nginx 상태 경로와 exporter 샘플을 받는다.
2. 승인된 서버 작업 시간에 109에서 이 설정을 적용하고 Prometheus remote write 수신, Loki 적재, exporter 지표, 앱·Nginx 로그 권한과 경로를 확인한다. 기존 pull scrape와 중복 수집 여부도 점검한다.
3. Grafana Explore에서 7대 각각의 probe 로그를 검색하고, 4개 대시보드가 실제 series를 표시하는지 확인한다.
4. mon 실행 설정에서 Prometheus 15일·Loki 14일 및 Loki Compactor를 확인한다. 5초 복제 지연은 테스트 replica에서만 재현하고, 오류율은 409 제외·5xx 포함 조건과 실제 경보 이력으로 검증한다.
5. 팀 노트북 최종 7대 배치 후 주소·로그·지표·보관을 다시 확인하고 결과를 이 표와 `STATE.md`에 기록한다.

각 단계의 검증 명령·시각·결과·미해결 문제를 PR에 남긴다. DB 복제 중단은 테스트 replica와 담당자 동의·복구 계획이 준비된 경우에만 한다. 설정 배포나 경보 발화가 확인되기 전에는 #15를 완료로 닫지 않는다.
