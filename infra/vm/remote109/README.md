# 109 원격 시스템 자동화 — 2026-11-07 현황

현재 운영값의 기준은 [DB·모니터링 현황](../../../docs/DB_운영_모니터링_현황_2026-11-07.md)이다. 11-06의 4대·Mongo 제외·192.168.0.x 결과는 과거 실험이다.

| VM | 현재 주소 | vCPU / RAM | 역할 |
| --- | --- | --- | --- |
| gw | 192.168.219.218 | 1 / 768MB | HAProxy 정문 |
| api1 | 192.168.219.214 | 1 / 1536MB | Nginx·FastAPI |
| api2 | 192.168.219.215 | 1 / 1536MB | Nginx·FastAPI |
| mon | 192.168.219.217 | 2 / 3072MB | Grafana·Prometheus·Loki·Alloy |
| db1 | 192.168.219.212 | 1 / 2048MB | MariaDB 10.11.14 primary |
| db2 | 192.168.219.213 | 1 / 2048MB | MariaDB 10.11.14 replica |
| mongo | 192.168.219.216 | 1 / 2048MB | MongoDB 8.0.34, 팀 OVA |

`ssh playdata`는 현재 192.168.219.102 WSL2 제어 노드다. VMware에 **7대 실행**, 별도 Terraform 상태에 6대, Mongo는 OVA 가져오기로 확인했다. 기본 wsl-vmware-lab 예제 상태를 적용하지 않는다. 6대 SSH 사용자는 ubuntu, Mongo OVA는 test이며 전용 키를 사용한다.

## 현재 접속·모니터링

- [서비스](http://192.168.219.218/) — 정문 원점. Locust 요청 경로에 /api를 한 번 붙인다.
- [전체 현황](http://192.168.219.217:3000/d/spacecube-overview)
- [MariaDB 전체](http://192.168.219.217:3000/d/spacecube-mariadb)
- [앱별 DB 연결·대기](http://192.168.219.217:3000/d/spacecube-db-connections)
- [FastAPI](http://192.168.219.217:3000/d/spacecube-api) · [Nginx](http://192.168.219.217:3000/d/spacecube-nginx) · [HAProxy](http://192.168.219.217:3000/d/spacecube-haproxy)
- [서버 자원](http://192.168.219.217:3000/d/spacecube-servers) · [저장소·이벤트](http://192.168.219.217:3000/d/spacecube-storage) · [Alloy](http://192.168.219.217:3000/d/spacecube-alloy) · [Loki](http://192.168.219.217:3000/d/spacecube-loki) · [로그](http://192.168.219.217:3000/d/spacecube-logs)

Grafana 11개 대시보드·Prometheus 19/19 UP을 확인했다. 파일 원본은 mon /var/lib/grafana/dashboards, 최근 30분·Asia/Seoul·15초 갱신을 저장했다. UI 저장 허용·파일 삭제 시 대시보드 보존 설정을 적용했다. UI 저장은 DB에 반영되지만 이후 같은 원본 파일을 덮으면 파일 값이 우선하므로 재배포 전에 persist_dashboards.py로 현재 화면을 백업·동기화한다. 비밀번호는 보호된 설정에만 둔다.

메트릭은 Prometheus가 exporter와 API `/metrics`를 직접 pull 하고, Alloy는 각 VM 로그를 Loki로 전송한다. Prometheus도 Alloy `:12345/metrics`를 scrape 해 에이전트 상태를 본다. Alloy remote_write를 Prometheus 자체로 보내는 구조는 아직 적용하지 않았다. 원격 쓰기 수신 기능·9090 접근 제어·중복 scrape 전환이 필요하고, 공식 Prometheus 문서도 이를 scrape 대체용으로 권장하지 않는다.

두 DB에는 node exporter 1.7.0·mysqld exporter 0.15.0과 앱별 연결 집계 타이머를 적용했다. [db-monitoring](db-monitoring/README.md) 참고. max_connections=151, 전역/앱 사용자 제한=0을 유지했다. replica IO/SQL Yes·지연 0초, API /health ok를 확인했다. Mongo exporter는 설치하지 않았으며 Mongo 자원은 이번 실행기 SSH 표본으로 수집한다.

## 현재 실행기·파일 위치

| 위치 | 내용 |
| --- | --- |
| 이 폴더 loadsuite/ | 새 읽기·쓰기·경합·혼합 단계 실행기와 순수 로직 테스트 |
| 로컬 logs/loadsuite-날짜-시각/ | 요청별 JSONL·Locust CSV/HTML·자원 시계열·RESULTS.md |
| 109 ~/spacecube109/SERVER_WORK_BOARD.md | 작업 예약·인계의 실시간 기준 |
| 109 ~/spacecube109/overlay/infra/vm/remote109 | 실제 6대 Terraform 상태·배포 자동화 |
| 109 ~/spacecube109/source | 남아 있는 checkout은 9b9b223. 실제 배포 SHA로 사용하면 안 됨 |
| 109 ~/.config/spacecube109 | 전용 키·보호된 앱/Grafana 설정 |

Claude 인계의 배포 SHA는 1583778이다. 실행기는 실제 배포 OpenAPI를 별도 보존한다. 로컬 구버전 이벤트 payload와 배포 v1 계약 차이를 확인하고 새 실행기를 맞췄다.

```powershell
& "$env:USERPROFILE\anaconda3\envs\pro_1\python.exe" -u infra/vm/remote109/loadsuite/runner.py
```

새 실행기는 합성 전용 계정·예약·후기를 만들고 API로 정해진 시험을 수행한다. 비밀번호·JWT·합성 키는 메모리에만 두며 DB 대량 삭제·연결 제한/워커 변경은 하지 않는다. 1명 점검 → 인증/경합 → 공개 읽기·예약 5→20→50명 → 나머지 쓰기 5명 → 혼합 50명 10분 순서다. 오류율 1% 이상·계약 오류·fixture 소진 시 중단한다. 현재 100/200/400명은 이 실행 범위에 포함하지 않는다.

아래는 이전 4대 자동화 도구의 절차다. 현재 6대 상태·Mongo OVA·DB exporter 변경을 보존하는지 먼저 검토한다. 특히 예전 build_config.py/renderer가 기존 Prometheus 설정을 덮으면 DB 대상이 빠질 수 있어 connect_prometheus.py 재적용·19개 대상 검증이 필요하다. 부하 실행 중에는 배포·서비스 재시작을 하지 않는다.

## 기존 자동화 실행 절차 — 재배포 전 확인

```powershell
# 매번 109 preflight를 거친다. Plan은 적용하지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Plan
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Status

# 새 VM 생성: 최초 OFF → cloud-init → ON. 이미 준비된 VM은 재생성하지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Create

# Grafana JSON만 mon에 복사하고 Grafana만 재시작한 뒤 PromQL·LogQL을 실서버에 조회한다.
# 앱·Prometheus·MariaDB 설정은 건드리지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Dashboards

# 현재 작업 소스의 프론트를 실제 API 모드로 빌드하고 Ansible로 배포한다.
# SourcePath를 주면 그 소스의 backend와 frontend를 사용한다. 비밀 파일은 묶지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Configure

# 이 PC에서만 부하를 만든다. 조회 전용, DB 쓰기 없음.
powershell -NoProfile -File infra/vm/remote109/run-experiments.ps1 -Users 5 -Duration 30s
powershell -NoProfile -File infra/vm/remote109/run-experiments.ps1 -Users 50 -Duration 60s -SkipBrowser
powershell -NoProfile -File infra/vm/remote109/run-experiments.ps1 -SkipLoad
```

`On`·`Off`는 이번 state에 VM 4대가 모두 있을 때만 전원을 변경한다. 운영 중 부하 시험과 동시에 실행하지 않는다.
삭제 명령은 이 실행기에 넣지 않았다. 삭제가 필요하면 실제 API·state·파일 경로를 대조해 별도 검토한다.

최초 DB 런타임 설정은 `create_runtime.py`에 JSON을 stdin으로 전달해 만든다. 비밀번호는 인자나 tfvars에 넣지 않는다.
현재는 이미 설정돼 있다. 키는 재실행 시 유지하며 두 앱에 같은 값을 전달한다.

## 스킬

사용자 요청으로 `vmware-wsl-lab` 4675414를 설치했다.

- 이 PC: `C:\Users\jinsa\.agents\skills\vmware-wsl-lab`
- 109 WSL: `/home/playdata/.agents/skills/vmware-wsl-lab`
- 109 기반 저장소: `/mnt/c/Users/Playdata/wsl-vmware-lab`
- preflight: vmrest 미인증 401 / 인증 200, 도구·기존 부팅 작업 점검 통과.

다음 대화부터 `$vmware-wsl-lab`로 호출할 수 있다. 목록에 안 보이면 Codex를 다시 시작한다.
스킬의 기본 네트워크는 NAT/host-only지만, 이번 새 시스템은 사용자 지시에 따라 브리지로 확장했다. 기반 템플릿과 기존 실습 네트워크는 변경하지 않았다.

## 결과와 공유

- `RESULTS.md`: 검증·예비 부하 결과와 한계.
- `TROUBLESHOOTING.md`: 발생·확인·처리·검증 기록.
- `UPSTREAM-ISSUE-DRAFT.md`: `naelonambul/wsl-vmware-lab`에 공유할 익명화 이슈 초안. 공유 기록이며 이슈 #1로 게시했다.

GitHub 게시에는 실행 원문이나 `.env`·개인키·state·생성 inventory를 첨부하지 않는다.

단계별 읽기 부하: `run-capacity.ps1`. 실행·해석·결과는 [LOAD-RESULTS-20261106.md](LOAD-RESULTS-20261106.md).


## 현재 실험 방법과 증거

현재 배포 코드는 develop d00988b, VM은 109 단일 호스트, Uvicorn 2워커·동시성 200이다. 단계를 실행하려면 `./infra/vm/remote109/run-capacity.ps1 -Stages @(50,100,200,400) -Seconds 60`을 사용한다. 요청 종류는 GET 유형·검색·상세·시간 칸이며 사용자 대기는 1~3초다. 각 단계 10초 내 목표 사용자에 도달하도록 증가율을 정하고 history CSV의 실제 인원을 확인한다.

실패율 1% 초과·p95 500ms 초과·실행 오류·목표 미도달이면 상승을 중단한다. SSH 전후 검사는 실제 DB 헬스와 6:6 분산·15개 지표·Nginx·Loki 라벨을 확인한다. CPU는 1분 rate를 15초 간격으로, 메모리는 MemAvailable 기준으로 저장한다. 결과는 logs 아래 CSV·HTML·JSON·Markdown으로 생성되며 Git에서 제외된다.

[공유용 증거](records/README.md), [실험 해석](LOAD-RESULTS-20261106.md), [dd.md 검토](DD-REVIEW.md), [DB 요청](DB-MONITORING-REQUEST.md)을 참고한다. 판정용 A7 10분·유선·워밍업 제외 혼합 시험이 아니며 DB 쓰기·로그인 부하·동시 예약은 아직이다.
