# vm — 로컬 VM 설치 체크리스트 (담당: 공동, VM은 노트북 주인)

1차 배포·측정·시연은 팀 노트북 4대의 VM 7대로 한다(11-05). 배치·주소·방화벽·이유는 [`docs/로컬_VM_구성.md`](../../docs/로컬_VM_구성.md). AWS 체크리스트(`infra/aws/`)는 참고안이다. 서버에는 Docker를 쓰지 않고 apt·systemd로 설치한다.

## 0. 모두 한 번

- [ ] 팀 전용 공유기, AP 격리 끔, 가능하면 유선
- [ ] 노트북마다 BIOS 가상화 켬, VirtualBox 7 설치(같은 버전)
- [ ] Ubuntu Server 24.04 기본 VM 하나를 만들어 내보내기(OVA) → 팀원이 가져와 복제
  - 기본 VM에 미리: `chrony`, `timedatectl set-timezone Asia/Seoul`, `ufw`(22만 열고 켬), `unattended-upgrades` 끔(측정 중 재시작 방지), 사용자 계정
- [ ] VM 네트워크: **브리지 어댑터**(유선 랜 카드 선택), 복제할 때 MAC 주소 새로 만들기
- [ ] 공유기에서 VM마다 IP 예약(`docs/로컬_VM_구성.md` 3절), 모든 VM `/etc/hosts`에 이름 등록
- [ ] Grafana 저장소(apt) 추가: Alloy는 모든 VM, Loki·Grafana는 `mon`

## 1. 노트북 1 (DB 전희정)

- [ ] `db1`: MariaDB 11.4(MariaDB 공식 저장소, Ubuntu 기본은 10.11), `90-spacecube.cnf`(`sql_mode=STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION`, `default-time-zone=+09:00`, utf8mb4, `server_id=1`, `log_bin`, `gtid_strict_mode=ON`), 계정 `app`·`app_ro`·`repl`·`exporter`
- [ ] `db1`: `0001_init.sql` → `seed.sql` 적용, `db/tests/check_ddl.py`를 `CHECK_DB_URL`로 한 번 돌려 확인(`spacecube_test`)
- [ ] `db1`: 백업 cron(하루 1회 `mariadb-dump --single-transaction`, 7개 보관)
- [ ] `mongo`: MongoDB 7.0, 인증 켬, WiredTiger 캐시 1GB, `docs/db/mongo_init.js`, `db/tests/check_mongo_init.js`, 백업 cron(`mongodump`, 7개)
- [ ] `gw`: HAProxy(apt), `infra/haproxy/README.md` 설정(80 → `api1:80`·`api2:80` 라운드로빈, `/health` 확인 `inter 2s fall 2 rise 2`, `/api/internal`·`/api/metrics` 차단, 통계·Prometheus 지표 8404), Alloy가 8404 수집 (11-06 B안)
- [ ] 세 VM 모두 Alloy(로그 → `mon:3100`, 지표 → `mon:9090`), `ufw` 규칙

## 2. 노트북 2 (A 이자연)

- [ ] `api1`: Python 3.12 venv + `environment.yml`의 pip 버전, `backend/.env`(`DB_WRITE_URL=…@db1`, `DB_READ_URL=…@db2`, `MONGO_URL=…@mongo`, `SERVER_NAME=api-1`, `SYNTHETIC_API_KEY` 등), uvicorn systemd(`--workers 2`, 8000)
- [ ] `api1`: Nginx(apt), Vue 빌드(`frontend`에서 `npm run build` → `dist/`) 복사, `infra/nginx/README.md` 서버용 설정(정적 파일 + `/api` → `127.0.0.1:8000`), `stub_status` + nginx exporter (11-06 B안)
- [ ] `api1`: cron — 이용 완료 배치(1시간), 크롤러(주 1회, `crawler/AGENTS.md` 규칙), `replay_events.py`, `event_daily` 집계(매일 새벽)
- [ ] `api1`: 크롤러·생성기 실행 환경과 키(`INTERNAL_API_KEY`, DB·MongoDB 접속 정보)는 A가 설치(11-05 #38). 생성기 과거 30일 백필은 수동으로 한 번, 먼저 회원 100명으로 검증
- [ ] `mon`: Prometheus(15일, 원격 쓰기 받기 켬), Loki(14일), Grafana(3000) + 대시보드 4장(서비스·예약·DB·이벤트) + 경보(복제 지연 5초, 오류율)
- [ ] 두 VM 모두 Alloy, `ufw` 규칙

## 3. 노트북 3 (B 이세훈)

- [ ] `api2`: `api1`과 같은 Nginx·코드·설정(`SERVER_NAME=api-2`, cron 없음)
- [ ] `db2`: MariaDB 11.4, `server_id=2`, `read_only=ON`, GTID 복제(`CHANGE MASTER TO MASTER_HOST='db1', MASTER_USE_GTID=slave_pos`), `SHOW SLAVE STATUS`에서 지연 확인
- [ ] 두 VM 모두 Alloy(mysqld exporter 포함), `ufw` 규칙

## 4. 노트북 4 (FE·PM 노진산)

- [ ] Locust(conda `pro_1`), 대상 `http://gw`, `X-Synthetic`·`X-Synthetic-Key`
- [ ] Playwright E2E를 실제 API로(`VITE_USE_MOCK=false`, `baseURL=http://gw`)

## 5. 다 켠 뒤 확인

- [ ] 노트북 4 브라우저로 `http://gw` → 가입·로그인·검색·예약·취소·후기
- [ ] `http://mon:3000` 대시보드에 VM 7대 지표·로그가 들어옴
- [ ] `db2`에서 `SHOW SLAVE STATUS` 지연 1초 미만, `app_ro`로 쓰기가 막힘
- [ ] 노트북 3 전원을 끄고 Locust 1분 오류율 1% 미만(A7)
- [ ] 측정 전 모든 VM 스냅샷

## 끄는 순서

Locust 정지 → `api1`·`api2` → `gw` → `db2` → `db1`·`mongo` → `mon`. 켤 때는 반대(DB부터).

## 109 예비 실험 환경 (#70)

팀 분산 배치와 별도로 [109 자동화·조회 부하 기록](remote109/README.md)을 추가했다. 새 VM 4대는 한 호스트에 있으며 DB는 기존 서버를 사용하고 MongoDB는 제외했다. [선별 증거](remote109/records/README.md)와 [dd.md 검토·미완료 후속](remote109/DD-REVIEW.md)을 참고한다. 이 기록은 #13·#15·#16 전체 완료나 A7 판정이 아니다.
