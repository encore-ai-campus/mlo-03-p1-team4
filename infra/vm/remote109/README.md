# 109 원격 시스템 자동화

109 Windows의 VMware Workstation을 WSL2 Terraform·Ansible로 제어한다. 기존 `wsl-vmware-lab` 템플릿·vmrest 인증을 재사용하되 Terraform 상태·VM 경로·SSH 키·배포 경로는 분리한다.

| 위치 | 역할 |
| --- | --- |
| 이 PC | Git 확인, 프론트 빌드, Grafana 브라우저, Playwright·Locust 실행 |
| `ssh playdata` (192.168.0.109, WSL2) | Terraform·Ansible 제어 노드 |
| 109의 VMware | gw .218 / api1 .214 / api2 .215 / mon .217, 모두 브리지 |
| 기존 DB | primary .212 / replica .213, 생성·초기화·마이그레이션하지 않음 |

MongoDB는 제외한다. 시스템은 Ubuntu 24.04 cloud image 기반이며 SSH 사용자는 `ubuntu`, 비밀번호 로그인 없이 전용 SSH 키를 사용한다.
원본 템플릿, 기존 109 데모 VM과 `wsl-vmware-lab/terraform` 상태는 변경하지 않는다.

구현 순서와 검증 결과는 `PLAN.md`에 기록한다. 비밀값·개인키·Terraform 상태는 Git에 넣지 않는다.

## 현재 접속

| 화면 | 주소 |
| --- | --- |
| 서비스 | http://192.168.0.218/ |
| 서버 | http://192.168.0.217:3000/d/spacecube-servers |
| Nginx | http://192.168.0.217:3000/d/spacecube-nginx |
| FastAPI | http://192.168.0.217:3000/d/spacecube-api |
| HAProxy | http://192.168.0.217:3000/d/spacecube-haproxy |
| Alloy | http://192.168.0.217:3000/d/spacecube-alloy |
| Loki | http://192.168.0.217:3000/d/spacecube-loki |
| 전체 로그 | http://192.168.0.217:3000/d/spacecube-logs |

Grafana 계정은 `admin`. 비밀번호는 새 인스턴스용이며, 이전 로컬 Grafana 비밀번호와 다르다.
사용자가 확인할 때만 `ssh playdata 'cat ~/.config/spacecube109/grafana/.env'`를 실행한다. 값을 공유·커밋하지 않는다.
초기 관리자 설정은 새 관리자 한 명만 있는 인스턴스에서 한 번 수행하며, 완료 마커 뒤에는 인증 실패 시 자동 재설정하지 않는다.

`.211`은 다른 장비 응답이 있어 제외했다. DB 서버·스키마·기존 데이터는 생성·초기화·변경하지 않았다.
MongoDB 제외에 따라 `/api/health`는 200 degraded / mongo down이다. primary·replica 연결은 정상 확인했다.

## 파일과 실행 위치

| 위치 | 내용 |
| --- | --- |
| 109 `~/spacecube109/source` | develop 9b9b223 소스 |
| 109 `~/spacecube109/overlay/infra/vm/remote109` | 이 폴더의 Terraform·Ansible 자동화, 별도 state |
| 109 Windows 기본 VM 폴더의 `spacecube-*` | 이번 Terraform이 관리하는 새 VM 4대 |
| 109 `~/.config/spacecube109` | 전용 키, 보호된 앱·Grafana `.env` |
| 이 PC `logs/remote109-*` | Playwright JSON·Locust CSV/HTML (Git 제외) |

등록된 Ubuntu 24.04 OVA 기반 템플릿을 복제했다. 원본 OVA·base·기존 데모 VM은 다시 준비하거나 삭제하지 않는다.
Terraform provider는 사용자 지정 VM 경로를 실제로 사용하지 않는 현상이 있어 기본 폴더의 고유 `spacecube-*` 이름을 사용한다.
기존 `wsl-vmware-lab/terraform` state는 복사하거나 수정하지 않는다.

## 재실행 (이 PC PowerShell)

```powershell
# 매번 109 preflight를 거친다. Plan은 적용하지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Plan
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Status

# 새 VM 생성: 최초 OFF → cloud-init → ON. 이미 준비된 VM은 재생성하지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Create

# 현재 작업 소스의 프론트를 실제 API 모드로 빌드하고 Ansible로 배포한다.
# SourcePath를 주면 그 소스의 backend와 frontend를 사용한다. 비밀 파일은 묶지 않는다.
powershell -NoProfile -File infra/vm/remote109/deploy-109.ps1 -Action Configure

# 이 PC에서만 부하를 만든다. 조회 전용, DB 쓰기 없음.
powershell -NoProfile -File infra/vm/remote109/run-experiments.ps1 -Users 5 -Duration 30s
powershell -NoProfile -File infra/vm/remote109/run-experiments.ps1 -Users 50 -Duration 60s -SkipBrowser
powershell -NoProfile -File infra/vm/remote109/run-experiments.ps1 -SkipLoad
```

`On`·`Off`는 이번 state에 VM 4대가 모두 있을 때만 전원을 변경한다. 운영 중 부하 시험과 동시에 실행하지 않는다.
삭제 명령은 이 실행기에 넣지 않았다. 삭제가 필요하면 실제 API·state·파일 경로를 대조해 별도 검토한다.

최초 DB 런타임 설정은 `create_runtime.py`에 JSON을 stdin으로 전달해 만든다. 비밀번호는 인자나 tfvars에 넣지 않는다.
현재는 이미 설정돼 있다. 키는 재실행 시 유지하며 두 앱에 같은 값을 전달한다.

## 스킬

사용자 요청으로 `vmware-wsl-lab` 4675414를 설치했다.

- 이 PC: `C:\Users\jinsa\.agents\skills\vmware-wsl-lab`
- 109 WSL: `/home/playdata/.agents/skills/vmware-wsl-lab`
- 109 기반 저장소: `/mnt/c/Users/Playdata/wsl-vmware-lab`
- preflight: vmrest 미인증 401 / 인증 200, 도구·기존 부팅 작업 점검 통과.

다음 대화부터 `$vmware-wsl-lab`로 호출할 수 있다. 목록에 안 보이면 Codex를 다시 시작한다.
스킬의 기본 네트워크는 NAT/host-only지만, 이번 새 시스템은 사용자 지시에 따라 브리지로 확장했다. 기반 템플릿과 기존 실습 네트워크는 변경하지 않았다.

## 결과와 공유

- `RESULTS.md`: 검증·예비 부하 결과와 한계.
- `TROUBLESHOOTING.md`: 발생·확인·처리·검증 기록.
- `UPSTREAM-ISSUE-DRAFT.md`: `naelonambul/wsl-vmware-lab`에 공유할 익명화 이슈 초안. 공유 기록이며 이슈 #1로 게시했다.

GitHub 게시에는 실행 원문이나 `.env`·개인키·state·생성 inventory를 첨부하지 않는다.

단계별 읽기 부하: `run-capacity.ps1`. 실행·해석·결과는 [LOAD-RESULTS-20261106.md](LOAD-RESULTS-20261106.md).


## 현재 실험 방법과 증거

현재 배포 코드는 develop d00988b, VM은 109 단일 호스트, Uvicorn 2워커·동시성 200이다. 단계를 실행하려면 `./infra/vm/remote109/run-capacity.ps1 -Stages @(50,100,200,400) -Seconds 60`을 사용한다. 요청 종류는 GET 유형·검색·상세·시간 칸이며 사용자 대기는 1~3초다. 각 단계 10초 내 목표 사용자에 도달하도록 증가율을 정하고 history CSV의 실제 인원을 확인한다.

실패율 1% 초과·p95 500ms 초과·실행 오류·목표 미도달이면 상승을 중단한다. SSH 전후 검사는 실제 DB 헬스와 6:6 분산·15개 지표·Nginx·Loki 라벨을 확인한다. CPU는 1분 rate를 15초 간격으로, 메모리는 MemAvailable 기준으로 저장한다. 결과는 logs 아래 CSV·HTML·JSON·Markdown으로 생성되며 Git에서 제외된다.

[공유용 증거](records/README.md), [실험 해석](LOAD-RESULTS-20261106.md), [dd.md 검토](DD-REVIEW.md), [DB 요청](DB-MONITORING-REQUEST.md)을 참고한다. 판정용 A7 10분·유선·워밍업 제외 혼합 시험이 아니며 DB 쓰기·로그인 부하·동시 예약은 아직이다.
