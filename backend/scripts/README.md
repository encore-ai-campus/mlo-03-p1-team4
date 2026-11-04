# scripts — 운영 스크립트 (담당: A)

API가 아니라 사람이 필요할 때 돌리는 스크립트입니다.

| 파일 (예정) | 하는 일 |
| --- | --- |
| `replay_events.py` | MongoDB가 멈췄던 동안의 이벤트를 `events.log`에서 다시 넣음. `event_id` UNIQUE라 여러 번 돌려도 중복 없음 |

```bash
conda run -n pro_1 --no-capture-output python -m scripts.replay_events --since 2026-11-05T10:00
```

`backend/`를 현재 폴더로 두고 실행합니다. 설정은 앱과 같은 `.env`를 읽습니다.
