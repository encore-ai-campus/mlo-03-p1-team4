# 109 시험 VM의 공통 서비스 설정

현재 실행 환경은 [remote109](../remote109/README.md)를 따른다. 이 폴더는 역할 설치·관측 설정·대시보드 생성에 필요한 공개 파일만 보관한다. 이전 사용자 PC 시험 VM은 삭제됐고 당시 host.py·관리 도우미는 이 변경에 포함하지 않는다.

- install-role.sh: gw/api1/api2/mon의 apt·systemd·방화벽 설정. 앱 Uvicorn은 2워커·동시성 200이다.
- haproxy-final.cfg: 실제 /health 기반 분산. haproxy.cfg는 DB 연결 전 기동 확인용 이력이다.
- nginx.conf: Vue 정적 파일과 /api 전달.
- prometheus.yml: 초기 .211 템플릿이며 remote109/build_config.py가 실제 gw .218로 렌더링한다. 직접 적용하지 않는다.
- dashboard-*.json: 현재 Grafana provisioning 산출물 11개.

## 메트릭과 로그 수집 경로

- 메트릭은 모니터링 VM의 Prometheus가 node exporter·FastAPI·HAProxy·Nginx·MariaDB exporter·Alloy `/metrics`를 직접 pull 합니다. `prometheus.yml`은 실험 VM용 초기 템플릿이며 109의 실제 주소와 DB exporter 대상은 원격 운영 설정에서 관리합니다.
- Alloy는 각 VM의 journal·로그 파일을 읽어 Loki로 전송합니다. Alloy 자체 상태 지표는 Prometheus가 Alloy `:12345/metrics`에서 pull 합니다.
- 현재 7 VM·19 target 구성에서는 이 pull 구조를 유지합니다. Alloy `prometheus.remote_write`를 Prometheus 자체로 밀어 넣으려면 Prometheus receiver를 켜고 포트 접근을 추가해야 하며, Prometheus는 receiver를 scraping의 대체 수집 경로로 쓰는 것을 권장하지 않습니다. 나중에 Mimir 등 Remote Write 저장소를 도입할 때 Alloy scrape + remote_write를 검토합니다.
- 마이그레이션을 할 경우 같은 target을 Prometheus와 Alloy가 동시에 수집하지 않도록 target 소유권·중복 시계열·`up` 상태·저장량을 단계별로 검증한 뒤 한쪽 scrape를 제거합니다.

기본 대시보드 JSON을 새로 만들 때는 conda pro_1에서 dashboards.py → overview.py → compare_apps.py → http_status_panels.py → style_dashboards.py → polish_dashboards.py 순서로 실행한다. 기존 servers/storage/logs JSON도 입력으로 사용하므로 삭제하지 않는다. 마지막 단계가 실제 109 수집 지표에 맞춰 패널을 정리한다. 109 배포용 build_config.py는 현재 JSON에 polish_dashboards.py를 적용한 뒤 설정 묶음을 만든다.

대시보드는 전체 현황, 서버, FastAPI, HAProxy, MariaDB, 이벤트·저장소, Nginx, Alloy, Loki, 로그 및 DB 앱별 연결·대기의 11개다. `verify-dashboard-queries.py`가 Grafana에 설치된 JSON을 읽어 각 PromQL·LogQL을 실제 Prometheus·Loki에 실행하며, 빈 결과와 쿼리 오류를 구분해 요약한다. exporter·데이터소스·대시보드 검증은 `deploy-109.ps1 -Action Dashboards`에 포함한다.

앱·DB 비밀번호는 런타임 보호 파일로만 전달한다. MariaDB exporter primary·replica가 온라인이며 연결·복제 지연·테이블 크기를 수집한다. MongoDB 8.0.34는 온라인이며 exporter는 미설치다. 11-07 현재 수집 대상은 19개다. 이 설정은 팀 분산 배치 및 infra/nginx·infra/haproxy의 정식 배포안을 대체하지 않는다.

11-07 저장 원본은 logs/read-high-20261107-183052/grafana-source.json에 보존했다. Grafana 파일 원본 변경을 먼저 적용하고 공급 폴링 후 API를 재조회해 유지 여부를 확인한다. UI 저장 직후 구 원본이 재공급되면 이전 화면으로 돌아갈 수 있다.

DASH-003: polish 다음 dashboard_handoff.py를 적용한다. 11개 탭과 8개 요약 카드의 반복 적용·패널 보존은 loadsuite/tests에서 검증한다.

11-08부터 build_config는 대시보드를 재생성하지 않고 검증된 JSON을 포장한다. health_app.py·spacecube-health.service와 nginx 두 health8001 경로 및 HAProxy큐를 함께 배포한다. 생성기를 직접 실행할 때만 polish→dashboard_handoff 순서로 명시 실행한다.
