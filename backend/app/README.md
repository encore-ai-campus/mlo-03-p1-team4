# app — FastAPI 앱 본체

| 위치 | 담당 | 내용 |
| --- | --- | --- |
| `main.py` (예정) | A | 앱 생성, 라우터 등록, CORS, 예외 처리기, 요청 로그 미들웨어, 시작·종료 때 연결 관리 |
| `core/` | A | 설정, primary·replica 세션, MongoDB, 보안, 오류·페이지, 이벤트, 지표, 로그, 오늘 날짜 |
| `models/` | A·B | SQLAlchemy 모델 (DDL과 같게, 표 담당 파트가 만듦) |
| `routers/` | A·B | 엔드포인트 |
| `schemas/` | A·B | 요청·응답 모델 |
| `services/` | A·B | 업무 규칙, 트랜잭션 |
| `repositories/` | A·B | SQL 접근 |
| `jobs/` | B | 주기 실행 배치 (이용 완료) |

## 라우터 등록

`main.py`는 A가 만들고, B는 자기 라우터를 한 줄씩 추가합니다. 경로 앞에 `/api`를 붙이지 않습니다(Nginx·Vite가 떼고 넘김).

```python
app.include_router(health.router, tags=["health"])                        # A  GET /health
app.include_router(auth.router, prefix="/auth", tags=["auth"])            # A
app.include_router(users.router, prefix="/users", tags=["users"])         # A
app.include_router(reviews.router, tags=["reviews"])                      # A  /reservations/{id}/review, /reviews, /venues/{id}/reviews
app.include_router(events.router, prefix="/events", tags=["events"])      # A
app.include_router(catalog.router, tags=["catalog"])                      # B  /categories, /regions, /facilities
app.include_router(venues.router, prefix="/venues", tags=["venues"])      # B
app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])  # B
app.include_router(internal.router, prefix="/internal", tags=["internal"])  # B
```

- `/metrics`는 `core/metrics.py`가 앱에 붙입니다(Nginx로 밖에 내보내지 않음).
- `main.py`를 동시에 고치면 충돌이 나기 쉬우니, 라우터를 추가할 때는 한 사람씩 합칩니다.
