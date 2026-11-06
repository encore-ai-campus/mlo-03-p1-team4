# 109 시험 VM의 공통 서비스 설정

현재 실행 환경은 [remote109](../remote109/README.md)를 따른다. 이 폴더는 역할 설치·관측 설정·대시보드 생성에 필요한 공개 파일만 보관한다. 이전 사용자 PC 시험 VM은 삭제됐고 당시 host.py·관리 도우미는 이 변경에 포함하지 않는다.

- install-role.sh: gw/api1/api2/mon의 apt·systemd·방화벽 설정. 앱 Uvicorn은 2워커·동시성 200이다.
- haproxy-final.cfg: 실제 /health 기반 분산. haproxy.cfg는 DB 연결 전 기동 확인용 이력이다.
- nginx.conf: Vue 정적 파일과 /api 전달.
- prometheus.yml: 초기 .211 템플릿이며 remote109/build_config.py가 실제 gw .218로 렌더링한다. 직접 적용하지 않는다.
- dashboard-*.json: 현재 Grafana provisioning 산출물 9개.

대시보드를 재생성할 때 conda pro_1에서 dashboards.py → overview.py → compare_apps.py → style_dashboards.py 순서로 실행한다. 기존 servers/storage/logs JSON도 입력으로 사용하므로 삭제하지 않는다. 마지막 스타일 단계가 작은 카드·2열 그래프·단위·CPU 쿼리 보정을 적용한다.

앱·DB 비밀번호는 런타임 보호 파일로만 전달한다. DB exporter는 설치 대기, MongoDB는 제외다. 이 설정은 팀 분산 배치 및 infra/nginx·infra/haproxy의 정식 배포안을 대체하지 않는다.
