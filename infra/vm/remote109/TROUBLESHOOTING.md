# 109 배포 트러블슈팅 기록

GitHub 공유용 초안이다. 자격증명·개인키·Terraform state·실제 사용자 경로·VM ID·MAC은 포함하지 않는다.
원본 로그는 109의 배포 작업 폴더와 이 PC의 Git 제외 `logs/`에 보관한다. 외부 게시 전에는 필요한 부분만 다시 검토한다.

## 1. VMware provider가 사용자 지정 VM 경로와 다른 경로를 반환

- 환경: Windows + WSL2 Ubuntu 24.04, Terraform 1.17.1, `elsudano/vmworkstation` 2.0.1.
- 재현 범위: `wsl-vmware-lab`의 등록된 Ubuntu 템플릿과 인증 로더를 재사용한 별도 Terraform 프로젝트. 기본 예제를 변경 없이 실행한 재현은 하지 않았다.
- 입력: VM 이름 `spacecube-<role>`, `path`는 기본 폴더 밖의 사용자 지정 VM 폴더.
- 관측: clone은 생성됐지만, provider가 `%USERPROFILE%\Documents\Virtual Machines\<denomination>\<denomination>.vmx`를 반환해 `Provider produced inconsistent result after apply ... .path`가 발생했다.
- 영향: 새 VM 4대가 state에 존재하되 tainted로 표시되고, 다음 plan이 VM 교체를 요구했다. cloud-init provisioner는 아직 실행되지 않았다.
- 근거: 실제 새 VMX/VMDK 존재, Terraform state의 실제 경로, plan에서 id 외 8개 속성이 동일함을 확인.
- 처리: 실제 기본 경로에 HCL·새 VM 경로 검증을 맞춤 → 새 VM의 존재와 속성을 확인 → 해당 새 VM 리소스만 untaint → 새 plan `4 to add, 0 to change, 0 to destroy` 확인 → cloud-init 적용·부팅.
- 결과: 원본 템플릿·기존 VM 삭제 없이 새 VM 4대의 Ansible ping 성공.
- 주의: untaint는 일반 오류 무시 수단이 아니다. 실제 디스크·식별자·속성 확인 없이 사용하면 안 된다.
- 외부 공유안: `UPSTREAM-ISSUE-DRAFT.md`. 저장소 안내의 사용자 지정 `LAB_VM_ROOT_WIN` 지원 범위 명시 및 `.path` 불일치 항목 추가 제안.

## 2. 게이트웨이 후보 IP 충돌

- 새 VM이 꺼져 있는데 게이트웨이 후보 IP에서 ping·SSH 응답과 다른 장비의 ARP가 확인됐다.
- 같은 할당 범위의 다른 빈 주소로 gw만 변경했다. 앱 IP는 DB 접근 약속에 맞춰 유지했다.
- 자동화에서 공유기 DHCP 예약/제외 범위는 변경하지 않았다. ARP 검사는 현재 사용 여부만 보여 주므로 장기 운영에는 DHCP 예약이 필요하다.
- 다른 장비의 IP·방화벽·SSH 설정은 변경하지 않았다.

## 3. HTTP IP 접속에서 프론트 요청이 전송되지 않음

- 직접 API 조회는 200인데 브라우저 화면은 네트워크 오류를 표시했다.
- Playwright에서 `isSecureContext=false`, `typeof crypto.randomUUID='undefined'`, `typeof crypto.getRandomValues='function'` 확인.
- 프론트 `getSessionId()`가 fetch 전에 실패한 것이 원인이다. 서버·방화벽 오류가 아니었다.
- 회귀 테스트에서 randomUUID 미지원 조건의 요청 실패를 확인한 뒤, Web Crypto getRandomValues로 동일한 UUID v4를 생성하는 대체 경로를 추가했다.
- 관련 내부 범위: 프로젝트 이슈 #9, F-60 세션 헤더. 이 항목은 VMware 스킬 자체 결함으로 보고하지 않는다.
- 단위 테스트·프론트 verify 결과는 배포 보고서에 기록한다. 실제 브라우저 재검증도 별도로 필요하다.

## 4. 재실행 때 불필요한 서비스 재시작

- 압축 묶음의 gzip 생성 시각이 달라 같은 설정도 변경으로 판단됐다.
- gzip mtime=0, 정렬된 tar 멤버로 묶음을 결정적으로 생성했다.
- 설정·앱 묶음·보호된 런타임 환경의 변경 또는 설치 완료 마커 부재일 때만 역할 설치를 실행하도록 Ansible 조건을 추가했다.
- 두 번째 실행 결과: api1/api2/gw/mon 전부 changed=0, unreachable=0, failed=0.

## 5. DB 데이터 계약 차이

- 기존 DB에는 공간 데이터 18개가 있다.
- 이미지 값 일부가 프로젝트 문서의 `art:` 규약과 다른 로컬 이미지 경로였다.
- DB 스키마·데이터를 수정하지 않았다. DB 담당자가 이미지·이름·소개 수집 정책과 기준 문서를 별도로 대조해야 한다.

## 6. 실행·승인 기록

- 원격 명령의 자동 승인 검토 크레딧 부족이 한 번 발생했고, 사용자 복구 안내 후 다시 진행했다.
- provider 경로 변경 재적용은 자동 승인 검토가 새 plan을 요구했다. 실제 plan으로 변경 범위를 확인하고 삭제 없는 방식으로 state를 복구했다.
- 스킬 저장소와 Codex 스킬을 최신 버전으로 설치하고 preflight exit 0을 확인했다. vmrest 비밀번호를 직접 출력하거나 수정하지 않았다.

## 7. Grafana 초기 관리자 설정과 계정 불일치

- 새 모니터링 VM에서 런타임 `.env`는 준비됐지만, 브라우저와 같은 값의 API 인증이 모두 401이었다.
- Grafana의 환경변수 초기 비밀번호는 이미 생성된 SQLite 관리자 계정을 다시 바꾸지 않는다. CLI 도움말에서 stdin 비밀번호 입력을 확인했다.
- 초기 admin 한 명만 있는 새 인스턴스인지 읽기 전용으로 확인한 뒤, 기존 `.env`의 지정값을 공식 CLI stdin으로 한 번 적용했다.
- 초기화 완료 마커를 두어 나중에 계정이 변경된 상태에서는 자동 재설정을 거부한다.
- 인증 재검증과 브라우저 로그인 성공, 서비스별 대시보드 탭 표시를 확인했다.

## 8. Windows mock E2E 종료 대기

- 74개 테스트 진행 뒤 Playwright가 시험용 Vite preview 정리를 기다리며 종료되지 않았다.
- 명령줄과 PID로 이번 시험용 preview만 확인해 종료했다. 사용자 개발 서버나 원격 VM은 종료하지 않았다.
- 최종 Playwright 출력은 67 passed / 7 skipped, exit 0이었다. 9.4분에는 이 종료 대기 시간이 포함된다.
- 실제 원격 API smoke 3개는 별도 실행으로 1.4초에 통과했다. 목업 시험과 실제 API 시험을 혼동하지 않는다.

## 9. 시험 보고서의 합성 키

- 외부 공유 전 검사에서 Playwright JSON 보고서 2개에 프로젝트 설정의 합성 키가 포함된 것을 발견했다. 게시·공유하지 않았다.
- 두 보고서의 해당 값을 가리고, 헤더를 직렬화되는 프로젝트 설정 대신 실행 시점 fixture에 넣었다.
- trace를 끄고 실행기에서 출력·텍스트 보고서의 키 값을 가린다. 수정한 실제 브라우저 시험은 같은 assertion으로 3개 통과했다.
- Windows 기본 cp949가 특수 문자를 출력하지 못한 경우도 있어 실행기 UTF-8과 PowerShell UTF-8 BOM을 명시했다.
- vmrest·DB 비밀번호, 개인키, Terraform state는 공유용 파일에 포함하지 않는다. 배포 tar도 `.env`·state·개인 실행 산출물을 제외한다.
