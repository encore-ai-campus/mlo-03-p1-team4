# jobs — 주기 실행 배치 (담당: B)

API가 아니라 cron(또는 systemd timer)으로 FastAPI #1에서만 돌립니다.

| 파일 | 주기 | 하는 일 | 기능 |
| --- | --- | --- | --- |
| `complete_reservations.py` | 1시간 | 끝나는 시각이 지난 `confirmed` → completed (`reserve_date < 오늘` 또는 오늘이고 `end_hour ≤ 지금 시`). 칸은 지우지 않음 | F-35 |

- 두 번 돌려도 결과가 같아야 합니다. primary에 씁니다.
- 서비스가 한 번에 조건부 UPDATE하고 커밋합니다. 완료된 예약의 시간 칸과 결제는 유지합니다.
- 성공 시 변경 건수를 `app.log`에 남깁니다. 실패하면 민감한 예외 메시지를 로그에 넣지 않고 종료 코드 1을 반환합니다.
- 로컬 확인은 `backend/`에서 `conda run -n pro_1 --no-capture-output python -m app.jobs.complete_reservations`로 합니다. DB 주소는 `DB_WRITE_URL`에 지정하고, 운영 cron은 api1 한 대에만 등록합니다.
- 결제 대기 만료 배치(`expire_pending.py`)는 11-03에 홀딩이 없어져 만들지 않습니다.
- 크롤러(`crawler/`)도 같은 서버에서 주 1회 cron으로 돌고, 결과는 `POST /internal/venues`로 넣습니다.
- 실행 결과는 `app.log`에 JSON 한 줄로 남겨 Loki에서 봅니다.

```bash
conda run -n pro_1 --no-capture-output python -m app.jobs.complete_reservations
```
