# 7대 VM 단계별 부하 구현·실행 계획

스킬: writing-plans · executing-plans · test-driven-development · ecc-security-review. 기존 상세 시나리오를 사용자 승인 범위에서 직접 실행한다.

- [x] 작업판 인계 확인·잠금 선점·7대 전원·DB 복제·API 계약 읽기 점검.
- [x] logic.py: 시간 자원 분리·예약 응답·expected 오류·측정 구간 판정 테스트를 먼저 실패 확인 후 구현.
- [x] locustfile.py: 공개/인증 읽기, 예약·취소, 후기 CRUD, 정보·이벤트·인증 smoke와 혼합 여정. 이벤트는 실제 배포 event_name 계약 사용.
- [x] runner.py: 키를 메모리로 조회·합성 계정/fixture 준비·단계·회복 간격·명확한 중단·원본 기록·보고서.
- [x] sample_remote.py: 7대 CPU/메모리/디스크·health·DB 복제·서버 로그를 읽기 전용 수집. MariaDB exporter 2대 추가 완료, Mongo는 SSH 자원 표본.
- [x] Ruff·순수/격리 9건·1명 smoke 및 C01/C02 통과. 최초 이벤트 필수 문맥 누락 실패 run 보존.
- [ ] 모든 주요 메소드 1→5명 smoke, 공개 읽기·예약 쓰기 5→20→50명 탐색. 단계 사이 30초 이상·health 회복 확인.
- [ ] 정상 조건이면 혼합 50명 10분(목표 도달 후 워밍업 60초+본 측정 540초). 실패하면 이유를 남기고 무리하게 다음 단계로 진행하지 않음.
- [ ] 완료 후 로그·DB/이벤트 전후 수·사양·SLO를 보고하고 잠금 해제·공용 작업판 갱신. 서버에 결과 사본 보관.

Ruling: 다른 VM·DB·워커/동시성 설정은 고정한다. 계정은 새 합성 계정 50개 이상을 독점 할당하며 자격 증명을 파일에 쓰지 않는다. 기존 source checkout SHA와 실제 배포 SHA가 다르므로 OpenAPI와 배포 파일의 지문을 기록한다. 새 패키지를 설치하지 않는다. 실제 DB에 DROP/TRUNCATE/대량 DELETE는 하지 않는다.
