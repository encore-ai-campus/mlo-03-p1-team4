# infra — 배포·운영 설정

| 폴더 | 담당 | 내용 |
| --- | --- | --- |
| `nginx/` | B | 리버스 프록시, FastAPI 2대 upstream, 프론트 정적 파일 |
| `vm/` | 공동 (VM은 노트북 주인) | **1차 배포**: 노트북 4대 · VM 7대 설치 체크리스트 (11-05) |
| `aws/` | 공동 (각자 자기 계정) | VPC·서브넷·보안 그룹·RDS·EC2 체크리스트 (참고안) |
| `local/` | DB | 로컬 개발용 docker compose (MariaDB, MongoDB) |
| `monitoring/` | A | Alloy → Loki·Prometheus → Grafana (모니터링 VM `mon`, apt·systemd) |

전체 구성은 [시스템 아키텍처 흐름도](../docs/산출물_02_시스템아키텍처_흐름도.md)와 그림 `docs/figures/architecture.png`, 배치·주소는 [로컬 VM 구성](../docs/로컬_VM_구성.md)을 따릅니다(11-05).

현재 109 시험망은 192.168.219.x다. 브라우저·Locust는 gw .218:80으로 접근하고, HAProxy가 api1 .214/api2 .215의 Nginx :80으로 분산한다. 각 Nginx는 화면 파일과 로컬 FastAPI :8000을 맡는다. 쓰기·인증·내 조회는 db1 .212:3306, 공개 조회는 db2 .213:3306, 이벤트는 로그 파일과 mongo .216:27017을 사용한다. mon .217은 Prometheus :9090·Loki :3100·Grafana :3000이며 DB node/mysqld exporter 포함 19 targets를 확인했다. [실제 IP·사양·DB 제한](../docs/DB_운영_모니터링_현황_2026-11-07.md)을 기준으로 한다.

현재 시험은 HAProxy 정문과 Nginx/API 2대를 사용하며, 재 본 뒤 조건을 넘으면 ALB·Auto Scaling 등을 더합니다. 조건표: [`docs/인프라_트래픽_안정성_검토.md`](../docs/인프라_트래픽_안정성_검토.md) 1-1절.

비밀값(DB·MongoDB 비밀번호, JWT 키, 내부 키, 인증서 키)은 이 폴더에 넣지 않습니다.
