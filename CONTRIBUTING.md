# 팀 방조 GitHub 규칙

다락큐브 저장소에서 같이 일하는 규칙입니다. 처음 한 번 읽고, 헷갈리면 다시 봅니다. AI 에이전트(Codex·Claude Code)도 이 규칙을 따릅니다(`AGENTS.md`).

## 1. 한 바퀴 = 이슈 하나

```text
이슈 확인(또는 만들기) → develop에서 브랜치 → 구현 → 검증(verify.ps1) → 커밋·푸시 → develop으로 PR → 리뷰 1명 → 머지 → 이슈 닫힘
```

| 브랜치 | 역할 | 누가 바꾸나 |
| --- | --- | --- |
| `main` | 발표·제출용 안정 버전. **직접 푸시·직접 PR 금지** | 마일스톤이 끝날 때 `develop` → `main` PR 하나로만 |
| `develop` | 날마다 합치는 곳(통합 브랜치). 모든 작업 PR은 여기로 | 리뷰 1명 받은 PR만 |
| `feat/…`·`fix/…`·`docs/…`·`chore/…` | 각자 작업 브랜치. `develop`에서 만들고 `develop`으로 PR | 본인 |

- 일은 **이슈**로 시작합니다. 이슈에는 파트 라벨과 그날 **마일스톤**을 붙이고, 맡은 사람을 지정합니다.
- 하루 묶음은 마일스톤입니다: `11-05 통합`, `11-06 피드백·검토`, `11-07 피드백 반영`, `11-08 발표 준비`, `11-09 발표`.
- 하다가 막히면 이슈에 `blocked` 라벨과 이유 한 줄을 남기고 팀 채널에 알립니다.

### Project 보드 ([팀 방조 · 다락큐브 1차](https://github.com/orgs/encore-ai-campus/projects/5))

이슈를 한 화면에서 보는 판입니다. 이슈·마일스톤은 그대로 쓰고, **진행 상태만 보드에서 옮깁니다.**

| 상태 | 언제 옮기나 |
| --- | --- |
| 할 일 | 처음 상태 |
| 하는 중 | 브랜치를 만들고 작업을 시작할 때 |
| 리뷰 | PR을 올렸을 때 |
| 막힘 | 다른 파트·결정을 기다릴 때(`blocked` 라벨도 같이) |
| 끝 | PR이 머지돼 이슈가 닫히면 |

- 보기: **전체 표**(모든 이슈), **보드**(상태 칸), **내 일**(나에게 배정된 것만), **목 11-05 통합**(그날 마일스톤만). 날마다 쓰는 보기는 필터의 마일스톤만 바꿉니다.
- 필드: 상태, 파트(FE·A·B·DB·공동), 담당, 마일스톤, 라벨, 연결된 PR.
- 이슈 템플릿으로 만든 이슈는 보드에 자동으로 들어갑니다. 빈 이슈로 만들었다면 이슈 오른쪽 'Projects'에서 넣습니다.
- AI 에이전트·터미널에서 보기:

```bash
gh project item-list 5 --owner encore-ai-campus --format json
```

```bash
gh issue list --repo encore-ai-campus/mlo-03-p1-team4 --milestone "11-05 통합"
```

## 2. 브랜치

| 종류 | 이름 | 예 |
| --- | --- | --- |
| 기능 | `feat/<파트>-<F-ID 또는 짧은 이름>` | `feat/B-F-30-reservation`, `feat/A-core` |
| 버그 | `fix/<파트>-<짧은 이름>` | `fix/FE-slot-409` |
| 문서 | `docs/<짧은 이름>` | `docs/readme-results` |
| 설정·인프라 | `chore/<짧은 이름>` | `chore/nginx-conf` |

- 파트: `FE`, `A`, `B`, `DB`, `공동`(브랜치 이름에는 `common`).
- 작업 브랜치는 **`develop`에서** 만듭니다: `git switch develop` → `git pull` → `git switch -c feat/FE-...`
- **`main`과 `develop`에 바로 푸시하지 않습니다.** 모든 변경은 PR로 들어갑니다. PR의 base는 **`develop`**입니다(GitHub 화면 기본값이 `main`이면 바꿔서 올림).
- 브랜치는 오래 두지 않습니다. 하루 안에 PR을 올리고, 머지되면 지웁니다.
- 충돌이 나면 내 브랜치에서 `git merge origin/develop`으로 합쳐 해결한 뒤 올립니다.

## 3. 커밋 메시지

```text
[파트] F-ID 요약
```

- 예: `[B] F-30 예약·결제 트랜잭션`, `[FE] F-50 후기 작성 창 오류 표시`, `[DB] seed 지역 별칭 추가`, `[공동] README 수행결과`
- 한국어로 씁니다. 한 커밋에는 한 가지 일만 담습니다.
- `.env`, 비밀번호, 토큰, 크롤링 원본(`crawler/data/`)은 절대 커밋하지 않습니다(`.gitignore`에 있음).

## 4. PR

- 제목은 커밋 메시지 규칙과 같게 씁니다. 본문은 템플릿(`.github/pull_request_template.md`)을 채웁니다.
- 본문에 **`Closes #이슈번호`**를 적어 머지할 때 이슈가 같이 닫히게 합니다.
- 리뷰어는 **1명 이상**입니다. 담당 폴더의 리뷰어는 `CODEOWNERS`가 자동으로 지정합니다.
- 올리기 전에 검증을 돌리고 결과를 PR에 적습니다.

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1
```

- DB를 건드렸으면 `db/tests/check_ddl.py`, 화면 흐름을 바꿨으면 `verify.ps1 -E2E`도 돌립니다.
- GitHub Actions(CI)가 아래 4-1절 검사를 다시 돌립니다. **CI가 빨간색이면 머지하지 않습니다.**
- 작업 PR → `develop` 머지는 **Squash and merge**(PR 하나 = 커밋 하나), `develop` → `main`은 **Merge commit**(그날 묶음이 한 번에 보이게)으로 합니다.
- `develop` → `main`은 마일스톤이 끝날 때(예: 11-05 통합 점검 통과 뒤, 11-08 발표 버전) 전원이 확인하고 올립니다.

### 4-1. CI (GitHub Actions, `.github/workflows/ci.yml`)

PR(`develop`·`main` 대상)을 올리거나 고칠 때마다, 그리고 `develop`·`main`에 머지될 때마다 돕니다. 워크플로 파일은 브랜치마다 따로 있어서 `develop`에 먼저 들어가고, 마일스톤 끝에 `develop` → `main`으로 같이 올라갑니다.

| 검사 | 언제 | 하는 일 | 로컬에서 같은 것 |
| --- | --- | --- | --- |
| Ruff | 항상 | 파이썬 린트·포맷(`ruff.toml`) | `verify.ps1` |
| 프론트 verify | `frontend/`가 바뀌었을 때 | 린트·단위 테스트·빌드 | `npm run verify` |
| 프론트 E2E | `frontend/`가 바뀌었을 때 | Playwright(Chromium) 데스크톱·폰, 목업 데이터. 실패하면 trace를 Artifacts에 올림 | `npm run test:e2e` |
| DB·백엔드 테스트 | `backend/`·`db/`·`docs/db/`·`infra/local/`·`environment.yml`이 바뀌었을 때 | `infra/local` compose로 MariaDB 11.4·MongoDB 7을 띄워 ① STRICT·시간대·seed 수 ② `check_ddl.py`(제약 29건 + 동시 결제) ③ `check_mongo_init.js` ④ 테스트 파일이 있으면 `spacecube_test`에 0001 + seed를 넣고 pytest | `check_ddl.py`, `verify.ps1` |
| CI 결과 | 항상 | 위 결과를 모아 하나라도 실패하면 실패 | — |

- `develop`·`main`에 머지될 때는 바뀐 곳과 상관없이 전부 돕니다. `workflow_dispatch`로 Actions 탭에서 손으로 돌릴 수도 있습니다.
- 건너뛴 검사는 '성공'으로 표시됩니다. 브랜치 보호를 켤 수 있게 되면 **'CI 결과' 하나만 필수 검사**로 지정하면 됩니다(관리자 권한 필요).
- 백엔드 설정 키(`backend/.env.example`)가 바뀌면 `ci.yml`의 pytest 환경 변수도 같이 고칩니다. CI의 DB 비밀번호는 CI 안에서만 쓰고 버리는 값입니다.
- 빨간색이면 Actions 탭에서 실패한 단계를 열어 보고, 로컬에서 같은 명령으로 재현해 고친 뒤 다시 푸시합니다.

### 리뷰할 때 보는 것

- 기준 문서(`docs/백엔드_A·B`, `오류코드.md`, `산출물_04`)와 경로·응답·오류 코드·이벤트 이름이 같은가
- `AGENTS.md`의 '바꾸면 안 되는 도메인 규칙'·'큰 버그를 막는 규칙'을 어기지 않았나(읽기 경로, 한 트랜잭션, 1062 → 409 등)
- 다른 파트 파일을 고쳤다면 그 파트 사람이 리뷰했나
- 비밀값·개인정보가 코드·로그에 없나

## 5. 이슈

- **기능** 템플릿: 무엇을, 기능 ID, 완료 조건(테스트 포함), 기준 문서
- **버그** 템플릿: 재현 순서, 기대 결과, 실제 결과, 화면·로그(비밀값 가림)
- 라벨

| 묶음 | 라벨 |
| --- | --- |
| 파트 | `FE`, `A`, `B`, `DB`, `공동` |
| 종류 | `feature`, `bug`, `docs`, `test`, `infra` |
| 상태 | `blocked`(막힘), `review-needed`(같이 봐야 함) |
| 우선순위 | `P0`(발표에 꼭 필요), `P1`(있으면 좋음) |

## 6. AI 에이전트로 작업할 때

- 저장소 루트(`Pro_1`)에서 실행합니다. 에이전트는 루트 `AGENTS.md`와 작업 폴더의 `AGENTS.md`를 먼저 읽습니다.
- 한 번에 이슈 하나, 담당 폴더만 고칩니다. 다른 파트 파일이 필요하면 멈추고 사람에게 알립니다.
- 검증이 **같은 원인으로 2번 실패하면** 더 고치지 않고 멈춘 뒤, 실패 명령·오류·추정 원인을 이슈 댓글이나 `STATE.md` 열린 질문에 남깁니다([산출물 05](docs/산출물_05_구현_운영_계획.md) 1-4절).
- AI가 만든 코드도 사람이 리뷰한 뒤 머지합니다.

## 7. 처음 받을 때

```bash
git clone https://github.com/encore-ai-campus/mlo-03-p1-team4.git
```

이후 순서는 [README](README.md) 8절과 [infra/local](infra/local/README.md)을 봅니다(conda 환경, 로컬 DB compose, 프론트 실행).
