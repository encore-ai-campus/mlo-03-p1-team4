# 109 서버 운영 스크립트 (11-07 PM·Claude 자체 작업분)

109 실습 서버(`ssh playdata`, 219망 VM 7대)에 로컬 브랜치를 올리고, 종단 점검·PR #91 검증을 하면서 쓴 스크립트다.
부하 시나리오 자체는 `../loadsuite/`(Locust 실행기)에 있고, 이 폴더는 **배포·점검·설정 실험** 쪽이다.

> 공통 규칙: 서버 공용 작업판 `~/spacecube109/SERVER_WORK_BOARD.md`를 먼저 보고, 변경·부하 작업은
> `~/spacecube109/.server-operation.lock`을 잡은 뒤 실행한다. 비밀값(.env·합성 키)은 파일에 쓰지 않고 환경변수로만 넘긴다.

## 파일

| 파일 | 하는 일 | 실행 위치 |
|---|---|---|
| `deploy-rolling.sh` | 저장소를 api2 → api1 한 대씩 배포. 한 대가 `/health` ok가 돼야 다음으로 넘어감. 잠금 자동 선점·해제 | 로컬(Git Bash) |
| `deploy-apps.sh` | api1·api2 동시 배포 + Nginx 설정·타이머 반영(초기 버전) | 로컬 |
| `deploy-fe.sh` | 프론트 빌드만 `/var/www/spacecube`에 교체(서비스 재시작 없음) | 로컬 |
| `nginx.conf` | #67 keepalive 16/4초·request_id·상류 지연 로그가 들어간 api용 Nginx 설정 | 배포 스크립트가 사용 |
| `timers.snippet.sh` | api1 정기 실행: 이용 완료 배치 매시 :05, `event_daily` 집계 매시 :20, 크롤러 월 04:00 | install-role에 삽입 |
| `e2e_api.py` | 정문 경유 API 종단 점검 33항목(가입→검색→예약·결제→중복·동시 예약→취소→후기→이벤트→탈퇴) | 로컬 |
| `health_app.py` | PR #91의 독립 헬스 앱(8001) | `verify-step2-health.sh`가 사용 |
| `verify-step2-health.sh apply\|rollback` | PR #91 2단계: api1·api2에 독립 헬스 서비스 + Nginx `/health`·`/api/health` 분리 | playdata |
| `verify-step3-haproxy.sh apply\|rollback` | PR #91 3단계: gw HAProxy 서버별 `maxconn 50`, `timeout queue 5s` | playdata |
| `collect-specs.sh` | VM 7대 사양·디스크·HAProxy/Nginx/Uvicorn/DB 풀/MariaDB/Mongo 설정 읽기 전용 수집 | playdata |

## 사용 예

```bash
# 배포 (저장소 루트를 WT로, 기본은 이 스크립트가 들어 있는 저장소)
bash infra/vm/remote109/ops/deploy-rolling.sh

# 종단 점검 (합성 키는 환경변수로만)
SYNTHETIC_API_KEY=... E2E_BASE=http://192.168.219.218/api python infra/vm/remote109/ops/e2e_api.py

# PR #91 검증 단계 적용/원복 (playdata에 스크립트 복사 후)
bash verify-step2-health.sh apply      # 원복: rollback (백업 *.bak-verify006)
bash verify-step3-haproxy.sh apply
```

## 부하 시나리오 요약 (Locust, `../loadsuite/`)

상세 계약은 `docs/Locust_읽기_쓰기_상세시나리오.md`. 부하 발생기는 109와 분리된 PC(Windows, `pro_1` Python, Locust 2.47)이고 정문은 `192.168.219.218`.

| 실행기 | 시나리오 | 단계 |
|---|---|---|
| `read_high.py` | 공개 읽기 10종(목록·상세·신규·시설·후기·빈 칸 등), 생각 시간 1~5초. 계정·쓰기 없음 | 100 → 200 → 400명 |
| `write_high.py` | VU마다 전용 합성 계정 + 겹치지 않는 미래 시간 칸. 예약 201 → 내역 → 취소·환불 200 → 내역 반복 | 100 → 200 → 400명 |

- 공통 프로토콜: spawn 5명/초, 목표 도달 뒤 예열 60초 · 측정 180초 · 회복 120초. 오류가 하나라도 나면 다음 단계로 가지 않음.
- 실행: `PYTHONUTF8=1 python write_high.py` (로그는 `logs/<run_id>/`).
- 시험 뒤 수집: `collect_evidence.py`(Prometheus 구간 지표) → `collect_server_evidence.py --label after`(Nginx 로그·설정 지문) → `collect_app_logs.py`(앱·HAProxy 로그) → `collect_write_audit.py`(DB 정합성) → `summarize_write.py --read-report ...`(저장소 루트에서).
- 정리: 자기 합성 계정의 남은 confirmed 예약만 API로 취소. DB 대량 삭제 없음.

## 지금까지 결과 (자세한 표는 docs)

- `docs/읽기부하_100_200_400_검토_2026-11-07.md`, `docs/쓰기부하_100_200_400_읽기비교_2026-11-07.md`: 풀 3+2 기준선.
- `docs/DB풀_5+5_읽기쓰기_재시험결과_2026-11-07.md`: 풀 5+5에서 쓰기 400명 첫 통과(예약 p95 286ms, 오류 0).
- `docs/PR91_헬스분리_HAProxy_검증_2026-11-07.md`: PR #91 1~3단계 비교(작성 예정·이 PR에 추가).
