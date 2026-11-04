# infra — 배포·운영 설정

| 폴더 | 담당 | 내용 |
| --- | --- | --- |
| `nginx/` | B | 리버스 프록시, FastAPI 2대 upstream, 프론트 정적 파일 |
| `aws/` | 공동 (각자 자기 계정) | VPC·서브넷·보안 그룹·RDS·EC2 체크리스트 |
| `local/` | DB | 로컬 개발용 docker compose (MariaDB, MongoDB) |
| `monitoring/` | A | Alloy → Loki·Prometheus → Grafana (모니터링 EC2, Docker Compose) |

전체 구성은 [시스템 아키텍처 흐름도](../docs/산출물_02_시스템아키텍처_흐름도.md)와 그림 `docs/figures/architecture.png`를 따릅니다. IP 번호 규칙(팀원 n번 = `10.1n`)은 [AWS 네트워크 설계](../docs/AWS_네트워크_설계.md).

```
사용자 ─HTTP(S)─▶ Nginx (public-a, 10.1n.1.10)
                   ├─upstream─▶ FastAPI #1 (10.1n.1.11:8000) ─┬─3306 쓰기·내 것─▶ RDS primary (private-db-a)
                   └─upstream─▶ FastAPI #2 (10.1n.2.11:8000) ─┼─3306 공개 조회──▶ RDS replica (private-db-c)
                                                              └─27017 이벤트────▶ MongoDB EC2 (10.1n.2.21)
모니터링 EC2 (10.1n.1.31): Prometheus 9090 · Loki 3100 · Grafana 3000  ◀─ 각 EC2의 Alloy(로그·exporter)
```

1차는 위 구성 그대로 띄우고(정문 Nginx 설정 보강만), 재 본 뒤 조건을 넘으면 ALB·Auto Scaling 등을 더합니다. 조건표: [`docs/인프라_트래픽_안정성_검토.md`](../docs/인프라_트래픽_안정성_검토.md) 1-1절.

비밀값(DB·MongoDB 비밀번호, JWT 키, 내부 키, 인증서 키)은 이 폴더에 넣지 않습니다.
