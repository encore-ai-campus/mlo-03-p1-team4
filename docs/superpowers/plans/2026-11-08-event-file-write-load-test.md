# 이벤트 기록 실패점 재현·용량 확장 계획

**목표:** 계측 보강을 시험 서버에 반영하고, 예약·취소 쓰기 부하에서 이벤트 파일 실패 지점과 자원 한계를 안전하게 확인한다.

**전략:** 먼저 기존 100·200·400 쓰기 조건으로 변경 전 기록과 비교 가능한 회귀 시험을 한다. 깨끗하게 통과한 뒤 별도 실행에서 500·600·800명으로 확장한다. 각 단계에서 API/이벤트 오류가 발생하면 즉시 증량을 멈추며, 1000명은 앞 단계 자료를 검토한 후 별도 승인된 후속 단계로 둔다.

**환경:** Locust 2.47.0, FastAPI 2워커·동시성 200, DB pool 5+5, MariaDB 연결 한도 151. 현재 값을 실제 서버에서 재확인하고, 검증 단계에서는 앱·DB·VM 설정을 바꾸지 않는다.

**기준:** [팀 공유 결과](../../부하실험_이벤트기록_팀공유_2026-11-08.md), [11월 7일 쓰기 시나리오](../../쓰기부하_100_200_400_읽기비교_2026-11-07.md), [Locust 실행기](../../../infra/vm/remote109/loadsuite/WRITE_PLAN.md), 이슈 #17, PR #97.

## 전제와 현재 차단 요소

- PR #97은 `develop` 대상이며 현재 코드 CI 통과, 사람 리뷰 대기 상태다. PR 병합 후 최신 `develop`을 배포한다.
- 현재 Locust `write_high.py`는 100·200·400 VU, 400개 슬롯만 지원한다. `run-capacity.ps1`은 GET 전용이며 최대 800 VU라 쓰기 500·600·800 시험에 그대로 쓸 수 없다. 쓰기 fixture/슬롯과 stage 목록을 지원하는 실행기 보강 및 검증이 선행되어야 한다.
- 시험 전에 SSH host key 지문을 확인하고 서버 작업판·잠금으로 타 팀/Claude 작업과 격리한다. `StrictHostKeyChecking`을 끄거나 알 수 없는 host key를 자동 수락하지 않는다.
- VM 7대 자원과 한 물리 호스트의 총 vCPU·RAM·스토리지 사용량을 읽기 전용으로 측정한다. 물리 호스트 여유가 확인되기 전에는 vCPU·RAM·디스크를 증설하지 않는다.
- MariaDB 연결 한도, VM 사양, Uvicorn·Nginx·HAProxy 값은 회귀 시험에서 고정한다. 이 계획은 부하 시험 중 성능 튜닝 계획이 아니다.

## 설계와 관측 단위

| 범위 | 기록 |
|---|---|
| 부하 발생기 | 실제 VU 도달 수, spawn·측정 구간, Locust request/transaction JSONL, RPS·상태코드·p50/p95/p99, CPU·RAM |
| 진입점 | HAProxy backend별 요청·5xx·health transition·분산 비율, Nginx upstream status/latency |
| FastAPI 앱별 | `.214`·`.215` 요청량·5xx·p95, Uvicorn 동시성 경고, `event_file_write_failures_total{stage,reason}`, thread/process 잠금 대기 histogram, 파일 쓰기 전체 시간 histogram |
| 이벤트 정합성 | MariaDB 성공 예약·취소 집계와 MongoDB 서버 이벤트 집계 비교, Mongo writer 오류 카운터, fallback 시도/성공 여부. SQL 원문·계정·개인정보는 수집하지 않음 |
| DB·VM | 앱별 DB connections/Sleep/Query·대기·잠금, max_connections 사용 비율, replica 지연, VM별 CPU·MemAvailable·swap·disk free·I/O/iowait, 물리 호스트 자원 |
| 회복 구간 | 각 단계 뒤 최소 120초 동안 health, HAProxy 6:6, Prometheus targets, DB 복제·연결, CPU/RAM 회복을 기록 |

CPU 50~60%는 용량 최적화 목표로 기록하되 단독 합격 조건으로 쓰지 않는다. 현재 CPU 지표는 1분 rate 표본이므로 순간 피크와 호스트 경합을 별도 수집한다.

## 실행 순서

### 게이트 0 — 병합·원격 접속

- [ ] PR #97의 사람 리뷰 1건과 필수 CI를 확인하고 `develop` 병합 여부를 확인한다.
- [ ] SSH host key fingerprint를 팀에서 확인하고 접속한다. 서버 공유작업판·운영 설정 지문·현재 실행 SHA를 수집한다.
- [ ] API·Prometheus·Grafana·DB가 정상이고 다른 작업이 없는지 확인한다.

### 게이트 1 — 배포·계측 스모크

- [ ] 기존 런타임 설정·파일 hash·Git SHA·systemd 상태·Grafana 설정을 백업한다.
- [ ] 최신 `develop`을 api1 한 대에 배포하고 health·로그·`/metrics`·새 metric series를 확인한다.
- [ ] 문제가 없으면 api2에 동일 버전을 순차 배포하고 HAProxy 6:6·전체 targets 정상 여부를 확인한다.
- [ ] Grafana에서 실패 건수·잠금 대기·전체 기록시간 panel이 두 API에 대해 값 또는 명시적 0으로 보이는지 확인한다.
- [ ] 합성 계정 1개로 예약 생성→취소 smoke를 실행하고 MariaDB·MongoDB 집계가 맞는지 확인한다. smoke 외에는 쓰기 부하를 주지 않는다.

### 게이트 2 — 쓰기 회귀 기준

- [ ] 실행기를 확장하기 전에 현재 동작하는 100·200·400 VU 경로로 재현 가능한 기존 단계들을 확인한다. 기존 지표와 비교할 때 설정·시간 칸 배정·생각 시간·warmup/measure/recovery 값을 고정한다.
- [ ] 단계 순서는 100→200→400. 각 단계 spawn 5 VU/s, 목표 도달 후 warmup 60초·측정 180초·회복 최소 120초, think time 1~5초로 기록한다.
- [ ] 전용 합성 계정 및 겹치지 않는 미래 시간 칸을 사용하고, 준비/로그인/cleanup을 본 측정에서 분리한다.
- [ ] 준비 중 HTTP 오류, 계약 불일치, 계정·슬롯 부족도 실행 실패로 기록하며 부하 단계로 진입하지 않는다.

### 게이트 3 — 용량 확장

- [ ] 게이트 2가 모두 깨끗하면 별도 run에서 500→600→800 VU를 진행한다. 현재 `write_high.py`의 400 계정·슬롯 한도를 먼저 확장하고 500/600/800 단계 fixture 단위 테스트를 작성한다.
- [ ] 각 단계는 목표 달성·워밍업 60초·측정 180초·회복 120초를 유지한다. 누적 데이터·실제 VU·RPS·실행 시간을 보존한다.
- [ ] 800명 통과 후 결과·자원·호스트 총량을 사람이 검토하기 전까지 1000명 단계는 시작하지 않는다.
- [ ] vCPU 증설은 모든 VM의 CPU와 물리 호스트 총량을 함께 분석한 뒤 한 서버씩, 한 번에 한 설정만 변경하는 별도 비교로 한다.

## 통과·중단 기준

다음 단계로 이동하려면 목표 VU 도달, unexpected API/Locust transaction error 0, 5xx·network failure 0, p95 ≤ 500ms, event file failure 0, Mongo writer error 0, 예약·취소 합계 정합, backend health·replica 정상, 120초 회복 확인을 모두 만족해야 한다.

아래 중 하나라도 발생하면 현재 단계를 중단하고 회복 구간만 수행한다. 다음 VU로 증량하지 않는다.

- 4xx/5xx/네트워크 오류 중 시나리오가 예상하지 않은 응답, transaction/contract/fixture 오류
- `event_file_write_failures_total` 또는 `mongo_event_write_failures_total` 증가
- FastAPI health 불량, HAProxy backend DOWN/UP 전환, Prometheus scrape 결손
- p95 500ms 초과, API/VM CPU 85% 이상이 1분 지속, MemAvailable 10% 미만 또는 swap-in/out 지속, 디스크 여유 급감·I/O 대기 상승
- DB 연결 사용량이 max_connections의 80%에 도달, 복제 지연 상승 또는 잠금 대기 발생
- 서버 작업판 변경·다른 부하와 중첩·설정 지문 변경

오류 시 해당 단계의 로그·메트릭 구간과 서버·호스트 자원만 보존하고, 계정 정리는 본 합성 계정의 소유 예약을 API로 취소한다. DB 대량 삭제, MariaDB 연결 한도 변경, 자동 retry로 실패를 숨기는 행위는 하지 않는다.

## 보고 항목

각 run에 브랜치·SHA·서버 배포 SHA, 설정 지문, 테스트망·VM/호스트 사양, 단계별 실제 VU·RPS·HTTP/transaction 오류·latency percentiles, 이벤트 실패 stage/reason, Mongo fallback 결과, DB 연결/복제, VM·호스트 CPU/RAM/disk/I/O, 중단 지점, cleanup 집계를 기록한다. 인증정보·SQL 원문·사용자 개인정보는 기록하지 않는다.
