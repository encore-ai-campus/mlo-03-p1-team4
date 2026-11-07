# PR #69 보완 검증

- 최신 develop 4d8386f에 기존 #69 시나리오를 적용한 별도 검증 폴더에서 수행했다. 원본 작업 폴더는 보존했다.
- 회귀 테스트를 먼저 추가해 14개 실패를 확인한 뒤 기본 조회·상한·예약 결과 분류를 구현했다. 별도 리뷰의 허위 성공 문제도 5개 실패로 재현한 뒤 보완했다.
- 최종 simulator/locust/tests/test_daily_locustfile.py: **27 passed**, Locust gevent/SSL monkey patch 경고 1개. 테스트 assertion·시간 제한을 완화하지 않았다. 이 테스트는 네트워크·DB 쓰기를 사용하지 않는다.
- Ruff check/format, Windows 실행기 구문, Locust --list의 네 클래스 확인.
- 실제 정문 http://192.168.0.218 Explorer ReadOnly 1명·10초: 실제 최고1명, GET12건·실패0, p95 약160ms. 로그인·이벤트·예약 POST는 보내지 않았고 Loki 전달은 disabled였다. Grafana 일일 적재 검증을 뜻하지 않는다.
- 읽기 전용 코드 리뷰 지적 2건(칸 응답 조기 반환·작업 예외의 허위 성공)을 보완하고 재검토에서 추가 중요 문제 없음 확인.

## PM 댓글 반영 (2026-11-07)

- 최신 `origin/develop`을 PR 브랜치에 병합했다. `/events`는 `event_type` 대신 허용된 `event_name`과 schema version, 사용자·사이트·획득·페이지·이동 문맥을 보낸다. 공간 이벤트의 `products.product_id`도 포함한다.
- 사용자 시작 때 서로 다른 `X-Session-Id`를 만들고 로그인·이벤트·조회·예약 요청 헤더에 사용한다. 이벤트 배치와 `user.session_id`에도 같은 UUID를 전달하고 순번을 증가시킨다.
- 중복 없는 실제 날짜를 사용자에게 순환 배정하고 재방문 때 다음 날짜를 쓴다. Write 예약은 페르소나의 요일 필터 후 날짜 2개 이상을 요구한다. 공간 조회 페이지와 가능 시간 시작 칸을 분산하고, 같은 Locust 프로세스 안에서 이미 선택한 겹치는 슬롯은 예약 후보에서 제외한다. 서버의 `SLOT_TAKEN` 대응은 유지한다.
- `run_daily.ps1`은 기존대로 실행마다 고유한 `logs/persona-...` 디렉터리를 만들고 `--csv`·`--html` 경로를 지정한다. 실제 정문을 호출해 CSV·HTML을 생성하는 검증은 하지 않았다.
- Locust 전용 회귀 **32 passed**, Ruff check·format 통과, `locust --list`에서 네 페르소나 확인. 테스트에는 gevent/SSL monkey-patch 경고 1개가 있다. 현재 `pro_1`은 Locust 2.43.1을 실행했지만 `environment.yml`은 2.47.0을 고정하므로 고정 버전에서의 실행은 확인하지 못했다.

## 남은 검증

Write 모드 로그인·예약·이벤트의 실제 저장, 실제 로그 파일 생성, 작업 스케줄러 등록, Loki에서 같은 run_id 확인은 아직이다. DB exporter 미완료이며 서버 설정은 변경하지 않았다.
전체 verify.ps1는 이번 보완에서 재실행하지 않았다. #73에서 확인한 로컬 CHECK_DB_URL 미설정 문제를 그대로 두고 업무 DB로 대체하지 않았다. 기존 PR 본문의 과거 전체 통과 기록을 이번 보완의 검증 결과로 재사용하지 않는다. CI 결과와 별도 확인한다.

정식 A7 혼합 시나리오·워밍업 reset·SameSlotRush·DB 삭제/초기화·계정 일괄 생성은 이 PR 범위가 아니다. 실제 브라우저 Playwright 시나리오와 Locust HTTP 페르소나도 구분한다.
