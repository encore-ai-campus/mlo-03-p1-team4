# DB 모니터링 요청 — 11-07 적용 결과

이전 192.168.0.x 요청은 현재 시험망 192.168.219.x에 적용했다. primary .212 / replica .213 / mon .217이다. [전체 운영 현황](../../../docs/DB_운영_모니터링_현황_2026-11-07.md)을 기준으로 한다.

- 두 DB의 node exporter 1.7.0(9100)·mysqld exporter 0.15.0(9104), systemd 자동 실행을 확인했다. mon만 접근하고 현재 PC의 접근은 차단된다.
- MariaDB 10.11.14, max_connections 151, 전역 max_user_connections 0, team4 계정별 제한 0이다. 기존 값을 올리지 않았다.
- exporter는 localhost 전용 계정·최대 연결 3, PROCESS/REPLICA MONITOR + SELECT ON spacecube.*만 사용한다. 인증 파일은 root:spacecube-exporter 0640, 상위 폴더 0750이다. 인증값은 공유하지 않는다.
- 활성 collector 9종: global_status, global_variables, slave_status, info_schema.tables, info_schema.innodb_metrics, info_schema.processlist, info_schema.innodb_cmp, info_schema.innodb_cmpmem, info_schema.query_response_time. DB 플러그인·userstat를 새로 켜지 않았다.
- CPU·메모리·디스크 여유, spacecube 데이터/인덱스/테이블 용량, 연결/최고 연결/실행 쿼리/접속 오류, InnoDB 잠금·데드락, 복제 지연·스레드를 수집한다. 19/19 Prometheus 대상 UP을 확인했다.
- api1 .214 / api2 .215별 Sleep·Query 수·현재 상태의 최대 체류 시간·InnoDB 행 잠금 대기를 15초마다 집계한다. 상태 체류 시간은 HTTP 응답 지연이나 앱 DB 풀 획득 대기가 아니다.
- SQL 원문·비밀번호·토큰은 수집하지 않는다. slow query/general log를 새로 켜지 않았다. DB 풀 획득 대기·프로세스별 Uvicorn 동시성은 앱 계측이 추가로 필요하다.

11-06 Uvicorn 200 제한 재시험에서 특정 워커 제한과 HAProxy health 503이 관측됐지만 DB 병목 확정은 아니다. 현재 지표를 확보한 상태에서 워커·DB 한도·하드웨어를 고정하고 새 읽기/쓰기 시험을 진행한다.
