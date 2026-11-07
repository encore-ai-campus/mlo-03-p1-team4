# HAProxy 정문 설정 (담당: B)

1차 로컬 VM 구성의 `gw`에서 사용합니다. 브라우저 요청을 두 API VM의 Nginx로 라운드로빈 분산합니다. 기준 파일은 `api1:80`·`api2:80` 이름을 사용하고, 실제 배포본은 `render_config.py`로 별도 생성합니다. IP·호스트 이름과 모니터링 접근 허용 CIDR은 배포 시 입력하며 기준 파일에 저장하지 않습니다.

- `GET /api/health`를 2초마다 확인하고 두 번 실패하면 해당 서버를 제외합니다. Nginx는 이 경로만 루프백 `8001/health`로 전달합니다. 업무 Uvicorn `8000`의 동시성 제한과 별도 프로세스로 분리합니다.
- 서버별 `maxconn 50`, 대기열 시간 제한 5초를 사용합니다. 업무 Uvicorn은 `--workers 2 --limit-concurrency 100 --timeout-keep-alive 5`를 유지합니다. Uvicorn 제한은 워커별 값이며, 50은 그보다 작은 초기값입니다. Nginx 유휴 연결·직접 내부 호출도 연결 수에 영향을 주므로 503이 절대 없다는 보장은 아닙니다. 배포 값을 낮추면 HAProxy 상한도 함께 낮춰야 합니다.
- `/api/internal`과 `/api/metrics` 및 하위 경로는 정문에서 거절합니다. `/api/internalized`처럼 접두어만 같은 다른 경로는 통과합니다.
- `retries 0`으로 예약·결제 POST를 다른 서버로 다시 보내지 않습니다. HAProxy 접근 로그는 메서드·상태·처리 시간·백엔드만 남기고 요청 경로·쿼리·IP·헤더를 제외합니다.
- `gw:8404/stats`와 `gw:8404/metrics`는 기준 파일에서 loopback만 허용합니다. 배포 시 `--monitor-source`로 실제 mon의 IP/CIDR을 지정합니다. 여러 출발지가 필요하면 옵션을 반복합니다. 자체 시험의 제어 PC 허용 결과는 아래 기록이며, mon scrape는 미검증입니다.

```bash
# API1_HOST·API2_HOST·MONITOR_CIDR은 배포 환경의 값으로 먼저 지정한다.
# Windows에서는 pro_1의 python으로 같은 CLI를 실행한다.
python3 infra/haproxy/render_config.py --api1 "$API1_HOST" --api2 "$API2_HOST" --monitor-source "$MONITOR_CIDR" --output /tmp/spacecube-haproxy.cfg
sudo haproxy -c -f /tmp/spacecube-haproxy.cfg
sudo install -o root -g root -m 0644 /tmp/spacecube-haproxy.cfg /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
```

서버 장애 시 `/api/health`가 503을 반환하는지와, 한 대를 중지한 뒤 정상 서버로 요청이 가는지는 실제 VM에서 확인해야 합니다.

## 독립 헬스 프로세스 (PR #66 후속)

`health_app.py`는 기존 `get_health()`를 재사용합니다. primary 장애는 503, replica·MongoDB 장애만 있으면 200 degraded라는 계약을 유지합니다. 먼저 로컬 업무 API `8000`의 기존 비동기 경로에 `HEAD /openapi.json`을 보내 응답 헤더를 확인합니다. 연결 제한 시간은 0.2초, 연결 후 소켓 제한 시간은 0.3초입니다. 본문을 받거나 업무 스레드 풀·DB를 추가 사용하지 않습니다. 연결 실패·HTTP 무응답·예상 밖 상태는 503으로 판정합니다. 로컬 응답 200과 Uvicorn 과부하 503은 응답 가능으로 처리하고, 별도 `get_health()`로 primary를 반드시 확인합니다. 과부하 503 때문에 두 노드가 함께 제외되는 문제를 피합니다.

이 확인은 한 연결의 응답 표본이며 모든 Uvicorn worker의 정상 동작을 보장하지 않습니다. 업무 서비스에서 OpenAPI 경로를 비활성화하거나 변경하면 검사 경로도 함께 검토해야 합니다.

api1·api2 모두 기존 backend 릴리스와 가상환경을 사용합니다. 새 패키지는 필요 없습니다. systemd가 업무 API와 같은 암호화 `backend-env` credential을 전달합니다. 업무 API·문서·지표·이벤트 기록기는 등록하지 않습니다. 상태 확인용 DB 연결은 프로세스별로 추가되므로 DB 연결 예산에 포함합니다.

```bash
# 새 코드만 배포 디렉터리에 추가한다. 업무 API 릴리스는 교체하지 않는다.
sudo install -d -o root -g spacecube -m 0750 /opt/spacecube/deploy/health
sudo install -o root -g spacecube -m 0640 infra/haproxy/health_app.py /opt/spacecube/deploy/health/health_app.py
sudo install -o root -g root -m 0755 infra/haproxy/start-health.sh /opt/spacecube/deploy/start-health.sh
sudo install -o root -g root -m 0644 infra/haproxy/spacecube-health.service /etc/systemd/system/spacecube-health.service
sudo install -d -o root -g spacecube -m 0750 /etc/spacecube
sudo install -o root -g spacecube -m 0640 infra/haproxy/health-deploy.conf.example /etc/spacecube/health-deploy.conf
# SPACECUBE_BACKEND_DIR와 SPACECUBE_VENV_DIR을 해당 API 배포 경로로 수정한다.
sudoedit /etc/spacecube/health-deploy.conf
sudo systemctl daemon-reload
sudo systemctl enable --now spacecube-health.service
```

서비스는 `spacecube` 사용자·그룹, `spacecube-api.service`, 암호화 credential 경로를 사용합니다. backend·venv 경로는 `/etc/spacecube/health-deploy.conf`의 비밀값 없는 배포 설정으로 받습니다. 예시의 `current/backend`는 해당 경로가 실제로 존재할 때만 사용하고, 업무 API와 같은 backend를 지정해야 합니다. 경로가 없으면 시작에 실패합니다. DB·JWT 값은 기존 암호화 credential로만 받습니다. `BindsTo`와 `PartOf`로 업무 서비스 중지·재시작을 따릅니다. 8001은 loopback에만 바인딩하고 외부 방화벽 포트를 추가하지 않습니다.

적용 순서는 **배포 경로 설정 → 헬스 프로세스 기동 → health 응답 확인 → Nginx 설정 검사·reload → 렌더링된 HAProxy 설정 검사·reload**입니다. 프로세스 시작 직후에는 초기화 시간이 필요하므로 health 200을 확인하고 진행합니다. 헬스 프로세스 없이 새 Nginx 설정만 적용하면 `/api/health`가 502가 됩니다. 실제 주소는 렌더링된 VM 배포본에만 들어갑니다.

설정 근거: [Uvicorn resource limits](https://www.uvicorn.org/settings/#resource-limits), [HAProxy 2.8 설정 문서](https://docs.haproxy.org/2.8/configuration.html).

## 자체 구성 테스트 환경 배포·시험 기록 (2026-11-07)

아래 VM 시험 중 30초 raw TCP 포화 수치는 이전 TCP-only 검사본의 결과입니다. HTTP 응답 검사 수정본의 배포 결과는 아래 별도 절에 기록합니다.

이 결과는 운영 환경이 아니라 사용자가 직접 구성한 bridged 테스트 VM에서 얻었습니다. MariaDB primary `192.168.0.212:3306/spacecube`는 SSH 없이 서비스 연결로만 사용했고, health와 categories 읽기 요청만 보냈습니다. 예약·결제 쓰기, DDL, 데이터 정리는 하지 않았습니다. MongoDB URL이 없어 health 본문 `degraded`/`mongo: down`은 예상 상태입니다.

| VM | 주소 | 적용·남긴 상태 |
| --- | --- | --- |
| gw | `192.168.0.231` | HAProxy 2.8.30 active·enabled, Nginx는 설정을 백업하고 inactive·disabled. `/etc/haproxy/haproxy.cfg` 검사 통과, 80·8404 listen |
| api1 | `192.168.0.232` | Nginx 1.24·FastAPI/Uvicorn active·enabled. 헬스 서비스 active·enabled. health 8001, 업무 API 8000은 loopback만 listen |
| api2 | `192.168.0.233` | api1과 같은 구성. 헬스 서비스와 업무 API는 모두 loopback만 listen |

gw의 원본 Nginx 설정은 `/opt/spacecube/backups/pr66-before-20261107-gw/nginx-etc.tgz`, 이전 HAProxy 설정은 같은 폴더의 `haproxy.cfg`에 보존했습니다. api1·api2의 Nginx·배포 복사본·API unit 백업은 각각 `/opt/spacecube/backups/pr66-before-20261107-api1/`, `...-api2/`에 있습니다. 새 헬스 앱·시작 스크립트는 `/opt/spacecube/deploy/health/`, `/opt/spacecube/deploy/start-health.sh`에 남겨 다음 시험에 재사용할 수 있습니다. 활성 Nginx 설정과 배포 복사본 해시는 두 API에서 `808cffe…`로 일치합니다.

확인 결과:

- Nginx `nginx -t`와 HAProxy `haproxy -c` 통과. 설정을 반영한 뒤 health/categories 200, `/api/internal/*`·`/api/metrics` 403.
- #67 회귀: `/`, `/venues`, `/index.html`, JS asset, WebP 모두 200. index `no-cache`, JS 1년 `public, immutable`, WebP 7일 `image/webp`, 없는 asset·사진 404.
- 새 연결 20건으로 round-robin을 확인: HAProxy 통계의 api1·api2 세션 증가가 각 10건.
- 30초 동안 각 API의 loopback 8000에 완료되지 않은 TCP 연결 240개를 유지한 부하 시험에서 api1 categories는 6/6회 503, health는 15/15회 200이었습니다. api2 categories는 5/6회 503·1/6회 200, health는 14/15회 200·1/15회 503이었습니다. 같은 구간 gateway health는 api1 부하 때 28/28회, api2 부하 때 26/26회 200이었고 두 backend는 계속 UP이었습니다. 독립 health 경로가 Uvicorn의 연결 포화와 분리됨을 확인했지만, 업무 API 포화 중에도 backend는 제외되지 않았으므로 실제 사용자 부하 기준 검증은 Locust로 남았습니다.
- gateway의 160개 동시 health 요청은 모두 200. HAProxy 통계에서 api1·api2 각각 최대 50 session을 관찰했고 설정 상한도 50입니다.
- api1·api2의 `spacecube-api.service`를 각 3회 중지·재기동해 매번 HAProxy backend가 DOWN→UP으로 복귀하는 것을 확인했습니다. 명령 제출부터 통계 상태 관측까지의 보수 상한은 api1 DOWN 3.25~3.78초·UP 6.23~6.47초, api2 DOWN 3.03~3.89초·UP 5.36~6.19초였습니다.
- 자체 구성 gw의 OUTPUT에서 api2 `192.168.0.233:80`만 임시 차단하자 HAProxy가 차단 명령 제출 후 6.46초 안에 api2를 DOWN 처리했습니다. DOWN 상태에서 gateway `/api/health`와 `/api/categories`를 각각 5회 읽어 모두 200이었고, HAProxy 세션 증가는 api1 10·api2 0이었습니다. 규칙 제거 후 api2는 2.69초 안에 UP으로 돌아왔습니다. 자동 복구 타이머까지 정리했고 최종 OUTPUT은 ACCEPT, 임시 규칙은 없음을 확인했습니다.
- 8404 stats·Prometheus는 시험 제어 PC `192.168.0.20`에서 200, api2에서 403. `mon` 실제 IP는 확인되지 않아 scrape 허용은 추가 확인이 필요합니다.

실행한 것은 설정 문법 검사와 위 읽기 전용 VM 시험입니다. 전체 `verify.ps1`, 예약 쓰기·중복 슬롯, MongoDB, `mon` scrape는 이 시험 범위에 없습니다. Nginx·HAProxy·API와 설정은 다음 시험용으로 유지하고 자동 시작을 확인했습니다.

## HTTP 응답 검사 수정 · 자체 구성 VM 배포 시험 (2026-11-07)

#66 PM 요청은 과부하 503을 헬스 장애로 전파하지 않는 것입니다. loopback 8000에 직접 연결한 포화 시험은 HAProxy maxconn 제한을 우회하므로 categories 503 자체로 정문 연결 제한의 결함을 입증하지 않습니다. 과부하 응답만으로 backend를 제외하도록 바꾸지 않습니다.

실제 결함은 TCP accept만 하는 멈춘 프로세스도 정상으로 판단하던 부분입니다. HTTP 응답 검사를 추가했고 `pro_1`에서 회귀 13건·Ruff 린트·포맷 확인이 통과했습니다. 실제 로컬 소켓이 연결만 수락하고 응답하지 않는 재현, 과부하 503 허용, primary 장애 503 유지, degraded 유지, 연결 거절·잘못된 HTTP·전송 실패를 확인했습니다. 실제 DB 연결은 대체했습니다. 기존 Starlette TestClient 경고 1건입니다.

수정본을 두 API VM에 배포하고 배포본 SHA-256이 양쪽에서 `ed33572d…eb96b082`로 일치함을 확인했습니다. 이전 앱은 `/opt/spacecube/backups/pr66-before-20261107-api1/health_app.py.before-http-response`와 `...-api2/...`에 보존했습니다. API를 중지하지 않고 `spacecube-health.service`만 재시작했습니다.

- api1·api2의 FastAPI·Nginx·health service 모두 active. 양 노드에서 loopback `HEAD /openapi.json`과 독립 `/api/health`는 정상 시 200.
- 각 노드에서 미완료 TCP 연결 240개를 잠시 유지해 업무 HEAD가 실제 503을 내는 동안 독립 health를 Nginx 경로로 5회 요청: api1·api2 모두 health 5/5회 200, categories 5/5회 503. 연결은 모두 닫았습니다. HAProxy의 두 backend는 시험 뒤 모두 UP으로 유지됐습니다.
- 부하 해제 후 HAProxy 경유 `/api/health`·`/api/categories`를 각 10회 요청해 모두 200. HAProxy api1·api2 상태도 UP.
- TCP accept 후 HTTP 무응답 감지 자체는 위 로컬 소켓 회귀로 검증했습니다. VM에서 실제 Uvicorn worker를 멈춘 장애 주입은 하지 않았습니다.

현재 두 API에는 수정본이 실행 중이며 health service는 enabled 상태입니다. HAProxy·Nginx 설정은 이번 배포에서 바꾸지 않았습니다.

## PR 준비 보완·최종 확인 (2026-11-07)

- 최신 `origin/develop` `97b533a`를 fast-forward 통합하고 STATE의 기존 기록을 보존했습니다.
- `pytest.ini` 기본 수집과 CI 변경 감지에 HAProxy 회귀를 연결했습니다. `verify.ps1`도 같은 수집 경로를 사용합니다. health 13건·배포 주소 생성기 17건, 총 30건 통과입니다.
- 기준 HAProxy 설정에서 시험 VM IP를 제거했습니다. 입력 검증이 있는 주소 생성기로 실제 배포본을 만들고 gw의 `haproxy -c` 통과 후 reload했습니다. health 서비스의 특정 릴리스 경로도 VM별 환경 파일로 옮겼으며, 양쪽 `bash -n`·`systemd-analyze verify`와 health 200을 확인했습니다.
- 최종 HTTP 검사·배포 설정으로 API1과 API2를 각각 1회 중지·복구했습니다. 각각 DOWN→UP, health 서비스 자동 재기동을 확인했습니다. 한 노드가 DOWN인 동안 gateway health·categories 각 3회, 두 시험 합계 12회 모두 200이었습니다. 자동 복구 타이머는 중지했고 서비스는 다음 시험용으로 남겼습니다.
- `verify.ps1`: Ruff 린트·122파일 포맷·프론트 verify는 통과했습니다. pytest는 487건 수집 중 공간 목록 4건이 실패했습니다. 로컬 MariaDB 11.4.13 `spacecube_test`에 기존 공간 21건이 있어 기대한 테스트 공간 외 데이터가 목록·페이지 수에 포함됐습니다. 실패 4건만 재확인해 같은 결과였으며 기존 데이터 삭제나 검증 완화는 하지 않았습니다. 깨끗한 MariaDB 11.4 CI 결과 확인 전 전체 검증 통과로 표시하지 않습니다.
- VM 실제 MariaDB는 계속 health·categories 읽기만 사용했습니다. 최종 worker hang 주입·Locust 사용자 부하·mon scrape는 미검증입니다. 해당 시험 시점에는 커밋·푸시하지 않았습니다.

푸시 준비 시 최신 develop `eca5a0e`를 추가 통합했습니다. 직전 기준 이후 변경은 STATE 기록뿐입니다. 공간 목록 fixture와 Locust 파일은 원복해 PR 변경에서 제외했고, 기존 테스트 실행 대상은 유지합니다. 로컬 목록 4건 실패는 기존 공유 데이터와 테스트 전제의 차이이며 GitHub CI의 새 임시 DB 결과를 별도로 확인합니다.
