# MariaDB 모니터링 추가

실제 219 대역 DB primary .212 / replica .213, mon .217에 맞춘 보조 Ansible 구성이다. 기존 DB 설치·복제·앱 배포 파일은 변경하지 않는다. configure.yml은 exporter·집계 타이머·방화벽만 설정한다.

인증 파일은 DB의 /etc/spacecube-monitoring/my.cnf에 root:spacecube-exporter 0640으로 보관한다. 계정은 localhost 전용·최대 연결 3이며 PROCESS·REPLICA MONITOR와 spacecube 스키마 SELECT만 부여한다. 전역/앱 연결 제한과 DB 데이터는 변경하지 않는다.

app_connections.py는 api1/api2 원본 IP의 Sleep/Query 수·상태 체류 최대 시간·InnoDB 행 잠금 대기 최대 시간을 집계한다. SQL 본문·인증정보·개인정보를 수집하지 않는다. 상태 체류 시간은 개별 요청 전체 지연과 다르다.


현재 적용 결과는 DB_운영_모니터링_현황_2026-11-07.md에 기록했다. 활성 collector는 기본 포함 9종이며 현재 19/19 targets UP이다. configure.yml의 추가 재적용 방어는 UFW active/incoming deny를 요구하고 9100/9104의 명시 deny보다 mon allow를 앞에 배치한다. 이 규칙 정리 변경은 진행 중인 부하에 영향을 주지 않도록 아직 재적용하지 않았다. 현재 실서버의 기존 규칙은 이미 mon-only이며 PC 접근 차단을 확인했다.

persist_dashboards.py는 mon에서 stdin JSON의 user/password로 localhost Grafana API를 읽고 현재 11개 대시보드를 파일 원본과 백업에 저장한다. allowUiUpdates/disableDeletion을 적용하고 서비스 재시작 없이 공급 설정을 reload한다. 비밀번호를 명령줄 인자나 파일에 넣지 않는다. UI의 Save는 DB 저장이고, 다음 파일 변경이 UI 값을 덮을 수 있으므로 재배포 전에 동기화한다.
