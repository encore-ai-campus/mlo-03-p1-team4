# scripts — 운영 스크립트 (담당: A)

API가 아니라 사람이 필요할 때 돌리는 스크립트입니다.

| 파일 (예정) | 하는 일 |
| --- | --- |
| `replay_events.py` | MongoDB가 멈췄던 동안의 이벤트를 `events.log`에서 다시 넣음. `event_id` UNIQUE라 여러 번 돌려도 중복 없음 |
| `measure_event_reliability.py` | 시험 세션의 API 접수·로그·MongoDB 고유 ID를 읽기 전용으로 대조. 생성기 직접 적재분은 제외 |

```bash
conda run -n pro_1 --no-capture-output python -m scripts.replay_events --since 2026-11-05T10:00
```

`backend/`를 현재 폴더로 두고 실행합니다. 설정은 앱과 같은 `.env`를 읽습니다.

```bash
conda run -n pro_1 --no-capture-output python -m scripts.measure_event_reliability --session-id <시험 세션 UUID> --accepted <202 응답의 accepted 합계> --expected-unique <재전송 제외 고유 이벤트 수>
```

MongoDB 백그라운드 쓰기가 끝난 뒤 실행합니다. `--accepted`에는 재전송을 포함한 API 접수 횟수를, `--expected-unique`에는 원래 만든 고유 이벤트 수를 넣습니다. 고유 수를 모르면 유실률을 계산하지 않습니다. 장애 중에는 `fallback_only_in_log`, 복구 뒤에는 `loss_rate`와 `missing_mongo_event_ids`를 대조합니다. 시험용 로그가 다른 위치에 있으면 `--file`로 지정합니다.
