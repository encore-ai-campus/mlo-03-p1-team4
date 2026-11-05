# infra — 배포·운영 설정

| 폴더 | 담당 | 내용 |
| --- | --- | --- |
| `nginx/` | B | 리버스 프록시, FastAPI 2대 upstream, 프론트 정적 파일 |
| `vm/` | 공동 (VM은 노트북 주인) | **1차 배포**: 노트북 4대 · VM 7대 설치 체크리스트 (11-05) |
| `aws/` | 공동 (각자 자기 계정) | VPC·서브넷·보안 그룹·RDS·EC2 체크리스트 (참고안) |
| `local/` | DB | 로컬 개발용 docker compose (MariaDB, MongoDB) |
| `monitoring/` | A | Alloy → Loki·Prometheus → Grafana (모니터링 VM `mon`, apt·systemd) |

전체 구성은 [시스템 아키텍처 흐름도](../docs/산출물_02_시스템아키텍처_흐름도.md)와 그림 `docs/figures/architecture.png`, 배치·주소는 [로컬 VM 구성](../docs/로컬_VM_구성.md)을 따릅니다(11-05).

```
노트북 4 브라우저·Locust ─HTTP 80─▶ gw Nginx (노트북 1, 192.168.0.11)
            ├─upstream─▶ api1 FastAPI #1 (노트북 2, .21:8000) ─┬─3306 쓰기·내 것─▶ db1 MariaDB primary (노트북 1, .12)
            └─upstream─▶ api2 FastAPI #2 (노트북 3, .31:8000) ─┼─3306 공개 조회──▶ db2 MariaDB replica (노트북 3, .32)
                                                               └─27017 이벤트────▶ mongo MongoDB (노트북 1, .13)
mon (노트북 2, .22): Prometheus 9090 · Loki 3100 · Grafana 3000  ◀─ 모든 VM의 Alloy(로그·exporter)
```

1차는 위 구성 그대로 띄우고(정문 Nginx 설정 보강만), 재 본 뒤 조건을 넘으면 ALB·Auto Scaling 등을 더합니다. 조건표: [`docs/인프라_트래픽_안정성_검토.md`](../docs/인프라_트래픽_안정성_검토.md) 1-1절.

비밀값(DB·MongoDB 비밀번호, JWT 키, 내부 키, 인증서 키)은 이 폴더에 넣지 않습니다.
