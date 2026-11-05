# aws — 팀원별 AWS 구성 체크리스트 (공동)

네 명이 각자 자기 계정에 같은 구성을 올립니다. 자세한 이유와 비용은 [AWS 네트워크 설계](../../docs/AWS_네트워크_설계.md)에 있습니다.

## 내 번호의 값

| 팀원 | VPC | Nginx | FastAPI #1 / #2 | 모니터링 | MongoDB |
| --- | --- | --- | --- | --- | --- |
| 1번 | 10.11.0.0/16 | 10.11.1.10 | 10.11.1.11 / 10.11.2.11 | 10.11.1.31 | 10.11.2.21 |
| 2번 | 10.12.0.0/16 | 10.12.1.10 | 10.12.1.11 / 10.12.2.11 | 10.12.1.31 | 10.12.2.21 |
| 3번 | 10.13.0.0/16 | 10.13.1.10 | 10.13.1.11 / 10.13.2.11 | 10.13.1.31 | 10.13.2.21 |
| 4번 | 10.14.0.0/16 | 10.14.1.10 | 10.14.1.11 / 10.14.2.11 | 10.14.1.31 | 10.14.2.21 |

위 표는 확장안 주소다. **1차 C안은 MongoDB가 Nginx와 같은 정문 서버(`10.1n.1.10`)에 있고, 모니터링 서버는 없다**(Grafana Cloud).

## 1차는 프리 티어안 — C안: EC2 3대, Docker 없이 직접 설치 (11-04)

기준: [AWS 프리 티어 구성](../../docs/AWS_프리티어_구성.md). 평소엔 아무것도 켜지 않고 노트북(`infra/local` compose)으로 개발한다.

- [ ] 크레딧 방식 계정(2025-07-15 이후). 결제 콘솔에서 크레딧 잔액·만료일 확인(무료 플랜은 소진 또는 6개월에 계정이 닫힘)
- [ ] AWS Budgets $10·$30 알림
- [ ] 리전 서울, VPC `10.1n.0.0/16`, 서브넷 4개: public-a `.1.0/24`(2a), public-c `.2.0/24`(2c), private-db-a `.21.0/24`, private-db-c `.22.0/24`. 퍼블릭 라우팅 테이블에만 `0.0.0.0/0 → IGW`(NAT 없음)
- [ ] 보안 그룹 4개: sg-web(80 ← 전체, 22 ← 내 IP/32) · sg-mongo(27017 ← sg-app) · sg-app(8000 ← sg-web, 22 ← 내 IP/32) · sg-db(3306 ← sg-app)
- [ ] RDS MariaDB 11.4 db.t4g.micro 단일 AZ(2a), 20GB gp2, 퍼블릭 액세스 끔, 자동 백업 7일(백업 저장은 DB 크기까지 무료)·삭제 보호·파라미터 그룹(`time_zone=Asia/Seoul`, utf8mb4, **`sql_mode=STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION`**)
- [ ] RDS에 `db/migrations/0001_init.sql` → `db/seed/seed.sql` 적용(②에서 접속), `db/tests/check_ddl.py`를 `CHECK_DB_URL`로 RDS의 `spacecube_test`에 한 번 돌려 파라미터 그룹까지 확인
- [ ] ① 정문 EC2 t4g.micro(public-a, `10.1n.1.10`, 탄력적 IP): Nginx, MongoDB 7.0(인증 켬, WiredTiger 캐시 0.25GB, `docs/db/mongo_init.js` 실행), 스왑 1GB, Alloy
- [ ] ② FastAPI #1 t4g.micro(public-a, `10.1n.1.11`): Python 3.12 venv + `environment.yml` 버전, uvicorn systemd 유닛(`--workers 2`), 이용 완료 배치·크롤러 cron, Alloy
- [ ] ③ FastAPI #2 t4g.micro(public-c, `10.1n.2.11`): ②와 같게, cron 없음
- [ ] 각 서버 `.env`(`SERVER_NAME`, `DB_WRITE_URL`, `MONGO_URL`=①, Grafana Cloud 토큰). 비밀값은 파일로 돌리지 않음
- [ ] Grafana Cloud 무료 스택, 세 서버의 Alloy가 로그·지표를 밀어 보냄
- [ ] 확인: 정문 주소로 `/api/health`가 두 서버에서 번갈아 응답, ③을 중지해도 요청이 ②로 감
- [ ] 측정하는 날만 read replica 생성 → Locust 비교 → **삭제**
- [ ] 다 쓰면 EC2 3대 중지 → RDS 일시 중지(7일 뒤 저절로 켜짐 주의). 정문 탄력적 IP는 꺼 둬도 요금이 나감. 프로젝트 끝나면 전부 삭제(RDS는 **삭제 보호를 먼저 끔**, 최종 스냅샷은 만들지 않음)

## 확장안 만드는 순서 (11-03, 기준 `docs/산출물_02` 5~6절, 크레딧이 넉넉할 때)

- [ ] 리전 서울(ap-northeast-2)
- [ ] VPC `10.1n.0.0/16`, 서브넷 4개: public-a `.1.0/24`(2a), public-c `.2.0/24`(2c), private-db-a `.21.0/24`(2a), private-db-c `.22.0/24`(2c)
- [ ] 인터넷 게이트웨이 연결, 퍼블릭 라우팅 테이블에만 `0.0.0.0/0 → IGW` (NAT 게이트웨이 없음)
- [ ] 보안 그룹 5개: sg-web, sg-app, sg-db, sg-mongo, sg-mon (인바운드 표는 `산출물_02` 5절)
- [ ] RDS MariaDB 11.4 db.t4g.micro primary(2a) + read replica(2c), DB 서브넷 그룹, 퍼블릭 액세스 끔
- [ ] EC2 t4g.micro 3대: Nginx(탄력적 IP), FastAPI #1·#2(사설 IP 고정)
- [ ] EC2 t4g.small 2대: MongoDB(public-c, 인증 켬), 모니터링(public-a, Docker Compose)
- [ ] AWS Budgets 월 예산 알림 (1인당 24시간 켜면 약 $116)

## 안정성 체크리스트 (11-03 방향: 먼저 띄우고 잰 뒤 더함)

### 1차 필수 (만들 때 같이)

- [ ] RDS: 자동 백업 7일, 삭제 보호, 파라미터 그룹(`time_zone=Asia/Seoul`, utf8mb4, `sql_mode`에 STRICT_TRANS_TABLES), 저장공간 자동 확장, 만든 뒤 `SELECT @@max_connections` 확인
- [ ] SSH 22는 내 IP/32만, AWS Budgets 알림
- [ ] 정문 Nginx 1차 보강(`infra/nginx/README.md`)
- [ ] 띄운 뒤 잴 것: p95·오류율, EC2 CPU·`CPUCreditBalance`, RDS 연결 수·`ReplicaLag`, 서버 1대 끄기 시험 (`docs/인프라_트래픽_안정성_검토.md` 1-1절)

### 나중에 추가 (조건을 넘을 때만, `STATE.md` B 목록)

- [ ] 정문 ALB(2a·2c) + 헬스체크 `/api/health` + ACM·Route 53 (B1)
- [ ] 시작 템플릿 + Auto Scaling 그룹(최소 2·최대 4), cron은 모니터링 EC2로 (B2)
- [ ] EC2·RDS 크기, replica 추가, Multi-AZ (B3~B5)
- [ ] CloudWatch 경보 → SNS, 런북 (B6), SSM Session Manager·Parameter Store (B7), 요청 제한 (B8), MongoDB 스냅샷 자동화 (B9)
- [ ] 끄는 순서: (ASG 0) → EC2 중지 → RDS 일시 중지 → replica 삭제 → 공인 IP 정리

## 할 일

- [ ] 손으로 만든 뒤 같은 구성을 다시 만들 수 있게 CloudFormation 또는 Terraform으로 옮길지 결정
- [ ] 안 쓸 때 끄기: EC2 중지 → RDS 일시 중지(최대 7일). replica는 일시 중지가 안 되니 테스트가 끝나면 지움. 탄력적 IP와 스토리지는 꺼도 요금이 나감
