# monitoring — 로그·지표·대시보드 (담당: A)

모니터링 EC2(public-a, 10.1n.1.31, t4g.small) 한 대에 Docker Compose로 Prometheus·Loki·Grafana를 띄우고, 각 EC2의 Grafana Alloy가 로그와 exporter 지표를 보냅니다. 기준: [산출물_02 4-3](../../docs/산출물_02_시스템아키텍처_흐름도.md), [DB 명세 9절](../../docs/산출물_04_DB명세서.md).

## 흐름

```
FastAPI app.log·events.log, Nginx 접근 로그 ─▶ Alloy (각 EC2) ─▶ Loki (14일) ─┐
FastAPI /metrics, mysqld·mongodb·node·nginx exporter ─▶ Prometheus (15일) ───┼─▶ Grafana
MongoDB user_events·event_daily (분석, 1년) ───────────────────────────────┘
```

## 파일 (예정)

| 파일 | 내용 |
| --- | --- |
| `docker-compose.yml` | Prometheus · Loki · Grafana |
| `alloy.config` | 로그 파일 → Loki, 로컬 exporter·`/metrics` → Prometheus |
| `grafana/dashboards/*.json` | 서비스 상태 · 예약 경쟁 · 사용자 흐름 |

## 대시보드 (초안)

| 패널 | 데이터 | 보는 것 |
| --- | --- | --- |
| 서버별 요청 수·오류율·p95 | Prometheus `http_requests_total`, `http_request_duration_seconds` | 라운드로빈, replica 있음·없음 비교 |
| 예약 성공·충돌·취소 | Prometheus `reservation_total{result}` | 409가 정상적으로 막히는지 |
| 복제 지연 | mysqld exporter | replica가 얼마나 늦는지 |
| 이벤트 유실·읽기 대체 | `mongo_event_write_failures_total`, `db_read_fallback_total` | MongoDB·replica 장애 |
| 오류 로그 | Loki `{job="api", level="error"}` | 원인 찾기 |
| 사용자 흐름 | MongoDB `user_events` / Loki `{job="events"}` | 검색 → 상세 → 칸 → 예약 단계별 이탈 |

## 할 일

- [ ] 모니터링 EC2(월 약 $20) / 노트북 Docker 중 선택 — 노트북이면 Alloy가 밖으로 밀어 보내야 하고 끄면 기록이 끊김
- [ ] Grafana·exporter용 DB 계정(`exporter`)은 DB 담당에게 요청
