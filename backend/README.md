# backend — FastAPI (담당: FastAPI A·B)

두 사람의 코드가 한 저장소, 한 앱(`app.main:app`)으로 합쳐집니다. 배포할 때는 이 앱을 EC2 두 대(FastAPI #1, #2)에 똑같이 띄웁니다. 서버 두 대와 개발 파트 두 개는 서로 관계없습니다.

| 파트 | 맡는 기능 | 기준 문서 |
| --- | --- | --- |
| A | 공통 core(두 DB 연결·MongoDB·오류·페이지·`get_today`·`/metrics`·헬스체크), 회원·인증, 후기, 이벤트 | [백엔드_A](../docs/백엔드_A_회원_후기_이벤트.md) |
| B | 유형·지역·시설, 공간 검색·상세·칸, 예약+모의 결제·취소, 이용 완료 배치, 크롤링 등록 `/internal/venues` | [백엔드_B](../docs/백엔드_B_공간_예약_결제_크롤링.md) |

## 계층

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
| `scripts/` | [A] 운영 스크립트 (`replay_events.py`: `events.log` → MongoDB 다시 넣기) |
| `tests/` | [A·B] pytest, 동시성 테스트 |
| `.env.example` | 설정 키 이름 (값 없음) |

## 실행 (예정)

```bash
conda run -n pro_1 --no-capture-output uvicorn app.main:app --reload --port 8000
```

- `.env.example`을 `.env`로 복사해 값을 채웁니다. `.env`는 저장소에 올리지 않습니다.
- 로컬에서는 `DB_READ_URL`을 비워 두면 primary 하나로 돕니다.

## 정할 것

- [x] ORM·드라이버(11-03): SQLAlchemy 2.1 동기 + PyMySQL, MongoDB는 pymongo, 마이그레이션은 SQL 파일. 규칙은 [AGENTS.md](AGENTS.md) 'DB 접근 규칙'
- [x] 토큰(11-03): 액세스 토큰만, JWT 60분, Bearer 헤더, 리프레시 없음
- [x] 실행 환경: conda `pro_1` 하나(루트 `AGENTS.md`, `environment.yml`). FastAPI 패키지도 `environment.yml`에 더한다. 서버(EC2)용 `requirements.txt`는 배포 때 뽑는다.
