# Postman CLI 테스트

이 폴더는 B의 예약·내부 공간 등록 API를 Postman CLI로 반복 검증하기 위한 로컬 컬렉션과 환경 파일을 둡니다. Postman 계정이나 공유 워크스페이스 없이 실행할 수 있습니다.

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
- `F-30 live booking`은 예약 생성·재시도·F-40 목록/상세 조회 후 마지막에 취소·전액 환불을 확인합니다. 로컬 spacecube_test API만 대상으로 실행하세요.
- F-40 컬렉션은 방금 생성해 후기를 작성하지 않은 예약의 `review_id: null` 필드 포함을 검사합니다. `backend/tests/check_reservation_http.py`는 이 컬렉션 실행 뒤 별도 HTTP 확인으로 후기 작성·소프트 삭제 후 목록·상세 ID 유지와 중복 작성 차단을 확인합니다. 목록당 SQL 호출 횟수와 페이지 범위는 MariaDB pytest에서 검증합니다.
- `access_token`은 비워 두고 Git에 저장하지 않습니다. 실예약 확인용으로 `Local.private.environment.yaml`을 복사해 사용하며, 이 파일은 `.gitignore`에 포함됩니다.
- 가상 예약에는 `X-Synthetic: 1`과 `synthetic_api_key`를 함께 보냅니다. 키는 임시 API 서버의 `SYNTHETIC_API_KEY`와 같아야 하며 공유 템플릿에는 비워 둡니다.
- 컬렉션 기본 실행 시 예약 환경값이 비어 있으면 쓰기 요청은 건너뜁니다.

## 검증

F-61 내부 공간 등록은 `collections/Internal venues API`와
`environments/Internal.environment.yaml`을 사용합니다. 기본 환경에서는 쓰기 요청을 건너뜁니다.
실제 등록·재전송·갱신·출처 오류 확인은 로컬 `spacecube_test`의 `CHECK_DB_URL`을 설정한 뒤
`pro_1`에서 `python backend/tests/check_internal_http.py`로 실행합니다.
내부 키·고유 출처·임시 서버는 검증기가 준비하고 종료 시 이번 실행 데이터를 정리합니다.

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

API는 `backend/`에서 실행하고 `base_url`은 `http://127.0.0.1:8000`을 가리키게 합니다. `Local.private.environment.yaml`에 `venue_id`, `booking_date`, `start_hour`, `hours`, `headcount`, `method`, `access_token`, `synthetic_api_key`를 실제 테스트 값으로 채운 경우에만 예약을 생성합니다. 실예약 테스트는 `--environment 'postman/environments/Local.private.environment.yaml'`로 실행하세요.

## 임시 서버를 사용하는 실제 HTTP 검증

저장소 루트에서 `pro_1` Python으로 실행합니다. `CHECK_DB_URL`에는 기존 DDL·seed가 적용된 로컬 MariaDB `spacecube_test`를 지정해야 합니다.

```powershell
python backend/tests/check_reservation_http.py
```

검증기는 실제 인증으로 OpenAPI·401·생성·재시도·목록·상세·취소 순서의 7요청/15검증을 실행합니다. DB 환불·칸 반환·예약/취소 카운터와 events.log의 취소 유형을 확인하고 임시 데이터를 정리합니다.
테스트용 서명 키·비밀번호는 자식 프로세스 환경과 메모리에만 두고, 액세스 토큰·가상 요청 키는 실행 중의 임시 환경 파일에만 넣습니다. 출력에서는 비밀값을 가립니다. 종료 시 서버·임시 파일과 이번 실행에서 만든 ID의 가상 데이터만 정리합니다.
