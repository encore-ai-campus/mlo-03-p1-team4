# 읽기 부하 단계 시험 — 2026-11-06

## 실행 방법

```powershell
./infra/vm/remote109/run-capacity.ps1 -Stages @(50,100,200,400) -Seconds 60
```

- 대상: http://192.168.0.218, 배포 기준 develop d00988b.
- 실행 위치: 사용자 PC의 conda pro_1. SSH playdata는 사전·사후 서비스 검사와 보호된 합성 키 로딩에 사용한다.
- GET 유형·검색·상세·시간 칸. 사용자 대기 1~3초. 새 실행기는 10초 내 목표 도달하도록 증가율을 max(5, ceil(사용자/10))으로 설정한다. DB 쓰기 없음.
- 단계 통과 기준: 요청 실패율 1% 이하 및 전체 p95 500ms 이하. 초과하면 상승 중단한다. 이번 예비 시험 기준이며 정식 SLA가 아니다.
- 결과: logs/locust-capacity-시간/summary.csv, before-*.json, after.json, cpu-*.json, memory-*.json, 실행 stdout/stderr.
- HTTP 원본 통계·HTML: summary.csv의 report 열이 가리키는 logs/remote109-시간/.
- DB exporter 설치 전이므로 DB CPU·잠금·복제·디스크 지표는 수집하지 않는다. HTTP 조회는 실제 DB를 사용한다.

## 해석 제한

60초에는 사용자 증가 시간이 포함되고 워밍업 제외 없음. 제한된 데이터 18개와 첫 검색 결과 중심 시나리오다.
사용자 수는 동시 요청 수가 아니다. 실제 달성 RPS를 함께 본다.
최고 통과 단계는 이번 조건의 확인된 수준이며 시스템 절대 최대 처리량이 아니다.
같은 호스트의 네 VM, 클라이언트 네트워크·자원과 짧은 시험 변동이 포함된다.
합성 키·원본 인증 파일·state는 보고서에 넣지 않는다.

## 실행기 수정 이력

첫 50명 시험 자체는 완료됐으나 Windows PowerShell이 Locust 정상 stderr를 NativeCommandError로 처리해 상위 요약이 중단됐다.
실행기를 숨김 Start-Process와 stdout/stderr 분리 저장으로 수정했다. 완료한 HTTP 통계는 보존했다.

## 최종 결과 (KST 16:22~16:33)

| 실제 도달 사용자 | 요청 | 실패 | RPS | p95 ms | 보고서 폴더 |
|---|---:|---:|---:|---:|---|
| 5 | 141 | 0 | 2.42 | 130 | remote109-20261106-162213 |
| 20 | 555 | 0 | 9.52 | 100 | remote109-20261106-162326 |
| 50 | 1307 | 0 | 21.96 | 260 | remote109-20261106-162505 |
| 100 | 2415 | 0 | 40.63 | 98 | remote109-20261106-162633 |
| 200 | 3822 | 0 | 64.42 | 150 | remote109-20261106-162746 |
| 400 | 8522 | 576 | 143.71 | 550 | remote109-20261106-163121 |

**최고 통과: 200명, 약 64.42 RPS. 400명은 실패율 약 6.76%, p95 550ms로 기준 초과.**
400명은 history CSV에서 실제 최대 400명을 확인했다. 처리량 143.71 RPS는 실패 응답도 포함하므로 성공 처리 용량이 아니다.
초당 5명 증가로 실행했던 최초 목표 400·800명 결과는 목표 미도달이므로 제외했다. 올바른 재시험은 400명에서 중단했고 800명은 실행하지 않았다.
400명 재시험은 10초 램프업(40명/초). 5~200명은 기존 5명/초여서 단계 간 램프 조건이 다르다. 장시간 일정 부하 재검증 전까지 절대 최대치로 사용하지 않는다.

## 오류와 회복
400명 단계에서 HTTP 503 발생. 직후 api1에만 분산되는 상태를 감지했으나 추가 부하 없이 재검사에서 api1/api2 6:6, 대상 15개 UP, nginx 2/2, 공간 18개 조회로 복구 확인.
DB exporter 미설치 상태이므로 DB 병목·복제 지연 원인은 확인하지 않았다.

## 자동화 원본
`run-capacity.ps1`: 단계별 실행, SSH 전후 서비스 검사, CSV 요약, CPU·메모리 query_range 저장, 기준 초과 시 중단.
`run-experiments.ps1`: 합성 키를 보호된 SSH 경로로 읽어 Locust 실행, HTML·CSV 저장.
새 실행기에는 stats_history의 실제 최대 사용자 수를 확인하는 조건도 추가했다.

## 상세 기록 경로
- logs/locust-capacity-20261106-162631: 100명
- logs/locust-capacity-20261106-162745: 200명 및 무효인 최초 400명 (400명 부분 제외)
- logs/locust-capacity-20261106-163119: 유효한 400명, CPU·메모리·오류 로그
- logs/remote109-20261106-163121/locust.html: 유효한 400명 HTML 보고서


## 503 원인 후속 확인

- 실제 systemd ExecStart: uvicorn 2워커, --limit-concurrency 100, keep-alive 5초.
- api1 journal에 16:31~16:32 `WARNING: Exceeded concurrency limit.` 확인. 앱 미들웨어에 들어가기 전에 Uvicorn이 503을 반환할 수 있다.
- 16:31:47 HAProxy api1 DOWN: /health 503, 1ms.
- 16:32:17 api2 DOWN: /health 503, 4ms.
- 16:32:18 api1 DOWN, active 서버 0, backend apps has no server available.
- 16:32:25 api2 UP: /health 200, 86ms. 부하 종료 후 분산 정상 재확인.
- 결론: 확인된 503 원인은 Uvicorn 동시성 제한과 헬스체크 공유에 따른 백엔드 제외의 연쇄다. DB 서버 장애·최대 처리량으로 해석하지 않는다.
- 100은 워커의 연결/작업 제한이므로 앱 전체의 사용자 수 100을 의미하지 않는다. CPU가 남아도 이 제한에서 거절될 수 있다.
- 근거 로그: logs/locust-capacity-20261106-163119/503-cause.log.
- 설정 변경·추가 부하는 하지 않았다. 제한 상향 전 DB 풀·지연·스레드풀 수용량을 검토하고, readiness와 부하 차단을 분리하는 방안을 검토해야 한다.

## 동시성 200 재시험 결론 (16:49~16:54 KST)

- 이전 100 제한의 서비스 journal 경고 건수 api1 270건·api2 66건을 재확인하고, 두 앱의 limit-concurrency만 200으로 변경했다. 워커 2개·VM·DB 풀·프록시는 유지했다. 원본 서비스 파일은 각 VM의 /etc/systemd/system/spacecube.service.pre-limit200에 백업했다.
- 이전 실패 400명의 세 단계 전인 50명부터 50→100→200→400으로 재시험. 목표 인원 전부 도달. 기준 초과로 800명은 미실행.
- 최고 통과 200명: 5162건, 실패 0, 86.94 RPS, p95 430ms.
- 400명: 7360건, 실패 155(약 2.11%), 124.02 RPS(실패 포함), p95 940ms, p99 21000ms. 실패 155건은 HTTP 503.
- 16:53:04부터 api1 Uvicorn journal에 Exceeded concurrency limit, 같은 시각 HAProxy api1 DOWN(/health 503, 1ms), 16:53:25 UP(200, 101ms) 확인. api2에 대해서는 같은 시간대 concurrency 경고 검색 결과가 없었다.
- 400명 VM 관측 최고: api1 CPU 55.8%·메모리 40.3%, api2 CPU 57.2%·메모리 39.0%. 아래 resources.csv와 원본 JSON은 다른 서버의 평균·최고·시각도 포함한다. CPU는 1분 rate를 15초 간격으로 수집한 값으로 순간 최고가 아니다.
- 종료 후 health 200 degraded(mongo 제외), api1/api2 6:6, 대상 15개 UP, nginx 2/2, 공간 18개 조회 확인.
- 동시성만 높여도 400명에서 제한·헬스 제외가 재발했다. DB 병목 여부는 미확인. 이전 시험과 램프업·시점·재시작·네트워크 조건이 달라 단순 개선율이나 절대 한계로 해석하지 않는다. FastAPI 제한은 200으로 유지, 추가 변경 없음.
- 상세 결과: logs/locust-capacity-20261106-164912/RESULTS.md, resources.csv, cpu-400.json, memory-400.json, summary.csv, after.json.
- HTTP 원본: logs/remote109-20261106-165225/locust.html 및 locust_failures.csv.

## 두 앱 편중 비교 기록

이전 Uvicorn 경고는 api1 270건/api2 66건(277건 아님), 제한 200 재시험은 8건/0건이다. 경고 건수는 요청 분배 비율이나 실제 처리 부하 비율이 아니다. 제한 200의 400명 시험 CPU 평균은 api1 45.8%/api2 47.6%로 비슷했다. 특정 워커 연결·DB 대기 편중은 가설이며 미확인이다.
Grafana HAProxy 대시보드에 서버별 기간 요청·분산 비율·5xx·세션·응답·헬스 전환·동시성 경고와 근거 로그를 추가했다. HAProxy 세션은 Uvicorn 워커 연결 수가 아니다. 워커별 연결·실행 작업·DB 풀 대기는 아직 미수집으로 표시한다.
추가 DB 요청은 DB-MONITORING-REQUEST.md를 참고한다. 설정 증설 없이 현재 제한·연결·잠금·원본별 연결 상태부터 확인한다.
