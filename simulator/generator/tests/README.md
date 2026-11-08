# 생성기 검증

`python -m pytest simulator/generator/tests -q`로 실행합니다. 설정·세션·시각·작업 기록·MongoDB 오류 처리는 외부 연결 없이 검증합니다. 서비스 통합 검증은 `CHECK_DB_URL`이 가리키는 로컬 MariaDB `spacecube_test`에서만 실행하며, 외부 트랜잭션을 롤백합니다. SQLite는 사용하지 않습니다.

공간보충기만 검증하려면 `python -m pytest simulator/generator/tests/test_venue_supplement.py -q`를 실행합니다. HTTP 201 신규 등록과 200 갱신 구분, 응답 유실 뒤 primary 결과 대조, 동일 요청 최대 3회 시도, 인증·서버 오류 및 시설 제외의 실패 처리, 부분 성공·미확정 항목 재개와 중복 전송 방지를 HTTP/DB 대역으로 검증합니다. 수동모드의 유형별 성공 수·계획 구분·콘솔 요약·보고서 저장도 검사합니다. 실제 크롤러나 내부 API를 실행하지 않습니다.

필수 유형 누락·지역 없음·시설 없음은 신규 실행과 재개에서 모두 API 호출 전에 중단되고 기록 파일도 변경되지 않는지 검사합니다. 기초 데이터가 정상이고 공간이 0개일 때는 기본 프로필로 30건을 계획하며, 개별 프로필의 잘못된 지역·시설은 해당 유형만 실패 처리하는지도 확인합니다.

MongoDB 테스트 대역은 부분 성공·중복·validator 오류 분기를 검증합니다. `CHECK_MONGO_URL`을 실행 환경에서 명시하면 100명·30일 테스트가 실제 MongoDB도 사용합니다. 접속정보를 코드·파일·출력에 남기지 않습니다.

실제 MongoDB 검증은 `space_rental_analytics_test.generator_validation_<UUID>` 컬렉션을 새로 만듭니다. 기존 Node로 `mongo_schema.cjs`를 실행해 공식 `docs/db/mongo_init.js`의 validator·인덱스 정의를 추출하며, 운영 `events/event_daily`와 기존 스키마는 변경하지 않습니다. 정상 적재, 동일 실행 재개 시 추가 0건, 잘못된 문서의 121 거절을 확인합니다. MariaDB는 롤백하고 MongoDB 검증 결과는 DB 담당 확인용으로 보존합니다. 컬렉션 이름과 수량은 `logs/generator-validation-<run_id>/report.json`에 기록합니다.

테스트가 서버나 Docker를 시작하지는 않습니다. Node 경로와 로컬 MariaDB·명시한 MongoDB가 준비되어 있어야 실제 저장까지 검증할 수 있습니다.
