# local — 로컬 개발 환경 (담당: DB)

AWS 없이 각자 노트북에서 개발하기 위한 docker compose입니다(11-04). Docker Desktop은 사람이 직접 켭니다.

## 처음 한 번

1. `infra/local/.env.example`을 `infra/local/.env`로 복사하고 비밀번호 두 칸을 채웁니다(로컬 전용 값, 다른 서비스 비밀번호를 쓰지 않음).
2. `Pro_1`에서 띄웁니다.

```bash
docker compose -f infra/local/docker-compose.yml up -d
```

3. 처음 띄울 때만 자동으로 들어갑니다: `db/migrations/0001_init.sql`(표 12 + 뷰) → `db/seed/seed.sql`(유형 5·시설 20·지역 230) → `docs/db/mongo_init.js`(컬렉션 3). 빈 테스트 스키마 `spacecube_test`도 같이 만듭니다.
4. `backend/.env`의 `DB_WRITE_URL`을 `mysql+pymysql://app:<MARIADB_PASSWORD>@127.0.0.1:3308/spacecube?charset=utf8mb4`, `MONGO_URL`을 `mongodb://127.0.0.1:27017`로 둡니다. `DB_READ_URL`은 비웁니다(로컬엔 replica 없음).

## 구성

| 서비스 | 이미지 | 포트(이 PC 안에서만) | 용도 |
| --- | --- | --- | --- |
| `mariadb` | `mariadb:11.4` (RDS와 같은 버전) | 3308 | 개발 DB `spacecube`(계정 `app`), 테스트 DB `spacecube_test`. 서버 설정 `sql_mode` STRICT, `time_zone=+09:00`, utf8mb4 |
| `mongodb` | `mongo:7` | 27017 | `user_events`·`event_daily`·`crawl_raw`. 로컬이라 인증 없음 |
| `adminer` (선택) | `adminer:4` | 8080 | `--profile tools`를 붙였을 때만. 브라우저로 표 보기 |

- 포트 3308: 이 PC는 3306을 설치형 MariaDB가, 3307을 Windows 서비스가 씁니다. 다른 PC는 `.env`의 `MARIADB_PORT`로 바꿉니다.
- 백엔드는 compose 밖에서 `uvicorn --reload`로 돌립니다.

## 자주 쓰는 것

| 하려는 것 | 명령 |
| --- | --- |
| 상태 보기 | `docker compose -f infra/local/docker-compose.yml ps` |
| 멈추기(데이터 유지) | `docker compose -f infra/local/docker-compose.yml stop` |
| 처음부터 다시(데이터 지움) | `docker compose -f infra/local/docker-compose.yml down -v` 후 `up -d` |
| 제약 시험(11.4) | `CHECK_DB_URL`을 `mysql+pymysql://app:<비밀번호>@127.0.0.1:3308/spacecube_test`로 주고 `python db/tests/check_ddl.py` |

## 확인한 것 (11-04)

- 두 서비스 모두 healthy, 초기화 3개 파일이 순서대로 실행됨
- MariaDB 11.4.13: 표 12·뷰 1, seed 유형 5·시설 20·지역 230(시·도 16), `sql_mode`·시간대·문자셋 설정대로
- `db/tests/check_ddl.py`를 11.4에서 돌려 29건 통과(동시 결제 포함) — RDS 버전 확인을 대신함
- MongoDB 7: 컬렉션 3, 인덱스 7·2·3

## Docker가 안 켜질 때

지난번 종료 때 남은 소켓 파일 때문에 "rename … .sock … .stale: The file cannot be accessed by the system"이 나면, Docker를 완전히 끄고 `%LOCALAPPDATA%\Docker\run`과 `%LOCALAPPDATA%\docker-secrets-engine` 폴더 이름을 `*.stale-날짜`로 바꾼 뒤 다시 켭니다(파일은 지워지지 않음). 기록: `docs/기록/검증_2026-11-04_DDL실행.md`.
