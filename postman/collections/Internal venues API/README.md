# 내부 공간 등록 API 검증

F-61 `POST /internal/venues`의 키 검증·신규 201·재전송/갱신 200·출처 검증을 확인합니다.

기본 환경에서는 OpenAPI와 키 없는 요청만 실행하고 쓰기 요청은 건너뜁니다. 실제 쓰기 검증은 기존 DDL·seed가 적용된 **로컬 MariaDB spacecube_test**에서 `backend/tests/check_internal_http.py`로 실행합니다. 검증기는 고유 synthetic 출처와 임시 내부 키로 실행하고 데이터를 정리합니다.

컬렉션을 직접 실행하려면 로컬 전용 환경에 `allow_internal_write=1`, `internal_api_key`, 세 요청의 JSON 문자열을 설정해야 합니다. 신규 등록 요청은 매번 새 source_id를 사용합니다. 키를 공유 환경이나 Git에 저장하지 않습니다.
