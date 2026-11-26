# 노진산 PC 시험 준비 · 2026-11-09

## 확인 결과

- 팀 배치 정문: http://192.168.0.218 (Host 뒤에 /api를 붙이지 않음).
- MongoDB: 192.168.0.211. 노진산 PC에서 DB에 직접 연결하지 않음.
- Grafana: http://192.168.0.217:3000. 이번 확인에서 TCP 연결 거절. 모니터링 서비스·방화벽 담당 확인 후 부하 실행.
- 정문 80 포트 연결 성공. 이는 실제 API 기능·배포 버전 검증을 뜻하지 않음.
- 로컬 Node 24.22.0, npm 11.19.1, pro_1 Locust 2.47.0(고정 버전 일치).
- Locust 일일 시나리오 회귀 32개 통과. 첫 시도는 임시 logs 상위 폴더 누락으로 31통과/1설정오류, 폴더 생성 후 32통과. 기존 gevent 경고 1건.
- 기존 로컬 프론트에서 Playwright --list 성공: 74개(데스크톱·모바일, 실제 실행 아님). Chromium 설치 폴더 존재. 해당 로컬 폴더의 다른 작업 변경은 유지.

## PR 상태와 실행 범위

- #110: 페르소나 문서 500명 병합 완료. 예약형409·검색전용91, 파일 수·상대 링크 확인. 문서를 실행하는 Playwright 어댑터는 없음.
- 기존 Locust daily_locustfile.py는 Student/Worker/Gathering/Explorer 네 클래스로 실행. 500개 Markdown을 자동 실행하지 않음.
- 기존 frontend/e2e는 study@example.com 목업 계정·고정 날짜·공간 이름에 의존. E2E_BASE_URL만 실제 주소로 바꿔 전체 실행하면 신뢰할 수 없음.
- #109 통합 크롤링/공간 보충, #108 중복, #96 Draft 백필, #91 health, #90 monitoring은 각각 별도 PR이며 페르소나 문서 머지만으로 완료되지 않음.

## Locust 읽기 준비 명령

최신 develop을 받은 체크아웃에서 PowerShell로 실행. 합성 키는 보호된 경로로 전달받아 현재 프로세스의 SYNTHETIC_API_KEY에 설정하고 Git·문서·결과에 기록하지 않는다. 날짜는 시험 당일과 다음날로 계산한다.

```powershell
Set-Location C:\MLops03\Pro_1
$dates = (Get-Date -Format yyyy-MM-dd) + ',' + (Get-Date).AddDays(1).ToString('yyyy-MM-dd')
powershell -NoProfile -ExecutionPolicy Bypass -File simulator/locust/run_daily.ps1 -Profile Explorer -Mode ReadOnly -Dates $dates -Users 1 -Duration 1m -Gateway http://192.168.0.218
```

출력 REPORT 경로의 CSV·HTML·daily-runs.jsonl을 보관. 읽기 1명 smoke → 읽기5명 → 쓰기1명 순으로 검토하며 이 준비 작업에서는 실부하를 실행하지 않았다. 쓰기는 별도 합성 계정 파일 LOCUST_ACCOUNTS_FILE과 날짜·취소/정리 계획이 필요. 일일 실행기는 프로필별 사용자 상한이 있어 고부하600명 시험에 사용하지 않는다.

## Playwright 준비와 다음 구현

현재 목업 회귀만 확인하려면 frontend에서 E2E_BASE_URL을 비운 상태로 npm run test:e2e를 사용한다. 실제 시험은 별도 spec으로 준비한다.

1. 여섯 유형에서 대표 1명씩 선택(500개 브라우저를 동시에 켜지 않음).
2. 공통 흐름을 구조화: 유형·지역·예산·인원·실제 날짜·이용시간·검색 종료/예약/취소/후기 기대 결과.
3. 실서버에서 유효한 공간·빈 시간·합성 계정을 준비하고 SYNTHETIC 헤더를 설정. 로그인 입력·토큰은 trace/영상/결과 공유에서 제외 또는 비식별화.
4. 검색전용 1명 → 예약/취소 1명 → 완료된 예약 후기 1명. 실서버 후기 자격은 completed 조건으로 준비.
5. 화면 결과와 API 상태, 이벤트 ID별 파일/Mongo 수집을 대조. 그 뒤 2~5개 브라우저로 확대하고 필요 시 Locust 읽기 부하와 병행.

운영 설정·VM 자원·DB 제한은 이 준비 작업에서 변경하지 않는다. Grafana 복구와 실제 API·키·합성 계정 확인 전에는 대량 쓰기 시험을 시작하지 않는다.
