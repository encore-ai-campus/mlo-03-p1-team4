# backend — FastAPI (담당: FastAPI A·B)

두 사람의 코드가 한 저장소, 한 앱(`app.main:app`)으로 합쳐집니다. 배포할 때는 이 앱을 VM 두 대(`api1`·`api2`, 노트북 2·3)에 똑같이 띄웁니다. 서버 두 대와 개발 파트 두 개는 서로 관계없습니다.

## 이슈 #1 작업 상태

공통 core와 실행에 필요한 A 회원·후기·이벤트 코드를 포함합니다. DB 연결마다 한국 시간대와 STRICT 모드를 설정하고, 가상 데이터 요청에는 `SYNTHETIC_API_KEY`를 확인합니다. `backend/tests/run_auth_tests.ps1`에서 공통 계약·이벤트·회원 테스트 53개가 로컬 MariaDB `spacecube_test`로 통과했습니다. 인증된 `POST /auth/logout`은 204를 반환합니다. 무상태 Bearer JWT라 서버 폐기 목록은 없고, 로그아웃 시 프론트가 저장한 토큰을 지워야 합니다. 비밀번호 변경 후 기존 토큰도 만료까지 유효합니다. 탈퇴는 B의 `reservation_repo.count_cancellable()`이 시작 전 예약을 확인해, 예약이 있으면 409를 반환하고 없으면 개인정보를 익명화합니다. 문서상 이벤트 형식은 `docs/백엔드_A_회원_후기_이벤트.md` 계약(서버 생성 `event_id`)에 맞췄습니다. `reason`·`result` 등 허용된 자유 문자열에 이름이나 토큰이 들어갈 가능성은 남아 있어 팀 합의가 필요합니다. B 예약 소유권 조회 연결 전에는 후기 기능 일부가 503입니다.

| 파트 | 맡는 기능 | 기준 문서 |
| --- | --- | --- |
| A | 공통 core(두 DB 연결·MongoDB·오류·페이지·`get_today`·`/metrics`·헬스체크), 회원·인증, 후기, 이벤트 | [백엔드_A](../docs/백엔드_A_회원_후기_이벤트.md) |
| B | 유형·지역·시설, 공간 검색·상세·칸, 예약+모의 결제·취소, 이용 완료 배치(F-35), 크롤링 등록 `/internal/venues` | [백엔드_B](../docs/백엔드_B_공간_예약_결제_크롤링.md) |

## 계층

F-61 `POST /internal/venues`는 크롤러·생성기에서 `X-Internal-Key`로 호출합니다.
`INTERNAL_API_KEY`와 primary `DB_WRITE_URL`, 기존 0001·seed가 필요합니다.
같은 `(source_site, source_id)`의 신규는 201, 재전송·갱신은 200이며 응답은
최상위 `venue_id`·`ignored_facilities`입니다. 공간·시설·그림을 한 트랜잭션에 저장합니다.
api1 호출 주소·검증 명령은 B 명세 7절과 `tests/README.md`를 따릅니다.

```
routers   →   services   →   repositories   →   MariaDB primary / replica
(HTTP 입출력)  (업무 규칙·트랜잭션)  (SQL)
                    └─ core.events.log_event() → events.log(→ Loki) + MongoDB user_events
```

- 라우터는 요청을 검증하고 서비스를 부를 뿐, SQL을 쓰지 않습니다.
- 트랜잭션(BEGIN~COMMIT)은 서비스에서 엽니다. 예약·결제 한 번이 대표 예입니다.
- 다른 파트의 표가 필요하면 그 파트의 repository 함수를 부릅니다. 직접 SQL을 쓰지 않습니다.
- 쓰기·인증·'내 것'은 primary(`get_db_write`), 공개 조회는 replica(`get_db_read`). 표는 [AGENTS.md](AGENTS.md).

## 폴더

| 폴더 | 내용 |
| --- | --- |
| `app/` | 앱 본체 (`main.py`, `core/`, `models/`, `routers/`, `schemas/`, `services/`, `repositories/`, `jobs/`) |
| `scripts/` | [A] 운영 스크립트 (`replay_events.py`: `events.log` → MongoDB 다시 넣기, `check_local_test_db.py`: 로컬 DB 세션 확인) |
| `tests/` | [A·B] pytest, 동시성 테스트 |
| `.env.example` | 설정 키 이름 (값 없음) |

## 실행 (예정)

```bash
conda run -n pro_1 --no-capture-output uvicorn app.main:app --reload --port 8000
```

- `.env.example`을 `.env`로 복사해 값을 채웁니다. `.env`는 저장소에 올리지 않습니다.
- 로컬에서는 `DB_READ_URL`을 비워 두면 primary 하나로 돕니다.
- 실제 앱 연결의 시간대·SQL 모드는 `backend` 폴더에서 `conda run -n pro_1 --no-capture-output python -m scripts.check_local_test_db`로 확인할 수 있습니다. 이 스크립트는 로컬 `spacecube_test` 외의 DB를 거부합니다.

## 회원·공통 계약 테스트

프로젝트 루트가 `C:\mlo-03-p1-team4`인 경우 PowerShell에서 실행합니다. 스크립트는 실행 위치와 무관하게 자기 파일 위치에서 백엔드 폴더를 찾고, 테스트용 로컬 DB 설정을 읽습니다.

```powershell
cd C:\mlo-03-p1-team4\backend
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\run_auth_tests.ps1
```

회원 테스트는 `CHECK_DB_URL`로 지정한 MariaDB `spacecube_test`에만 연결하며 테스트 데이터는 트랜잭션 롤백으로 정리합니다. 팀 DB 주소는 사용하지 않습니다.

## Swagger에서 직접 회원 흐름 확인

1. 로컬 테스트용 DB 주소만 `backend/.env`의 `DB_WRITE_URL`에 설정하고 `DB_READ_URL`은 비워 둡니다. `.env`는 Git에 올리지 않습니다.
2. `backend` 폴더에서 `conda activate pro_1` 후 `uvicorn app.main:app --host 127.0.0.1 --port 8001`을 실행합니다.
3. 브라우저에서 `http://127.0.0.1:8001/docs`를 열고 `POST /auth/signup`으로 테스트 회원을 만듭니다. 실명·실제 전화번호 대신 가짜 정보를 쓰세요. 날짜 예시는 `000101`, 성별 숫자는 `3`입니다.
4. `POST /auth/login`을 먼저 실행해 200 응답과 `access_token`을 확인합니다. Swagger 오른쪽 위 **Authorize**를 누르고 안내된 HTTPBearer 입력칸에 토큰 값만 붙여 넣은 뒤 **Authorize → Close**를 누릅니다. `Bearer ` 글자는 입력하지 않습니다.
5. `GET /users/me`에서 본인 정보가 반환되는지 확인합니다.
6. `POST /auth/logout`도 같은 토큰으로 실행하면 204를 반환합니다. 호출 뒤 Swagger의 **Authorize → Logout**으로 토큰을 지우세요. 로그아웃 호출 자체는 서버에서 토큰을 폐기하지 않으므로 복사된 토큰은 최대 60분 동안 유효합니다.
7. 탈퇴 API는 예약 연동 전 503이 정상 동작입니다.

Swagger가 만든 curl에 `-H 'Authorization: Bearer …'`가 없으면 Authorize가 적용되지 않은 상태입니다. 이때 `/users/me`와 `/auth/logout`의 401은 정상 응답입니다. 로그인 응답이 200인지, Authorize 입력 후 **Authorized**로 표시되는지 먼저 확인하세요. 직접 curl을 쓸 때는 `-H "Authorization: Bearer <로그인 응답의 access_token>"` 헤더를 추가해야 합니다.

Swagger에서 생성한 회원은 테스트 DB에 남습니다. 자동 pytest는 매 테스트 트랜잭션을 롤백합니다.

## 정할 것

- [x] ORM·드라이버(11-03): SQLAlchemy 2.1 동기 + PyMySQL, MongoDB는 pymongo, 마이그레이션은 SQL 파일. 규칙은 [AGENTS.md](AGENTS.md) 'DB 접근 규칙'
- [x] 토큰(11-03): 액세스 토큰만, JWT 60분, Bearer 헤더, 리프레시 없음
- [x] 실행 환경: conda `pro_1` 하나(루트 `AGENTS.md`, `environment.yml`). FastAPI 패키지도 `environment.yml`에 더한다. 서버(EC2)용 `requirements.txt`는 배포 때 뽑는다.
