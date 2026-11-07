# 독립 헬스 회귀 검증 (B · F-70)

로컬 업무 HTTP 무응답·연결 실패·과부하 503 및 primary 장애 판정 13건과 배포 주소 생성·입력 거절·기준 파일 보존 17건을 검증합니다.
저장소 상태 확인은 대체하므로 업무 DB 읽기·쓰기는 없습니다. `CHECK_DB_URL`이 설정돼 있으면 루트 공통 fixture의 테스트 DB 실행 잠금 접속은 일어납니다. 주소 예시는 문서용 예약 대역을 사용합니다.

프로젝트 `pro_1` 환경에서 저장소 루트를 기준으로 실행합니다.

```powershell
conda run -n pro_1 python -m pytest infra/haproxy/tests -q
```

루트 `pytest.ini`의 기본 수집에도 포함되므로 `verify.ps1`과 CI의 전체 pytest가 같은 회귀를 실행합니다. CI는 `infra/haproxy/**`·`infra/nginx/**` 변경도 감지합니다.
