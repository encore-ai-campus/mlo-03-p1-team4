# PR 검증 기록

2026-11-06, develop d00988b를 별도 검증 폴더로 추출하고 이 PR의 인프라 파일만 적용했다. 원래 작업 폴더의 FE·문서 변경은 포함하지 않았다.

## 통과

- Ruff check / format: 전체 검증 스냅샷 104개 Python 파일 통과.
- PowerShell 실행기 3개 구문 검사, Bash 스크립트 구문 검사 통과.
- Grafana JSON 9개 파싱·패널 ID 중복·24열 범위 검사 통과. 실제 Prometheus 쿼리 58개 정상 응답, 데이터소스 2개 정상 확인은 현 배포에서 수행했다.
- 기존 프론트 예약 회귀 파일 단독 재실행: 2 passed. 별도 Vite build 통과.
- 실제 서버 조회 Playwright smoke 3건, Locust 단계 시험은 RESULTS.md 및 공유 CSV 참조. 이번 PR 작성 중 추가 부하는 실행하지 않았다.
- 알려진 실제 비밀값·개인키 마커의 공개 파일 검사: 일치 0. 원본 HTML·로그·env·state는 제외했다.

## 전체 verify.ps1는 통과하지 못함

- 최초 실행: logs 아래 검증 폴더라 oxlint 대상 제외, 기존 pytest 임시 폴더 권한 문제. 두 환경 원인을 분리했다.
- 재실행: Python 4 failed / 56 passed / 302 errors. 로컬 spacecube_test용 CHECK_DB_URL 미설정으로 DB fixture를 준비하지 못했다. 온라인 업무 DB로 대체하지 않았다.
- 프론트: 66 passed / 1 failed, 기존 ReservePage 회귀의 5초 timeout. 해당 파일 단독 재실행에서는 같은 assertion으로 2개 통과했다. 테스트와 시간 제한을 바꾸지 않았다.
- 따라서 전체 통과로 표시하지 않으며 Draft PR로 리뷰를 요청한다. CI/로컬 테스트 DB 환경에서 전체 검증이 남아 있다.

실행기 verdict.json과 종료 코드는 실패 기준/사후 서비스 점검 실패를 구분 없이 전체 실패로 반환하도록 보완했다. 구문 검사와 별도 코드 리뷰를 수행하며, 이 종료 코드 보완을 위해 실제 부하를 다시 주지는 않았다.

## 공개 전 보완 검증

Terraform 저장 계획 보호 로직 6개 오프라인 사례 통과(전원만 변경 허용, 사양 변경·교체·범위 밖·전원 모드 생성 거부). Bash·PowerShell 구문 및 Ruff 재확인 통과. 실제 합성 키 검사 일치 0. 별도 읽기 전용 코드 리뷰 지적 4건을 보완하고 재검토에서 추가 중요 문제 없음 확인. 이 보완은 실행 중 서버에 적용하지 않았으며 추가 부하도 주지 않았다.

브랜치 생성 시 develop에 330ce48(#68, docs/db/mongo_init_2.js 추가)이 반영돼 해당 커밋을 부모로 보존했다. 위 전체 검증 스냅샷과 실제 배포는 d00988b 기준이며 새 Mongo 초기화 파일 실행·검증은 하지 않았다. 최종 전체 Ruff는 105개 파일 포맷 통과, PowerShell/Bash/계획 정책 검증은 별도 보완 파일 기준이다.
