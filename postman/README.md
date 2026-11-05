# Postman CLI 테스트

이 폴더는 B의 예약 API를 Postman CLI로 반복 검증하기 위한 로컬 컬렉션과 환경 파일을 둡니다. Postman 계정이나 공유 워크스페이스 없이 실행할 수 있습니다.

Windows에서 `postman`이 데스크톱 앱 별칭으로 잡히면 NVM 설치 폴더의 npm shim을 직접 부릅니다. 아래 코드는 Postman CLI가 설치된 Node 버전 폴더를 찾습니다.

```powershell
$PostmanCli = Get-ChildItem (Join-Path $env:NVM_HOME 'installs') -Directory |
  Sort-Object Name -Descending |
  ForEach-Object { Join-Path $_.FullName 'postman.cmd' } |
  Where-Object { Test-Path -LiteralPath $_ } |
  Select-Object -First 1
& $PostmanCli --version
```

## 안전 확인

- `Contract checks`는 OpenAPI의 예약 경로와 인증 실패 응답을 확인하며 DB 데이터를 쓰지 않습니다.
- `F-30 live booking`은 예약 생성 뒤 같은 요청을 한 번 더 보내 10분 내 재시도 응답 200을 확인합니다. 로컬 `spacecube_test` API만 대상으로 하고, 활성 공간·예약 가능 시간·Bearer 액세스 토큰을 환경에 넣은 뒤 실행하세요.
- `access_token`은 비워 두고 Git에 저장하지 않습니다. 실예약 확인용으로 `Local.private.environment.yaml`을 복사해 사용하며, 이 파일은 `.gitignore`에 포함됩니다.
- 컬렉션 기본 실행 시 예약 환경값이 비어 있으면 쓰기 요청은 건너뜁니다.

## 검증

```powershell
& $PostmanCli collection lint 'postman/collections/Reservations API'
& $PostmanCli environment lint 'postman/environments/Local.environment.yaml'
& $PostmanCli collection run 'postman/collections/Reservations API' `
  --environment 'postman/environments/Local.environment.yaml' `
  --no-report-events
```

실예약 확인용 환경을 만들 때는 템플릿을 복사한 뒤 로컬 값만 채웁니다.

```powershell
Copy-Item 'postman/environments/Local.environment.yaml' 'postman/environments/Local.private.environment.yaml'
```

API는 `backend/`에서 실행하고 `base_url`은 `http://127.0.0.1:8000`을 가리키게 합니다. `Local.private.environment.yaml`에 `venue_id`, `booking_date`, `start_hour`, `hours`, `headcount`, `method`, `access_token`을 실제 테스트 값으로 채운 경우에만 예약을 생성합니다. 실예약 테스트는 `--environment 'postman/environments/Local.private.environment.yaml'`로 실행하세요.
