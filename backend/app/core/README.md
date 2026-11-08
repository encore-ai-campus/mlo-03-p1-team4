# core — 공통 모듈 (담당: A)

B가 1일차부터 쓰므로 A가 가장 먼저 만듭니다. 바꿀 때는 B에게 먼저 알립니다. 자세한 형태: [백엔드_A 3절](../../../docs/백엔드_A_회원_후기_이벤트.md).

| 파일 (예정) | 제공하는 것 | 쓰는 쪽 |
| --- | --- | --- |
| `config.py` | `.env` 설정값 (pydantic-settings, `backend/.env.example`의 키) | 전체 |
| `db.py` | SQLAlchemy 엔진 2개(PyMySQL, `pool_pre_ping`, 세션 시간대 +09:00), `get_db_write()` primary 세션, `get_db_read()` replica 세션(실패하면 primary + 경고 + `db_read_fallback_total`) | 전체 |
| `mongo.py` | pymongo 클라이언트(앱에 하나, 시간 제한 1초), `space_rental_analytics.events` 컬렉션 (인덱스는 만들지 않음) | A |
| `event_document.py` | 새 15종 이벤트 문서 조립·상품 조건·개인정보 제한 | A |
| `security.py` | bcrypt 해시·검증, JWT 발급·해석 | A |
| `deps.py` | `get_current_user()` → `CurrentUser(user_id)`(primary), `get_optional_user()`, `require_internal_key()` | A, B |
| `errors.py` | `AppError(code, message, status, detail=None)`와 예외 처리기 (Pydantic 오류도 `VALIDATION`으로) | 전체 |
| `pagination.py` | `?page=&size=`(size 최대 50), `{"items","page","size","total"}` | 전체 |
| `events.py` | `log_event(session_id, user_id, event_type, venue_id=None, category=None, payload=None, is_synthetic=False, *, products=None)`: `events.log`에 바로 한 줄, MongoDB는 내부 스레드 풀(2개, 대기열 1,000건) | A, B, 배치 |
| `metrics.py` | `/metrics`, `reservation_counter`(`reservation_total{result}`), `event_file_write_failures_total{stage,reason}`, `event_file_lock_wait_seconds{scope}`, `event_file_write_duration_seconds`, `mongo_event_write_failures_total`, `db_read_fallback_total` | A, B |
| `logging.py` | `app.log`·`events.log` (JSON 한 줄), 파일 잠금 timeout 원인 구분 | 전체 |
| `clock.py` | `get_today()`, `get_now()`(시간대 없는 한국 시각), `override_business_time()`(백필 서비스 시각 한정), `get_event_time()`(실제 적재 시각). `SERVER_NAME=generator`는 생성 프로세스 환경에만 지정하고 공용 `.env`는 바꾸지 않음 | 전체·생성기 |
| `synthetic.py` | `is_synthetic_request(request)` (헤더 `X-Synthetic: 1` + `X-Synthetic-Key`(= `.env` `SYNTHETIC_API_KEY`), 키 틀리면 401) | 전체 |

## 오류 코드

전체 목록·사용자 문구·`detail` 모양·프론트 동작은 [`docs/오류코드.md`](../../../docs/오류코드.md) 한 곳에만 둡니다. `errors.py`는 그 표의 코드만 씁니다. FastAPI 기본 오류(422·404·405·500)도 예외 처리기에서 같은 형식(`VALIDATION`·`NOT_FOUND`·`METHOD_NOT_ALLOWED`·`INTERNAL_ERROR`)으로 바꿉니다.
