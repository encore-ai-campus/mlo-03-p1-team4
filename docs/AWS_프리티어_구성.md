# AWS 프리 티어 구성 (무료 위주, 크레딧 조금)

> **11-05 결정:** 1차 배포·측정·시연은 AWS 대신 **팀 노트북 4대의 VM 7대**로 합니다([로컬 VM 구성](로컬_VM_구성.md)). 이 문서의 AWS 내용은 비교용 참고안입니다.

2026-11-04 · 공동 · 사용자 결정: AWS는 프리 티어 안에서, 웬만하면 무료로, 크레딧은 조금만 쓴다. **크레딧 방식(2025-07-15부터 만든 계정)**으로 하고, **EC2 3대에 Docker 없이 직접 설치(C안)**한다.

## 1. 결론

- **평소 개발·검증은 노트북**에서 한다(무료). MariaDB 11.4·MongoDB 7은 `infra/local` docker compose로 띄운다. 이 Docker는 로컬 전용이다.
- **AWS는 EC2 3대 + RDS 1대**, 배포 리허설·측정·시연 때만 켠다. EC2에는 **Docker를 쓰지 않고** apt로 설치해 systemd로 돌린다.
  - ① 정문 EC2: Nginx + MongoDB
  - ② FastAPI #1 (+ 이용 완료 배치·크롤러 cron)
  - ③ FastAPI #2 (다른 AZ)
- 서버가 실제로 2대라 **Nginx 라운드로빈, 한 대를 꺼도 버티는지, AZ를 나눈 배치**를 발표에서 그대로 보여 줄 수 있다.
- **read replica는 비교 측정하는 날 몇 시간만** 만들고 지운다. 평소에는 `DB_READ_URL`을 비워 primary 하나로 돈다(`get_db_read()`가 primary로 대체).
- **모니터링은 Grafana Cloud 무료**. 모니터링 EC2는 만들지 않고, 각 EC2의 Alloy가 로그·지표를 밀어 보낸다.
- 작업 시간에만 켜면 **월 약 $17**, 24시간 켜면 월 약 $57(4절). 크레딧 $100~200 안에서 프로젝트 기간을 버틴다.
- **무료 플랜 계정은 크레딧을 다 쓰거나 6개월이 지나면 닫힌다.** 결제 콘솔에서 크레딧 잔액을 주마다 보고, AWS Budgets로 $10·$30 알림을 건다.

`산출물_02` 5·6절의 구성(EC2 5대 + RDS 2대, 월 약 $116)은 **확장안**으로 남긴다. 구성 요소와 경로(primary/replica, MongoDB, 로그·지표)는 같고, MongoDB를 정문 EC2에 같이 두고 모니터링을 Grafana Cloud로 옮긴 것만 다르다.

## 2. 계정 방식 (참고)

| | 2025-07-15 이전에 만든 계정 | 2025-07-15부터 만든 계정 (**우리 기준**) |
| --- | --- | --- |
| 방식 | 12개월 동안 월 사용량 한도 안에서 무료, 넘으면 요금 | 가입 크레딧 $100 + 활동으로 최대 $100 더(총 $200), 사용량이 크레딧에서 빠짐 |
| 기간 | 가입 후 12개월 | 6개월 또는 크레딧을 다 쓸 때까지 |
| 무료 EC2 종류 | `t2.micro`, `t3.micro` | `t3.micro`, `t3.small`, `t4g.micro`, `t4g.small` 등 |
| 넘으면 | 그만큼 요금 청구 | 무료 플랜이면 계정이 닫힘(유료 플랜으로 바꾸면 계속 사용) |

- 크레딧을 더 받는 활동에 EC2 띄웠다 지우기, RDS 만들기, AWS Budgets 예산 만들기가 들어 있다. 어차피 하는 일이라 같이 받는다.
- **시연 전에 크레딧 잔액을 확인**한다.

## 3. 구성 (C안)

| 서버 | 서브넷 · 사설 IP | 종류 | 설치(직접, systemd) | 공인 IP |
| --- | --- | --- | --- | --- |
| ① 정문 | public-a · `10.1n.1.10` | t4g.micro(1GB) | Nginx(Vue 빌드 정적 파일 + `/api` → ②·③ 라운드로빈), MongoDB 7(WiredTiger 캐시 0.25GB, 인증 켬), Alloy | **탄력적 IP**(주소 고정) |
| ② FastAPI #1 | public-a · `10.1n.1.11` | t4g.micro | Python 3.12 venv + uvicorn `--workers 2`, 이용 완료 배치·크롤러 cron, Alloy | 자동 공인 IP(설치·크롤링 출구용) |
| ③ FastAPI #2 | **public-c** · `10.1n.2.11` | t4g.micro | ②와 같은 코드·설정(cron 없음), Alloy | 자동 공인 IP |
| MariaDB primary | private-db-a | RDS db.t4g.micro, 단일 AZ, 20GB gp2 | 관리형. 파라미터 그룹 `sql_mode` STRICT·`time_zone=Asia/Seoul`·utf8mb4 | 없음(퍼블릭 액세스 끔) |
| MariaDB replica | private-db-c | RDS read replica | **측정하는 날만** | 없음 |
| 모니터링 | — | Grafana Cloud 무료 | 지표 1만 시리즈, 로그 월 50GB, 보관 14일, 사용자 3명 | — |

- 확장안과 같은 주소 규칙이다(`AWS_네트워크_설계.md`). MongoDB만 정문 EC2(`10.1n.1.10`)로 옮겨 `MONGO_URL`이 그 주소를 가리킨다.
- 정문 EC2 메모리가 모자라면(1GB에 Nginx + MongoDB) 스왑 1GB를 켜고, 그래도 부족하면 이 한 대만 t4g.small로 올린다. MongoDB가 멈춰도 이벤트는 `events.log` → Loki에 남고 예약은 성공한다(`AGENTS.md` 도메인 규칙).
- 연결 수 계산은 확장안과 같다: 서버 2대 × 워커 2 × 풀 최대 5 = primary 20개(RDS 한도 약 35~40 안).
- Locust는 노트북에서 정문 탄력적 IP로 보낸다.

### 네트워크와 보안 그룹

- 서브넷 4개: public-a `.1.0/24`(①②), public-c `.2.0/24`(③), private-db-a `.21.0/24`, private-db-c `.22.0/24`(RDS 서브넷 그룹이 AZ 2개를 요구). NAT 게이트웨이 없음.

| 보안 그룹 | 붙는 곳 | 인바운드 |
| --- | --- | --- |
| sg-web | ① | 80 ← 전체(HTTPS는 HTTP로 다 된 뒤 검토, 11-04), 22 ← 내 IP/32 |
| sg-mongo | ① | 27017 ← sg-app |
| sg-app | ②③ | 8000 ← sg-web, 22 ← 내 IP/32 |
| sg-db | RDS | 3306 ← sg-app |

- 모니터링 EC2가 없으니 sg-mon은 만들지 않는다. Alloy는 밖(Grafana Cloud)으로만 보낸다.

### 왜 Docker를 안 쓰나

- 서버가 역할별로 나뉘어 각 서버에 설치할 것이 한두 개라 직접 설치로 충분하다. 수업의 리눅스 운영(apt·systemd·로그)과도 맞다.
- 로컬과 같은 버전은 패키지 버전 고정으로 맞춘다: MongoDB 7.0, Python 3.12 + `environment.yml`의 패키지 버전.
- 설치 순서는 `infra/aws/README.md` 체크리스트에 둔다. 손으로 두 번 이상 하게 되면 설치 스크립트(bash)로 옮긴다.

## 4. 비용 (서울, 크레딧 계정, 대략 — 켜기 전에 요금 계산기와 결제 콘솔에서 다시 확인)

| 항목 | 시간당 | 24시간 한 달 | 작업 시간만(약 170시간) |
| --- | --- | --- | --- |
| EC2 t4g.micro × 3 | 약 $0.0104 × 3 | 약 $23 | 약 $5 |
| 공인 IPv4 × 3(켜져 있을 때) | $0.005 × 3 | 약 $11 | 약 $3 |
| RDS db.t4g.micro | 약 $0.025 | 약 $18 | 약 $4 |
| 저장(RDS 20GB + EBS 8GB × 3) | — | 약 $5 | 약 $5(꺼 둬도 나감) |
| **합계** | | **약 $57** | **약 $17** |
| replica 측정하는 날(4시간 안팎) | | | 약 $0.1~0.5 |

- 꺼 둬도 나가는 것: RDS·EBS 저장공간, **정문 탄력적 IP**(인스턴스가 꺼져 있으면 시간당 $0.005). ②③의 자동 공인 IP는 중지하면 반납돼 요금이 없다.
- RDS는 일시 중지해도 7일 뒤 저절로 다시 켜진다.

## 5. 켜고 끄는 일정

| 때 | AWS에서 하는 일 |
| --- | --- |
| 개발 기간 | 아무것도 켜지 않음. 노트북(compose)으로 개발·테스트 |
| 배포 리허설(하루) | VPC·서브넷·보안 그룹 → RDS(0001·seed 적용, `db/tests/check_ddl.py`로 확인) → EC2 3대 설치 → `/api/health` 두 서버 → 중지 |
| 측정하는 날 | 켜기 → replica 만들기(10~20분) → Locust replica 없음/있음 비교 → **replica 삭제** |
| 시연 날 | 켜기, 끝나면 중지 |
| 프로젝트 끝 | EC2·RDS·스냅샷·탄력적 IP·EBS 삭제, 결제 콘솔에서 남은 요금 0 확인 |

끄는 순서: EC2 3대 중지 → RDS 일시 중지 → (있으면) replica 삭제. 켜는 순서는 반대로 RDS부터.

## 6. 측정할 때 주의

- t4g.micro는 평소 CPU를 vCPU당 10%만 보장한다. 부하 시험 중 `CPUCreditBalance`가 줄어드는지 함께 본다(`인프라_트래픽_안정성_검토.md` 1-1절).
- '서버 1대 끄기' 시험은 ③을 실제로 중지해 본다. 정문(①)은 한 대뿐이라 단일 장애점이고, 이것은 확장안(ALB)에서 다룬다.
- 동시 접속 목표는 `인프라_트래픽_안정성_검토.md` 5절의 1단계(50명)부터 본다.

## 7. 코드·설정에 주는 영향

- 코드 변경 없음. 서버마다 `.env`만 다르다: `DB_WRITE_URL`(RDS 주소), `DB_READ_URL`(평소 비움, 측정하는 날 replica 주소), `MONGO_URL`(`10.1n.1.10`, 인증 포함), `SERVER_NAME`(`api-1`/`api-2`), Grafana Cloud 주소·토큰(Alloy, 비밀값이라 파일에 쓰지 않음).
- 필요한 설정 파일(할 일, 담당은 `STRUCTURE.md` 표대로): Nginx 사이트 설정(`infra/nginx`, B), uvicorn systemd 유닛·배치 cron(`backend/`·`infra/aws`), Alloy 설정(`infra/monitoring`, A).
- 팀 4명은 각자 로컬에서 개발하고, AWS 배포는 한 사람 계정으로 해도 된다. 각자 계정에 올리면 각자 크레딧이 나간다.

## 8. 출처 (2026-11-04 확인)

- [Track your Free Tier usage for Amazon EC2 — AWS 문서](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html): 2025-07-15 전후 무료 인스턴스 종류, 12개월/6개월·크레딧
- [AWS Free Tier](https://aws.amazon.com/free/): 크레딧 $100 + 최대 $100, 무료 플랜 6개월·크레딧 소진 시 종료
- [공인 IPv4 요금 $0.005/시간](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights)
- [Grafana Cloud 요금](https://grafana.com/pricing/): 무료 지표 1만 시리즈, 로그 50GB, 보관 14일, 사용자 3명
- 서울 시간당 단가(t4g.micro 약 $0.0104, RDS db.t4g.micro 약 $0.025)는 공개 요금 기준 어림값이다. 실제 금액은 요금 계산기로 다시 본다.
