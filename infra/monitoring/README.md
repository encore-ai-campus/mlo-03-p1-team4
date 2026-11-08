# monitoring — 로그·지표·대시보드 (담당: A)

> **현재 실험 배포(2026-11-08):** 109의 7 VM 구성에서 Prometheus는 exporter·FastAPI `/metrics`를 직접 pull 합니다. Alloy는 로그를 Loki로 보내고, Prometheus가 Alloy 자체 `/metrics`를 scrape 합니다. 아래 AWS·Docker Compose 흐름은 초기 참고안이며 현재 배포 경로가 아닙니다.

초기 AWS 참고안은 Monitoring EC2(public-a, 10.1n.1.31, t4g.small) 한 대에 Docker Compose로 Prometheus·Loki·Grafana를 띄우는 구성입니다. 현재 실험 서버와 구분해서 읽어 주세요. 기준 문서: [산출물_02 4-3](../../docs/산출물_02_시스템아키텍처_흐름도.md), [DB 명세 9절](../../docs/산출물_04_DB명세서.md).

## 흐름

```
FastAPI app.log·events.log, Nginx 접근 로그 ─▶ Alloy (각 VM) ─▶ Loki ──────────┐
FastAPI /metrics, mysqld·node·HAProxy·Nginx exporter ─▶ Prometheus pull ───────┼─▶ Grafana
Alloy 자체 /metrics ────────────────────────────────▶ Prometheus pull ─────────┤
MongoDB events·event_daily (분석) ─────────────────────────────────────────────┘
```

## 파일 (예정)

| 파일 | 내용 |
| --- | --- |
| `docker-compose.yml` | Prometheus · Loki · Grafana |
| `alloy.config` | 현재 배포에서는 로그 파일 → Loki. exporter 지표 수집 경로는 109 모니터링의 Prometheus pull 설정에서 관리 |
| `grafana/dashboards/*.json` | 서비스 상태 · 예약 경쟁 · 사용자 흐름 |

## 대시보드 (초안)

| 패널 | 데이터 | 보는 것 |
| --- | --- | --- |
| 서버별 요청 수·오류율·p95 | Prometheus `http_requests_total`, `http_request_duration_seconds` | 라운드로빈, replica 있음·없음 비교 |
| 예약 성공·충돌·취소 | Prometheus `reservation_total{result}` | 409가 정상적으로 막히는지 |
| 복제 지연 | mysqld exporter | replica가 얼마나 늦는지 |
| 이벤트 유실·읽기 대체 | `event_file_write_failures_total{stage,reason}`, `event_file_lock_wait_seconds{scope}`, `event_file_write_duration_seconds`, `mongo_event_write_failures_total`, `db_read_fallback_total` | 파일 실패 단계·원인·잠금별 대기·MongoDB·replica 장애 |
| 오류 로그 | Loki `{job="api", level="error"}` | 원인 찾기 |
| 사용자 흐름 | MongoDB `user_events` / Loki `{job="events"}` | 검색 → 상세 → 칸 → 예약 단계별 이탈 |

## 할 일

- [ ] 원격 저장소(Mimir 등) 도입 시 Alloy scrape + remote_write 구조를 별도 검토. 원시 Prometheus receiver를 pull 대체로 쓰지 말고, target 중복·receiver 접근제어·시계열 저장량을 먼저 측정
- [ ] Grafana·exporter용 DB 계정(`exporter`)은 DB 담당에게 요청
