# 노진산 PC · 대표 6명 Playwright 준비

2026-11-09 작성, 11-17 결과 반영. 처음에는 서버가 오프라인이라 준비만 했고, 11-09 발표 배포(`https://www.darakcube.kro.kr`)에서 실제로 실행했다. 결과는 맨 아래 '실행 결과'.

## 설계·구현 순서

1. 기존 목업 E2E와 다른 설정·시험 폴더를 사용한다. 기존 74개 시험은 변경하지 않는다.
2. 실제 Markdown 6개를 구조화한 조건과 연결하고 원본 경로·해시를 결과에 남긴다.
3. 기본은 준비/목록 확인이다. 명시적인 실행 옵션이 있을 때만 서버에 접속한다.
4. 읽기는 검색·후보·상세·시간 조회를 확인한다. 예약형 5명도 읽기 단계에서는 회원·결제 흐름을 생략한 부분 시험이다.
5. 쓰기는 별도 모드·합성 키·합성 계정·페르소나별 사전 조건 확인이 필요하다. 예약·취소는 생성한 예약 ID 하나에 한정한다. 후기·회원가입은 이번 범위 밖이다.
6. 순차 1 worker, 재시도 없음, 첫 오류 중단. 재고/조건 부족은 skip으로 표시하고 성공으로 세지 않는다.
7. 서버 오프라인 상태에서는 정책 단위 시험·Playwright 목록 수집·설정 검사만 수행한다.

## 실행 위치

현재 준비된 최신 코드: `C:\Users\jinsa\.codex\worktrees\architecture-ip-update\Pro_1`.
Python이 필요하면 기존 `pro_1` conda 환경을 사용한다. 브라우저 실행에는 이 폴더의 Node/Playwright를 사용한다. 기존 `C:\MLops03\Pro_1`의 다른 작업은 덮어쓰지 않는다.

## 명령

저장소 루트 PowerShell:

```powershell
# 오프라인 준비 확인: 서버 접속 안 함
powershell -NoProfile -ExecutionPolicy Bypass -File frontend/run-personas.ps1

# 서버 온라인 후, 합성 키를 현재 프로세스 E2E_SYNTHETIC_KEY로 전달받아 실행
powershell -NoProfile -ExecutionPolicy Bypass -File frontend/run-personas.ps1 -Run -Headed

# 특정 대표만: study, work, photo, workshop, gathering, browse
powershell -NoProfile -ExecutionPolicy Bypass -File frontend/run-personas.ps1 -Run -Persona study -Headed

# 쓰기: E2E_EMAIL/E2E_PASSWORD에 허용된 합성 계정이 필요
# 해당 페르소나의 시설·일정·외부 조건을 확인한 뒤 E2E_CONFIRMED_PERSONAS에 ID 지정
# 예: study,work. 전체 조건을 확인하지 않고 모두 지정하지 않는다.
powershell -NoProfile -ExecutionPolicy Bypass -File frontend/run-personas.ps1 -Run -Mode write -Persona study -Headed
```

### 도메인으로 6명 동시 실행·화면 녹화 (11-09 추가)

```powershell
# 읽기: 6명이 동시에 https 도메인으로 접속, 사람마다 화면 영상 저장
powershell -NoProfile -ExecutionPolicy Bypass -File frontend/run-personas.ps1 -Run -Gateway https://www.darakcube.kro.kr -Parallel -Record -Headed

# 쓰기(로그인→예약→취소)도 같은 옵션을 붙인다
powershell -NoProfile -ExecutionPolicy Bypass -File frontend/run-personas.ps1 -Run -Mode write -Gateway https://www.darakcube.kro.kr -Parallel -Record
```

- `-Record`: 페르소나마다 `videos/<id>-<모드>.webm`(1280×800)을 남긴다. 화면 오른쪽 아래에 이름표(예: `이도겸 · study · read`)가 보인다. 영상으로 볼 수 있게 동작 사이 400ms를 쉰다(`-SlowMo 0`이면 원래 속도).
- `-Parallel`: 6명을 worker 6개로 동시에 돌린다. 한 명이 실패해도 나머지는 끝까지 진행한다. 없으면 기존처럼 1명씩·첫 오류 중단.
- `-Headed`는 창 6개를 띄워 실시간으로 보는 용도다. 녹화는 `-Headed` 없이도 된다.
- 영상에는 화면이 그대로 찍힌다. 쓰기 모드는 로그인 화면의 이메일이 보이므로(비밀번호는 가려짐) 합성 계정만 쓰고, 영상을 공개 채널에 올리기 전에 확인한다. 영상은 `logs/`에 있어 Git에 올라가지 않는다.

기본 정문 `http://192.168.0.218`. 다른 환경은 `-Gateway`로 변경한다. `-Run` 전까지 네트워크 접속은 하지 않는다. 기본 날짜는 KST 기준 다음 주의 선호 요일이며 과거 날짜를 고정하지 않는다.

결과는 `logs/playwright-personas/<실행번호>/`의 report.html·report.json·test-results에 저장한다. 이메일·비밀번호·토큰·키·응답 본문·trace·스크린샷은 저장하지 않는다. 영상은 `-Record`를 줄 때만 `videos/`에 저장한다. report.html은 브라우저에서 파일을 직접 연다. Playwright 기본 HTML 보고서 대신 입력값·원시 오류를 제외한 요약 보고서를 사용한다. 읽기도 실제 프론트의 이벤트 POST는 발생하므로 합성 키가 필요하다.

실제 서버 시험·예약·취소·이벤트 유실 검증은 아직 하지 않았다. 첫 실행 전 Grafana·합성 키·합성 계정·대상 배포 버전과 예약 가능 재고를 확인한다. 쓰기 실패 시 결과의 남은 예약 ID를 확인하고 수동 취소 여부를 검토한다.

## 준비 검증

- 새 정책 단위 시험 7개 통과, 대표6명 목록 수집 성공.
- 프론트 lint 통과(기존 경고1). 기본 병렬 단위 시험은 기존 ReservePage 1개 시간초과(70통과/1실패); worker1 재실행에서71개 통과, 별도 빌드 성공. 타임아웃·제품 코드는 변경하지 않았다.
- 상세 응답 시설에서 실제 DB 시드 명칭인 인터넷/WIFI·전기·의자/테이블을 확인한다. 반입 안내·모임 확정·상품 도착 같은 정성적 조건과 외부 사정은 실행자 확인 사항이다.
- 날짜는 KST 기준 다음 주의 선호 요일이다. 예약 후 취소는 데이터 정리를 위한 시험 변형이며 실제 페르소나가 항상 취소한다는 의미가 아니다.
- 위 '준비 검증'은 서버 접속 전 확인이다. 실서버 결과는 아래에 따로 적는다.

## 실행 결과 (11-09, 읽기 모드)

- 6명 동시 실행·녹화(`-Parallel -Record`): 6명 모두 조건에 맞는 공간까지 찾음. 지역은 실서버에 공간이 있는 곳으로 옮김(PM 결정, `personas.mjs`의 `sourceSido`·`note`에 원래 지역과 사유). 6분할 영상: `docs/figures/results/playwright_personas_grid.mp4`
- 같은 실행에서 이벤트 전송은 401이었다(입력한 합성 키와 서버 `SYNTHETIC_API_KEY` 불일치). 화면 흐름 결과에는 영향이 없지만, 이 실행의 이벤트는 MongoDB에 쌓이지 않았다.
- 쓰기 모드(로그인 → 예약 → 취소)는 실서버에서 실행하지 않았다.

## 페르소나 500명 읽기 시험

`frontend/e2e-personas/personas500.mjs`가 500명 Markdown에서 유형·지역·인원·검색 전용 여부를 규칙으로 뽑는다(뽑지 못한 값은 유형 폴더 기본값, `inferred`에 표시). 실서버에 없는 시·도는 가까운 서비스 지역(서울·인천·부산·충남·경기)으로 옮긴다. 흐름은 검색 → 첫 후보 상세·시간표 확인이며 예약·가입은 하지 않는다. 공개 조회 API 오류만 실패로 세고 이벤트 전송 결과는 따로 센다.

```powershell
# 목록만(서버 접속 없음)
$env:PERSONA_SET='500'; node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.persona.config.js --list
# 실행: E2E_SYNTHETIC_KEY·E2E_BASE_URL·PERSONA_RUN=1을 설정한 뒤, 동시 브라우저 수는 PERSONA_WORKERS(기본 8)
```

11-09에 8명 시범 실행은 모두 통과했고, 500명 전체 실행은 하지 않았다.
