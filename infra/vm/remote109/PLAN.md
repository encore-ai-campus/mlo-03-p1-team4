# 109 원격 VM 자동화 실행 계획

목표: 109에서 기존 시스템을 재현하고 이 PC에서 모니터링·Playwright·Locust로 확인한다.

설계: WSL Terraform 1.17.1 + 기존 vmworkstation provider 2.0.1, 등록된 ubuntu24-base 복제, cloud-init 브리지 고정 IP, Ansible apt·systemd 설치.

- [x] 109의 Windows 32GB RAM·유선 .109, WSL Terraform/Ansible/VMware 기반 확인.
- [x] 사용자 요청으로 이 PC의 시험 VM 4대·기반 VM 삭제. 코드·OVA 유지.
- [x] GitHub develop 최신 9b9b223 확인, 109 별도 source 클론.
- [x] Terraform 구성 문법·plan 검증, 신규 VM 4대만 생성.
- [x] cloud-init SSH 준비·고정 IP·Ansible 연결 확인.
- [x] Ansible로 HAProxy/Nginx/FastAPI/Grafana/Prometheus/Loki/Alloy/exporter 설치.
- [x] DB 접속·현재 스키마·조회 API 확인. DB 변경 없음.
- [x] HAProxy 실제 /health 전환·15개 지표 대상·대시보드·Loki 확인.
- [x] 이 PC의 Playwright 조회 smoke·Locust 읽기 부하 시험.
- [x] 재실행 명령·실험 결과·제약을 README·STATE에 기록.

선택 근거: Linux KVM 신규 설치보다 기존 vmrest provider를 활용한다. 원본 OVA 재전송 대신 같은 Ubuntu 24.04의 준비된 cloud image를 사용한다.
DB 비밀번호·JWT·API 키는 제어 노드와 VM의 보호된 `.env`에만 두고 Terraform 변수·state·Ansible 로그에는 넣지 않는다.

## 후속 미완료

- [ ] DB exporter 및 워커 연결·DB 풀 계측
- [ ] A7 혼합 부하·SameSlotRush·10분 유선 판정
- [ ] dd.md 검토 후속(DD-REVIEW.md)
