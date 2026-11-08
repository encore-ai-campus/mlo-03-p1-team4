# 109 시스템 배포·실험 결과 — 2026-11-06

## 배포

- 실행 호스트: `ssh playdata`, Windows 32GB RAM + WSL2 Ubuntu 24.04.
- 저장소: 109 `/home/playdata/spacecube109/source`, develop `9b9b223d1f48199560dd1191971a4d6edf11326c`.
- 추가 수정: HTTP IP 접속의 세션 UUID 생성 대체 경로. GitHub에는 아직 반영하지 않은 로컬 수정이다.
- 새 VM: gw `.218`(1c/768MB), api1 `.214`·api2 `.215`(각 1c/1536MB), mon `.217`(2c/3072MB), 전부 브리지·20GB sparse 디스크.
- `.211`은 다른 장비의 응답이 확인돼 사용하지 않았다. 기존 DB는 `.212`·`.213`, MongoDB는 제외했다.
- 이 PC에서 만들었던 시험 VM 4대와 기반 VM은 사용자 요청으로 삭제했다. 원본 OVA·코드·스크립트는 유지했다.
- 서비스: HAProxy → 서버별 Nginx → FastAPI 2워커, Grafana/Prometheus/Loki/Alloy, node exporter 4개·nginx exporter 2개.

## 검증

| 항목 | 결과 |
| --- | --- |
| 스킬·제어 환경 | vmware-wsl-lab 4675414 설치, preflight exit 0 |
| Terraform | 경로 문제 복구 후 새 VM 4대 부팅, 기존 VM 삭제 0 |
| Ansible SSH | 4/4 pong |
| Ansible 동일 설정 재실행 | 4대 모두 changed=0, unreachable=0, failed=0 |
| DB 연결 | primary·replica 헬스 및 조회 API 200, 공간 목록 total=18 |
| 실제 헬스 | 200 degraded, mongo=down; MongoDB 제외에 따른 예상 상태 |
| 분산 | 12회 요청 api1 6회 / api2 6회 |
| Prometheus | 현재 대상 15개 UP, nginx_up 2/2 |
| Loki | gw/api1/api2/mon 서버 라벨 확인 |
| 프론트 verify | 린트 오류 0, 기존 경고 1, 단위 63개·빌드 통과 |
| 목업 E2E | 67 passed / 7 skipped. 시험 preview 종료 대기 수동 정리 포함 |
| 실제 API Playwright | 3 passed (1.4초) |

## Locust — 이 PC에서 읽기 전용

| 사용자 / 시간 | 요청 | 실패 | 전체 p95 | 전체 평균 |
| --- | --- | --- | --- | --- |
| 5명 / 30초 | 71 | 0 | 약 200ms | 약 61ms |
| 50명 / 60초 | 1,355 | 0 | 약 120ms | 약 53ms |

50명 시 유형 조회 268건, 공간 검색 684건, 상세 262건, 시간 칸 141건. 전체 약 22.75요청/초.
검색 p95 약 130ms, 상세 약 120ms, 시간 칸 약 89ms. Locust percentile은 근사값이다.

보고서 원본(이 PC, Git 제외):

- `C:\MLops03\Pro_1\logs\remote109-20261106-150244\` — 실제 Playwright 3건 + 5명 시험.
- `C:\MLops03\Pro_1\logs\remote109-20261106-150609\` — 50명 시험 CSV·HTML.
- 109 `~/spacecube109/reports/services.json` — 서비스·수집 상태.
- 109 `~/spacecube109/ansible-*.log`, `terraform-create.log` — 실행 이력. 원문은 외부에 그대로 공유하지 않는다.

## 한계와 후속

- 이 PC는 Wi-Fi, 109는 유선이다. 짧은 예비 읽기 시험이며 A7의 10분·워밍업 제외·유선 기준 합격 판정이 아니다.
- 회원가입·예약·결제·취소·같은 칸 50명 경쟁·DB 복제 지연·DB 쓰기 부하는 실행하지 않았다.
- 새 VM 4대가 같은 물리 호스트에 있어 호스트 장애 대응은 검증하지 못했다. Windows 무로그온 재부팅 시험도 하지 않았다.
- FastAPI `/metrics`는 현재 스크랩된 워커 기준이며 2워커 전체를 합친 지표가 아니다. 전체 요청·성능 판단에는 HAProxy와 Locust를 함께 사용한다.
- 기존 DB 이미지 값 일부가 `art:` 계약과 다르다. DB 데이터·스키마는 수정하지 않았다.
- 기존 npm 의존성 moderate 취약점 11건을 보고받았으며 자동 버전 변경은 하지 않았다.
- 외부 공유 초안은 `UPSTREAM-ISSUE-DRAFT.md`. 아직 GitHub에 게시하지 않았다.
