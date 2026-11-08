# 이벤트 파일 기록 실패 대응 계획

> 실행 방식: 이 작업 트리에서 직접 구현한다.

**목표:** API의 `events.log` 기록 실패를 원인별로 관측하고 예약·취소 이벤트가 MongoDB까지 대체 전달되도록 한다.

**접근:** 잠금 실패를 일반 파일 I/O 실패와 구분하는 예외·지표를 추가한다. 예약 서버 이벤트는 파일 기록 실패 시 요청 버퍼에 남겨 응답 후 MongoDB writer로 전달하고, 프론트 이벤트 접수 API의 기존 503 계약은 유지한다. 0.1초 대기는 원인이 확정되지 않아 이번 수정에서 변경하지 않는다.

**기술:** Python 3.12, FastAPI, Prometheus client, PyMongo.

**기준:** `docs/백엔드_A_회원_후기_이벤트.md`, 이슈 #17, `docs/DB풀_5+5_읽기쓰기_재시험결과_2026-11-07.md`.

## 전역 제약

- SQL 원문·인증정보·개인정보를 로그나 지표 label에 넣지 않는다.
- `log_event()` 공개 시그니처와 API 오류 계약은 바꾸지 않는다.
- MongoDB 실패 지표와 파일 기록 실패 지표를 구분한다.
- 운영 DB·서버 설정을 변경하거나 부하 시험을 실행하지 않는다.

## 검토 초점

- 스레드 잠금 timeout과 OS 파일 잠금 timeout이 구분되는가.
- `PermissionError` 등 잠금 외 I/O 오류가 timeout으로 잘못 분류되지 않는가.
- 파일 기록 실패 시 예약/취소 이벤트는 응답 후 MongoDB로 전달되는가.
- 프론트 이벤트 API는 503을 유지하고 실패 문서를 큐에 넣지 않는가.
- 메트릭 label은 유한한 원인 코드만 허용하는가.

## 단계

1. 실패 분류·관측·서버 이벤트 대체 전달의 회귀 테스트를 먼저 작성하고 실패를 확인한다.
2. `_process_lock()`에 구분 가능한 timeout 예외와 잠금 대기 histogram을 추가한다.
3. 이벤트 파일 실패 카운터를 원인 label로 기록하고, 서버 예약 이벤트만 MongoDB writer의 응답 후 버퍼로 보낸다.
4. 기존 문서와 대시보드 정의를 동기화하고 관련 검증을 실행한다.
5. 이슈 #17에 붙일 측정 결과·수정 범위·미확정 원인·후속 운영 검증 문안을 준비한다. GitHub 쓰기 인증이 없으면 원격 이슈는 수정하지 않는다.

## 메트릭 수집 아키텍처 결정

이 수정으로 새 FastAPI 메트릭은 기존처럼 Prometheus가 `/metrics`를 pull 한다. 현재 7 VM·19 target에서 이 경로를 유지하고 Alloy는 로그를 Loki로 보낸다. Alloy `prometheus.remote_write`에서 자체 Prometheus receiver로 보내는 전환은 이번 범위에서 적용하지 않는다. 원시 Prometheus의 remote-write receiver는 고볼륨 수집 경로로 권장되지 않고, 별도 receiver·방화벽·중복 scrape 제어가 필요하기 때문이다. Mimir 같은 Remote Write 저장소를 도입할 때 Alloy scrape+remote_write를 별도 설계한다.
