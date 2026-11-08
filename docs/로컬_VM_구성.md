# 로컬 VM 구성 (1차 배포·측정·시연)

2026-11-05 · 공동 · PM 결정(노진산): **1차는 AWS 대신 팀 노트북 4대에 VM을 만들어 같은 공유기에 브리지로 붙인다.** 노트북은 모두 16코어·32GB로 같다. AWS 구성(`AWS_프리티어_구성.md`)과 확장안(`산출물_02` 1절부터)은 비교용 참고안으로 남긴다.

![다락큐브 시스템 아키텍처 1차 구성(로컬 VM)](figures/architecture.png)

## 현재 109 시험 배치 (11-07 실제 확인)

현재는 노트북 한 대의 VMware Workstation에 **7대가 모두 실행 중**이다. 제어 노드는 `ssh playdata` → `192.168.219.102`다. 아래 2절의 노트북 4대 분산·계획 사양은 11-09 이전 계획이며 현재 실측 사양과 구분한다.

| VM | 현재 IP | 실제 vCPU / RAM | 소프트웨어 |
| --- | --- | --- | --- |
| gw | 192.168.219.218 | 1 / 768MB | HAProxy 정문 |
| db1 | 192.168.219.212 | 1 / 2048MB | MariaDB 10.11.14 primary |
| mongo | 192.168.219.216 | 1 / 2048MB | MongoDB 8.0.34, 팀 OVA |
| api1 | 192.168.219.214 | 1 / 1536MB | Nginx + FastAPI, Uvicorn 2 workers / concurrency 200 |
| mon | 192.168.219.217 | 2 / 3072MB | Grafana·Prometheus·Loki·Alloy |
| api2 | 192.168.219.215 | 1 / 1536MB | Nginx + FastAPI, Uvicorn 2 workers / concurrency 200 |
| db2 | 192.168.219.213 | 1 / 2048MB | MariaDB 10.11.14 replica, read_only=1 |

DB node/mysqld exporter는 설치·자동 실행됐고 9100/9104는 mon .217만 허용한다. Prometheus는 **19/19 UP**이다. DB 한도는 양쪽 max_connections=151·max_user_connections=0·앱 개별 한도 0을 유지했다. [운영·모니터링 현황](DB_운영_모니터링_현황_2026-11-07.md)에 버전·권한·집계·검증·현재 대시보드를 모았다.

## 1. 왜 바꾸나

| | AWS C안 (11-04) | 로컬 VM (11-05) |
| --- | --- | --- |
| 비용 | 작업 시간만 월 약 $17, 크레딧 계정은 다 쓰면 닫힘 | **0원** |
| replica | 측정하는 날만 몇 시간 | **계속 켜 둠** |
| 모니터링 | Grafana Cloud 무료(외부) | **우리 VM**(`mon`)에서 Prometheus·Loki·Grafana |
| 서버 수 | EC2 3대 + RDS | **VM 7대** (확장안과 같은 역할 분리) |
| 장애 시연 | 가용 영역(2a·2c) 분리 | **노트북 분리**(노트북 한 대 전원을 꺼도 서비스 유지) |
| 배우는 것 | 관리형 서비스 | 리눅스 설치·systemd·방화벽·복제를 직접 |

## 2. 노트북별 배치 (11-09, 11-08 21시 PM 확정)

사양은 109 시험 서버에서 마지막으로 검증한 사양(11-08)의 **1.5배**다. 소수는 올렸다. 근거는 [수행결과 위키](https://github.com/encore-ai-campus/mlo-03-p1-team4/wiki/수행결과)와 아래 표의 109 최고 사용률이다. DB 3대와 정문은 노트북 1에 모은다.

| 노트북 (주인) | VM | vCPU / 메모리 / 디스크 | 109 검증 사양 · 최고 사용률(CPU/RAM) | 올리는 것 | 열 포트 ← 받는 곳 |
| --- | --- | --- | --- | --- | --- |
| **1** (DB 전희정) | `gw` 정문 | 2c / 1.5GB / 30GB | 1c / 768MB · 33% / 59% | **HAProxy**(80 → api1·api2 라운드로빈, `/health` 2초 능동 확인, `/api/internal`·`/api/metrics` 차단, 통계·지표 8404), Alloy | 80 ← 공유기 전체, 8404 ← mon |
| | `db1` MariaDB primary | 2c / 3GB / 30GB | 1c / 2GB · 52% / 30% | MariaDB 10.11.14(STRICT `sql_mode`, `+09:00`, utf8mb4), 백업 cron, mysqld exporter, Alloy | 3306 ← api1·api2·db2 |
| | `db2` MariaDB replica | 3c / 3GB / 30GB | 2c / 2GB · 59% / 33% | MariaDB replica(`read_only`, GTID 복제), mysqld exporter, Alloy | 3306 ← api1·api2 |
| | `mongo` | 2c / 3GB / 20GB | 1c / 2GB · 11% / 39%, 디스크 10GB에 여유 2GB | MongoDB 8.0.34(팀 OVA, 인증 켬, `docs/db/mongo_init.js`), 백업 cron, mongodb exporter, Alloy | 27017 ← api1·api2 |
| **2** (A 이자연) | `api1` FastAPI #1 | 6c / 2.5GB / 30GB | 4c / 1.5GB · 83% / 56% | **Nginx**(80: Vue 정적 파일 + `/api` → `127.0.0.1:8000`) + FastAPI(uvicorn 워커 2), cron: 이용 완료 배치(1시간)·크롤러(주 1회)·`replay_events.py`·`event_daily` 집계(매일 새벽), 데이터 생성기(과거 30일 백필, 수동 실행), `app.log`·`events.log`, `/metrics`, nginx exporter, Alloy | 80 ← gw, 8000 ← mon(지표) |
| | `mon` 모니터링 | 2c / 4.5GB / 30GB | 1c / 3GB · 6% / 31% | Prometheus(15일), Loki(14일), Grafana(현재 시험 서버 대시보드 11개, 경보 별도 확인) | 3000·9090 ← 공유기, 3100·지표 받기 ← 모든 VM |
| **3** (B 이세훈) | `api2` FastAPI #2 | 6c / 2.5GB / 30GB | 4c / 1.5GB · 68% / 54% | api1과 같은 Nginx·코드(cron 없음), `/metrics`, nginx exporter, Alloy | 80 ← gw, 8000 ← mon(지표) |
| **4** (FE·PM 노진산) | VM 없음 | — | — | Locust(부하·`SameSlotRush`·서버 끄기 시험), Playwright E2E(실제 API), 발표 브라우저·녹화 | Locust 웹 8089 ← 노트북 4 안에서만 |

| 노트북 | VM 수 | 쓰는 자원 | 노트북(16스레드·32GB) 대비 |
| --- | --- | --- | --- |
| 1 | 4 | 9c / 10.5GB / 110GB | 56% / 33% |
| 2 | 2 | 8c / 7GB / 60GB | 50% / 22% |
| 3 | 1 | 6c / 2.5GB / 30GB | 38% / 8% |
| 4 | 0 | Locust 약 1코어 (시험할 때만) | 넉넉함 |
| **합계** | **VM 7대** | **23c / 20.5GB / 200GB** | |

- **api1·api2를 다른 노트북에**: 노트북 2나 3을 꺼도 서비스가 버팀(서버 끄기 시연, A7은 노트북 3 끄기).
- **DB 3대와 정문을 노트북 1에**: DB 담당이 설치·복제·백업을 한곳에서 관리한다. 정문을 노트북 3에 두면 A7에서 정문까지 같이 꺼진다. 노트북 1이 꺼지면 DB가 멈춰 어차피 서비스가 멈추므로 장애 범위가 늘지 않는다.
- **바뀐 점**: db1→db2 복제가 같은 노트북 안에서 일어나 네트워크를 건너지 않는다. 복제·replica 읽기 기능은 그대로다.
- **3 vCPU(`db2`)**: VMware "소켓당 코어 수"를 1 또는 3으로 둔다. 109에서 소켓당 2코어로 3 vCPU를 주자 VM이 켜지지 않았다.
- **mongo 디스크**는 1.5배(15GB)보다 크게 20GB로 잡는다. 109에서 10GB 중 여유가 2GB였다.
- **Locust는 서버와 다른 노트북에**: 같은 노트북이면 CPU를 나눠 써서 측정이 틀어짐.
- **알려진 한계**: 노트북 1이 꺼지면 정문과 DB가 같이 멈춤. 공유기도 한 대. 1.5배는 여유 확보이며 1,000명 p95 500ms를 보장하지 않는다.

## 3. 월요일(11-09) 주소

| 이름 | IP | 노트북 |
| --- | --- | --- |
| `gw` | 192.168.0.211 | 1 |
| `db1` | 192.168.0.212 | 1 |
| `db2` | 192.168.0.213 | 1 |
| `mongo` | 192.168.0.216 | 1 |
| `api1` | 192.168.0.214 | 2 |
| `mon` | 192.168.0.217 | 2 |
| `api2` | 192.168.0.215 | 3 |
| 노트북 4 (관리·시연 PC) | 192.168.0.19 | 4 |

설치 템플릿(`infra/vm/lab/install-role.sh`·`haproxy*.cfg`·`prometheus.yml`)이 이 주소를 그대로 쓴다. 109에서는 `192.168.219.x`를 썼고 .211이 다른 기기에 잡혀 있어 `gw`만 .218이었다. 방화벽 템플릿의 SSH·통계 허용 주소는 노트북 4(.19)다.

- 공유기 관리 화면에서 VM의 MAC 주소마다 IP를 **DHCP 예약**한다(고정 IP를 VM 안에서 직접 줘도 됨).
- 모든 VM의 `/etc/hosts`에 위 이름을 넣어, 설정 파일에는 IP 대신 이름(`db1`, `api1`)을 쓴다.
- 백엔드 `.env`: `DB_WRITE_URL=mysql+pymysql://app:…@db1:3306/spacecube?charset=utf8mb4`, `DB_READ_URL=mysql+pymysql://app_ro:…@db2:3306/spacecube?charset=utf8mb4`, `MONGO_URL=mongodb://app:…@mongo:27017/spacecube`. 값은 팀 채널 비밀 메시지로 나눈다.

## 4. 방화벽 (`ufw`, AWS 보안 그룹 대신)

| VM | 허용 |
| --- | --- |
| 전부 | 22 ← 팀 노트북 4대의 IP만, 나머지 들어오는 것 거부 |
| `gw` | 80 ← 공유기 대역, 8404 ← `mon` |
| `api1`·`api2` | 80 ← `gw`, 8000 ← `mon`(지표만) |
| `db1` | 3306 ← `api1`, `api2`, `db2`; 9100·9104 ← `mon`만 |
| `db2` | 3306 ← `api1`, `api2`; 9100·9104 ← `mon`만 |
| `mongo` | 27017 ← `api1`, `api2` |
| `mon` | 3000·9090 ← 공유기 대역, 3100·9090 ← 모든 VM(Alloy) |

## 4-1. 정문 구성 (11-06 B안)

```
브라우저 ─▶ gw: HAProxy :80 ─▶ api1: Nginx :80 ─▶ FastAPI 127.0.0.1:8000
                            └▶ api2: Nginx :80 ─▶ FastAPI 127.0.0.1:8000
```

- HAProxy가 진입과 분산을 맡고, `GET /health`를 2초마다 확인해 2번 실패한 서버를 먼저 뺍니다(무료 Nginx는 요청이 실패해야 뺌). 결제(POST)는 다시 보내지 않습니다.
- 서버마다 Nginx가 화면 파일과 `/api` 전달을 맡아, 서버를 늘리면 HAProxy에 한 줄 더해 확장합니다.
- `gw` 한 대는 단일 장애점으로 남습니다(발표 범위에서 허용). 비교: [`figures/haproxy_compare.png`](figures/haproxy_compare.png), 원본 `figures/src/haproxy_compare.drawio`.

## 5. 11-05 결정과 바뀌는 점

| 결정 | AWS에서 | 로컬 VM에서 |
| --- | --- | --- |
| A6 RDS 백업 7일 | RDS 자동 백업 | `db1` cron: 하루 1회 `mariadb-dump` → `/var/backups/mariadb`, 7개 보관. `mongo`도 `mongodump` 7개 |
| A6 삭제 보호 | RDS 설정 | 해당 없음. 대신 **VM 스냅샷**(설치를 마친 뒤, 측정 전에 VMware Workstation 스냅샷) |
| A6 파라미터 그룹 | RDS 파라미터 그룹 | `/etc/mysql/mariadb.conf.d/90-spacecube.cnf`에 `sql_mode`·`default-time-zone`·문자셋 |
| A6 `X-Synthetic-Key`, Nginx `max_fails=2`, `limit_req` 안 넣음 | 그대로 | 그대로 |
| A7 측정 기준 | 그대로 | 그대로. 단 **유선 랜 기준**. 와이파이로 잰 값은 '참고'로 표시(응답 시간이 2~10ms씩 흔들림) |
| replica | 측정하는 날만 | 계속 켜 둠. 'replica 있음·없음' 비교는 `DB_READ_URL`을 비워 api 두 대를 다시 시작해서 함 |
| 연결 수 | RDS `db.t4g.micro` 약 35~40 | MariaDB 기본 `max_connections` 151. 풀 규칙(`backend/AGENTS.md`)은 그대로 |

## 6. 먼저 확인할 것

1. **공유기의 'AP 격리'(접속 기기끼리 통신 차단)가 꺼져 있는지.** 학원·공용 와이파이는 보통 켜져 있어 노트북끼리 VM이 안 보인다 → **팀 전용 공유기**를 쓴다.
2. **유선 연결.** USB 랜 어댑터 + 공유기 랜 포트를 권장. 와이파이 브리지는 어댑터·드라이버별 확인이 필요하며 측정이 흔들린다.
3. **가상화 프로그램.** 현재 109는 VMware Workstation + WSL2 Terraform/Ansible를 사용한다. 실제 LAN 어댑터에 브리지해야 하며 이 서버는 VMnet2를 쓴다. 다른 노트북은 브리지 이름·연결 어댑터를 따로 확인한다. WSL2를 위해 Hyper-V/VBS를 임의로 끄지 않는다.
4. **OS 이미지.** 일반 6대는 Ubuntu 24.04 cloud image, Mongo는 팀에서 받은 MongoDB 8.0.34 OVA를 사용한다. 일반 VM은 ubuntu, OVA는 test 계정과 전용 SSH 키로 점검한다.
5. **노트북 운영.** 측정·시연 동안 절전 끄기, 덮개를 닫아도 계속 켜짐, 전원 연결.
6. **발표 장소.** 시연은 같은 공유기 안에서만 된다. 발표 날은 노트북 4대와 공유기를 함께 가져가고, 안 되면 일요일에 찍어 둔 녹화로 대신한다.

설치 순서 체크리스트는 [`infra/vm/README.md`](../infra/vm/README.md).
