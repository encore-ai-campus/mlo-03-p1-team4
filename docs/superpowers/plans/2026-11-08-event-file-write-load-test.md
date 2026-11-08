# 이벤트 기록 실패점 재현·용량 확장 계획

**목표:** 계측 보강을 시험 서버에 반영하고, 예약·취소 쓰기 부하에서 이벤트 파일 실패 지점과 자원 한계를 안전하게 확인한다.

**전략:** 공개 GET 용량 시험과 이벤트 기록 신뢰성 쓰기 시험을 분리한다. 11월 8일 GET 500·600·800은 끝났고 HTTP 오류는 0이었으나 800에서 API CPU 목표를 넘었다. 다음 쓰기 시험은 새 계측을 배포해 저부하 데이터 대사부터 확인한 뒤 진행한다. 1000명 GET은 topology·실행기·호스트 예산을 재검토하기 전에는 시작하지 않는다.

**환경:** 현재 작업판 기준 API는 2 vCPU·RAM 1536MiB, Uvicorn 2워커·동시성 200, DB pool 5+5, MariaDB 연결 한도 151이다. VM 3 vCPU 시도는 cores/socket topology 문제로 부팅하지 못해 2 vCPU로 복구됐다. 총 host budget은 16 logical CPU/31.6GiB, VM 배정 10 vCPU/12.75GiB로 기록돼 있다. 다음 topology 검토 전까지 자원 변경은 하지 않는다.

**기준:** [팀 공유 결과](../../부하실험_이벤트기록_팀공유_2026-11-08.md), [11월 7일 쓰기 시나리오](../../쓰기부하_100_200_400_읽기비교_2026-11-07.md), [Locust 실행기](../../../infra/vm/remote109/loadsuite/WRITE_PLAN.md), 이슈 #17, PR #97.

## 전제와 현재 차단 요소

- PR #97은 `develop` 대상이며 현재 코드 CI 통과, 사람 리뷰 대기 상태다. PR 병합 후 최신 `develop`을 배포한다.
- `capacity-public-20261108-082946`은 공개 GET 전용 500/600/800 VU를 오류 0으로 완료했다. 800에서 API 평균 CPU 67%로 50~60% 목표를 못 맞췄고, 별도 3 vCPU 시도는 topology 문제로 실패해 원복됐다. 이 결과를 쓰기 용량 증거로 취급하지 않는다.
- 서버 작업판에 기록된 별도 쓰기 600 VU는 API 예약 응답은 성공했으나 이벤트 파일 append 실패 17건(api1 10·api2 7)으로 대사 불일치가 났다. 코드 배포 후 저부하 대사가 통과하기 전까지 본격 쓰기 부하는 금지한다.
- 현재 Locust `write_high.py`는 100·200·400 VU, 400개 슬롯만 지원한다. `run-capacity.ps1`은 GET 전용이며 최대 800 VU다. 쓰기 500·600·800 계획은 실행기 보강 없이는 불가하다. 현재는 이 쓰기 확장 대신 기존 100·200·400 재현을 우선한다.
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

### 게이트 2 — 저부하 쓰기·이벤트 대사

- [ ] 새 지표와 Prometheus panel이 두 API에 보이는지 확인한 뒤, 합성 계정 1개로 예약 생성·취소 1회 smoke를 실행한다.
- [ ] 5→20→50 VU 저부하 쓰기에서 MariaDB 성공 예약/취소 수, `events.log` 식별자 수, MongoDB 예약 이벤트 수를 run_id와 합성 식별자로 대사한다. 계정·시간 칸은 전용이며 인증값은 보고서에 남기지 않는다.
- [ ] 저부하 누락 0·중복 0, 이벤트 실패 카운터 0, health·replica 정상일 때만 100·200·400 기준 회귀로 이동한다. 대사 불일치나 event failure가 하나라도 발생하면 중단한다.

### 게이트 3 — 쓰기 회귀 기준

- [ ] 실행기를 확장하기 전에 현재 동작하는 100·200·400 VU 경로로 재현 가능한 기존 단계를 확인한다. 기존 지표와 비교할 때 설정·시간 칸 배정·생각 시간·warmup/measure/recovery 값을 고정한다.
- [ ] 단계 순서는 100→200→400. 각 단계 spawn 5 VU/s, 목표 도달 후 warmup 60초·측정 180초·회복 최소 120초, think time 1~5초로 기록한다.
- [ ] 전용 합성 계정 및 겹치지 않는 미래 시간 칸을 사용하고, 준비/로그인/cleanup을 본 측정에서 분리한다.
- [ ] 준비 중 HTTP 오류, 계약 불일치, 계정·슬롯 부족도 실행 실패로 기록하며 부하 단계로 진입하지 않는다.

### 게이트 4 — 읽기 용량 재개

- [ ] GET 500/600/800은 2-vCPU API에서 이미 완료했으므로 그대로 반복하지 않는다. 우선 3 vCPU topology에서 cores/socket이 총 vCPU를 나누도록 VMX/Terraform 계획과 실제 기존 topology를 읽기 전용으로 확인한다.
- [ ] 3 vCPU 또는 다른 배치가 host 16 logical CPU·31.6GiB 예산에 맞고 대상 1대만 in-place 변경하는지 계획에서 검증한다. 부팅실패·대상 외 변경·삭제·host RAM 여유 미달이면 적용하지 않는다.
- [ ] 호스트 자원 범위가 검토되고 변경 승인이 확인된 후에만 API 한 대씩 변경하고 health·Prometheus·HAProxy 복구를 확인한다. 이어서 공개 GET 500→600→800을 60초 warmup·180초 측정·120초 회복으로 실행한다.
- [ ] 목표 50~60% 평균 CPU, p95 ≤ 500ms, 오류 0 및 host budget을 같이 판정한다. 결과 검토 전 1000 VU는 실행하지 않는다. `run-capacity.ps1`의 최대 800 제한도 1000 시험 전에 별도 보강·검증해야 한다.

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
