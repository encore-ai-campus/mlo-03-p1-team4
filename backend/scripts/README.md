# scripts — 운영 스크립트 (담당: A)

API가 아니라 사람이 필요할 때 돌리는 스크립트입니다.

| 파일 (예정) | 하는 일 |
| --- | --- |
| `replay_events.py` | MongoDB가 멈췄던 동안의 이벤트를 `events.log`에서 다시 넣음. `event_id` UNIQUE라 여러 번 돌려도 중복 없음 |
| `measure_event_reliability.py` | 시험 세션의 API 접수·로그·MongoDB 고유 ID를 읽기 전용으로 대조. 생성기 직접 적재분은 제외 |
| `prepare_issue17_db_user.ps1` | `.31` 시험 계정을 `spacecube_test` DML 권한만 갖도록 준비 |
| `run_issue17_test_api.ps1` | `.31/.40` 전용 설정으로 격리 API를 localhost에서 실행 |
| `replay_issue17_events.ps1` | `.40` 복구 뒤 격리 로그 재적재와 세션 지표 계산 |

```bash
conda run -n pro_1 --no-capture-output python -m scripts.replay_events --since 2026-11-05T10:00
```

`backend/`를 현재 폴더로 두고 실행합니다. 설정은 앱과 같은 `.env`를 읽습니다.

```bash
conda run -n pro_1 --no-capture-output python -m scripts.measure_event_reliability --session-id <시험 세션 UUID> --accepted <202 응답의 accepted 합계> --expected-unique <재전송 제외 고유 이벤트 수>
```

MongoDB 백그라운드 쓰기가 끝난 뒤 실행합니다. `--accepted`에는 재전송을 포함한 API 접수 횟수를, `--expected-unique`에는 원래 만든 고유 이벤트 수를 넣습니다. 고유 수를 모르면 유실률을 계산하지 않습니다. 장애 중에는 `fallback_only_in_log`, 복구 뒤에는 `loss_rate`와 `missing_mongo_event_ids`를 대조합니다. 시험용 로그가 다른 위치에 있으면 `--file`로 지정합니다.

## 이슈 #17 시험 API

`run_issue17_test_api.ps1`는 `.31/spacecube_test`와 `.40/space_rental_analytics_test`를 연결한 격리 API를 `127.0.0.1:8002`에서 시작합니다. DB 비밀번호는 실행 중 숨김 입력으로만 받고 `.env`나 저장소 파일에 기록하지 않습니다. 이벤트 로그는 OS 임시 폴더에 따로 생성합니다. 출력된 PID, `X-Internal-Key`, `X-Synthetic-Key`는 이번 로컬 시험에만 사용하고 공유하지 않습니다. 끝난 뒤 PID 프로세스를 종료합니다.

`.31`에 `issue17_runner@100.100.100.1` 계정이 없거나 권한 범위를 맞춰야 하면 먼저 `prepare_issue17_db_user.ps1`를 실행합니다. root와 시험 계정 비밀번호는 숨김 입력으로 받습니다. 계정은 `spacecube_test`에서 SELECT/INSERT/UPDATE/DELETE만 갖고, 다른 전역 권한은 제거됩니다. Workbench SQL 기록에 비밀번호가 남지 않도록 MariaDB native password 해시를 사용합니다.

`100.100.100.1`은 이 PC의 VMware VMnet8 어댑터 주소이자 `.31` 접속의 출발지 주소입니다. VM에 할당하는 `.2` 이상의 주소와 용도가 다릅니다. 실패 시 스크립트는 단계·오류 종류·DB 오류 코드만 출력합니다.

`.40` MongoDB root 비밀번호가 이전에 채팅·문서·로그로 공유됐다면 새 값으로 교체한 뒤 사용합니다. `.31` 관리자 비밀번호도 같은 값이면 `.31`도 교체하고, 새 값만 숨김 입력에 넣습니다.

`backend/` 폴더에서 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare_issue17_db_user.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_issue17_test_api.ps1
```

MongoDB를 복구한 뒤 시험 API가 출력한 임시 `events.log`를 지정해 두 번 재적재하여 중복 방지를 확인합니다. 필요하면 같은 실행에서 해당 세션의 지표도 계산합니다. 이 스크립트는 `%TEMP%\issue17-events-<UUID>\events.log`만 허용하고 MongoDB 비밀번호는 숨김 입력으로 받습니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\replay_issue17_events.ps1 `
  -LogFile "$env:TEMP\issue17-events-<UUID>\events.log" `
  -SessionId <시험 세션 UUID> -Accepted <202 accepted 합계> -ExpectedUnique <재전송 제외 고유 수>
```
