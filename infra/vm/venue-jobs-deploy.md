# 크롤러·공간 보충 배포 안내 — cron / systemd timer

2026-11-08 · 공동/B · #99·#100. 근거: 사용자가 공유한 PM 노진산의 「남은 작업과 월요일(11-09) 계획」(11-08 14시), 변경된 #99, [VM 설치 체크리스트](README.md).

## 1. 배포 환경과 실행 방식 선택

| 구분 | 발표용 분산 환경 | 109 시험·예비 환경 |
| --- | --- | --- |
| 배치 | 노트북 주인이 새로 설치한 VM 7대, DB·시드부터 새로 적재 | 한 호스트의 VM 7대, 기존 시험 데이터 보유 |
| 주소 | `api1 = 192.168.0.214` (사용자 확인). 나머지 VM의 현장 IP도 `/etc/hosts`에 반영 | 기존 주소·설정은 시험 기록으로 관리 |
| 정기 작업 위치 | 노트북 2의 Ubuntu `api1` 한 대 (`192.168.0.214`) | 예비 환경의 `api1` 한 대 |
| 스케줄러 | cron 사용 (11-08 사용자 확정) | 기존 systemd timer 구성 확인 후 선택 |

109의 IP·데이터·활성 타이머가 새 배포에도 그대로 있다고 가정하지 않는다. 109는 용량 시험 작업판의 잠금 해제·인계 확인 뒤에만 운영 담당이 변경한다. 새 환경과 109는 DB·MongoDB 연결 대상을 각각 확인한다. 같은 DB를 향한 정기 실행은 한 api1만 담당한다.

11-08 사용자 확인: 월요일 공간 보충기와 이후 #100 통합 실행기의 배포 대상은 Ubuntu `api1`(`192.168.0.214`)이다. 수동 30건 등록을 검증한 `192.168.0.232`는 별도 테스트 VM이다. 보충기·프로필·실행 기록은 #99의 지정 경로를 따르며, Python·계정·설정 주입은 실제 대상 서버에서 확인한다.

발표 배포는 아래 방식 B의 cron으로 공통 실행 파일을 호출한다. 방식 A의 systemd timer는 다른 환경의 전환 참고용으로 남기며, 발표 환경에서 cron과 함께 등록하지 않는다. 이 문서의 명령은 **배포 대상 Ubuntu VM에서 노트북 주인/운영 담당이 실행하는 예시**다. 문서를 추가한 것만으로 서버에 등록되지는 않는다.

## 2. 월요일 실행 순서와 정책 확인

1. DB 마이그레이션·기본 시드 후 첫 크롤링을 수동 실행한다.
2. 공간 보충기를 실행하고 다섯 유형의 활성 공간이 각각 6곳 이상인지 확인한다.
3. 회원 100명·30일 생성기 → 집계·CSV → 브라우저 점검으로 진행한다.
4. PM 계획의 11:10 이후 정기 실행을 켜고 첫 로그를 확인한다. 분산 환경 준비가 늦으면 PM 판단으로 109 예비 환경을 사용한다.

발표일 정기 크롤링은 **bootstrap, 실행당 상세 합계 20건 이하, KST 매시 :10·:40** 기준이다. `weekly`는 신규 사이트맵 ID·유형별 등록 상한 때문에 이 계획에 대신 사용하지 않는다. 요청 간격·robots·출처별 사전 확인은 [crawler 지침](../../crawler/AGENTS.md)을 따른다. 30분 주기를 시연 이후 상시 운영 주기로 확정한 것은 아니다.

**초기 시연 준비의 「DB 활성 공간 유형별 6곳 이상」과 변경된 #99의 「이번 실행 신규 등록을 유형별 6곳까지 보충」은 서로 다른 수치다.** 변경된 #99의 계획량은 `max(0, 6 - 이번 크롤러의 유형별 유효 신규 등록 수)`이며 HTTP 201만 센다. HTTP 200 갱신은 제외한다. 매회 크롤러 신규 등록이 모두 0이면 보충 공간이 30곳씩 추가될 수 있으므로, PM은 정기 실행을 켜기 전에 변경된 #99 정책과 발표일 주기를 함께 확인한다. DB 보유량 기준으로 정책을 임의 전환하지 않는다.

## 3. 공통 실행 파일과 설정

보충기·프로필·실행 기록 경로는 [#99 7절](https://github.com/encore-ai-campus/mlo-03-p1-team4/issues/99)의 배포 기준이다. Python·실행 계정·공통 진입점·설정 파일은 아래 설치 예시를 실제 api1 환경과 대조하고 #100에서 연결한다.

| 항목 | 배포 기준·확인 사항 |
| --- | --- |
| 저장소 | `/opt/spacecube` — #99 배포 기준 루트 (backend·crawler·simulator 포함) |
| 공간 보충기 | `/opt/spacecube/simulator/generator/venue_supplement.py` — #99 지정 |
| 기본 프로필 | `/opt/spacecube/simulator/generator/venue_profiles.json` — #99 지정 |
| 실행 기록 | `/opt/spacecube/logs/venue-supplement-<run_id>/` — #99 지정, 재개용 기록 보존 |
| Python | `/opt/spacecube/venv/bin/python` — 설치 예시. 실제 Python 3.12·프로젝트 고정 의존성 확인 |
| 실행 계정 | `spacecube`, 그룹 `adm` — 실제 설치 계정과 일치시킴 |
| 공통 진입점 | `/opt/spacecube/ops/run-venue-job.sh` — 운영 담당이 아래 내용으로 설치 |
| 설정 | 공통 `get_settings()`가 읽는 `/opt/spacecube/backend/.env` |
| 필수 값 | `DB_WRITE_URL`, `MONGO_URL`, `INTERNAL_API_KEY`; host는 `db1`, `mongo` |
| 쓰기 경로 | `logs/`, `crawler/data/`와 기존 사이트맵 상태 파일 — 실행 계정 쓰기 권한 확인 |

#100은 통합 실행기의 소스 위치를 `simulator/generator/run_pipeline.py`로 지정한다. 통합 기록은 저장소 루트의 `logs/venue-pipeline-<통합 실행 ID>/`, 보충 기록은 #99의 `logs/venue-supplement-<보충 실행 ID>/`에 보존하며 두 실행 ID를 연결한다. 통합 실행기는 #103 보충기와 #108 크롤러를 연결한 구현이다. #100 본문·댓글에는 실제 Python·실행 계정·작업 폴더·설정 경로가 아직 고정돼 있지 않고 이 문서에서 관리하도록 돼 있다. Ubuntu api1 `192.168.0.214`와 발표 배포의 cron 사용은 11-08 사용자가 추가 확인한 사항이다. 매시 :10/:40 주기는 11-08 사용자 확정이며 cron은 `10,40 * * * *`이다.

대상 서버에서 확정할 실행 환경 항목은 다음 세 가지다. 통합 CLI 연결 후 실제 서버의 정기 실행 검증이 남아 있다.

- [ ] Python 실행 파일 경로와 프로젝트 의존성 설치 상태
- [ ] 실행 계정·그룹 및 기록 디렉터리 접근 권한
- [ ] 환경변수·비밀값 주입 방식과 설정 파일 경로

109 설치기는 `/etc/spacecube/.env`를 서비스 환경으로 주입한다. cron에서도 같은 설정을 쓰려면 운영 담당이 `backend/.env`를 그 보호 파일에 연결하거나 동일한 설정 로딩 경로를 마련한다. 기존 `backend/.env`를 확인 없이 덮어쓰지 않는다. 링크를 쓸 경우 대상 파일·상위 디렉터리를 `spacecube:adm` 실행 문맥에서 읽을 수 있어야 한다. 비밀값을 셸 스크립트·스케줄러·Git에 복사하지 않는다.

VM 안에서 필요한 디렉터리를 준비한다. 기존 설정 파일의 권한은 운영 담당이 확인한다.

```bash
sudo install -d -o spacecube -g adm -m 0750 /opt/spacecube/logs /opt/spacecube/crawler/data
sudo install -d -o root -g root -m 0755 /opt/spacecube/ops
sudo -u spacecube -g adm test -r /opt/spacecube/backend/.env
timedatectl status
getent hosts db1 db2 mongo api1 api2 gw mon
```

공통 파일을 `sudoedit /opt/spacecube/ops/run-venue-job.sh`로 만들고 아래 내용을 넣는다. 통합 apply는 두 출처를 수집하고 #103 저장 계획을 자동 적용한다. `crawler/AGENTS.md`의 실행 직전 약관 확인 규칙을 지키기 위해 운영 담당의 `check-shareit-terms.sh`가 먼저 성공해야 한다. 그 파일은 실제 약관 본문·시행일을 확인하는 현장 절차이며, 단순히 성공 코드를 반환하는 대역으로 만들지 않는다. 미설치·확인 실패 시 이번 호출은 중단된다. `--confirm-shareit-terms` 자체는 자동 약관 검증 기능이 아니다.

```bash
#!/bin/bash
set -euo pipefail
cd /opt/spacecube
export PYTHONPATH=/opt/spacecube:/opt/spacecube/backend
export TZ=Asia/Seoul
exec 9>/opt/spacecube/logs/.venue-dispatch.lock
if ! /usr/bin/flock -n 9; then
    printf '%s\n' '공간 정기 작업 실행 중: 이번 호출을 건너뜁니다.'
    exit 0
fi
test -x /opt/spacecube/ops/check-shareit-terms.sh
/opt/spacecube/ops/check-shareit-terms.sh
exec /opt/spacecube/venv/bin/python -m simulator.generator.run_pipeline --mode apply --crawler-mode bootstrap --confirm-shareit-terms
```

```bash
sudo chmod 0755 /opt/spacecube/ops/run-venue-job.sh
```

`.venue-dispatch.lock`은 공통 진입점의 중복 호출 방지용이다. #99·#100의 `.venue-pipeline.lock`과 다른 파일을 써서 내부 잠금을 다시 잡는 교착을 피한다. #100은 크롤러부터 보충 종료까지 자체 공통 잠금을 유지해야 한다. #100 전에는 운영 담당이 크롤러와 단독 보충기를 동시에 실행하지 않고 순서대로 실행한다.

**통합 CLI 확인:** `python -m simulator.generator.run_pipeline --mode dry-run --crawler-result <JSON>`으로 계획을 확인한다. 입력은 `newly_registered_by_category` 아래 다섯 유형의 0 이상 정수다. `--save-plan`은 미리보기 기록만 남기며 실제 실적으로 재개할 수 없다. 중단된 실제 실행은 `python -m simulator.generator.run_pipeline --mode resume --run-id <통합 UUID>`로 이어간다. 크롤러를 반복 호출하지 않고 연결된 #103 계획을 사용한다. `--profiles`, `--api-url`, `--output-root`를 바꿨다면 재개에도 같은 값을 지정한다. 정기·수동·보충기 단독 실행은 #103의 공통 `.venue-pipeline.lock`을 사용한다.

## 4. 방식 A — systemd timer

`/etc/systemd/system/spacecube-venue-job.service`를 아래 내용으로 저장한다.

```ini
[Unit]
Description=Spacecube 공간 정기 작업
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=spacecube
Group=adm
WorkingDirectory=/opt/spacecube
ExecStart=/opt/spacecube/ops/run-venue-job.sh
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal
```

설정은 공통 진입점에서 호출하는 Python의 `get_settings()`로 읽는다. 서비스에만 환경변수를 추가해 cron 경로와 설정이 달라지지 않도록 한다.

`/etc/systemd/system/spacecube-venue-job.timer`:

```ini
[Unit]
Description=Spacecube 공간 작업 매시 10분과 40분

[Timer]
OnCalendar=*-*-* *:10,40:00 Asia/Seoul
AccuracySec=1s
RandomizedDelaySec=0
Persistent=false
Unit=spacecube-venue-job.service

[Install]
WantedBy=timers.target
```

`Persistent=false`는 VM이 꺼져 있던 동안 놓친 실행을 부팅 직후 보충 실행하지 않는 발표용 선택이다. 다음 정규 시각을 기다리며, 바로 실행할 때는 운영 담당이 service를 수동 시작한다.

기존 크롤러 예약과 아래 방식 B의 cron 줄을 먼저 비활성화하고 활성화한다. 이미 실행 중인 작업이 있으면 종료·인계를 확인한 뒤 전환한다.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now spacecube-venue-job.timer
systemctl list-timers --all
systemctl status spacecube-venue-job.timer
journalctl -u spacecube-venue-job.service --since today --no-pager
```

`enable --now`는 timer를 켠다. 즉시 실제 데이터 작업을 한 번 실행하려면 `sudo systemctl start spacecube-venue-job.service`를 별도로 실행한다. 이 호출도 현재 공통 파일의 명령에 따라 실제 크롤링 또는 통합 apply를 수행한다.

## 5. 방식 B — cron

VM의 시스템 시간대를 `Asia/Seoul`로 맞춘다. cron 종류에 따라 지원이 다른 `CRON_TZ`에 의존하지 않는다. 시간대를 변경했다면 운영 담당이 cron 서비스를 재시작한다.

`/etc/cron.d/spacecube-venue-job`에 아래 내용을 저장하고 마지막 줄에도 개행을 둔다. `/etc/cron.d` 형식에는 사용자 열이 필요하다. 아래 root 작업은 `runuser`로 실제 작업을 `spacecube:adm` 계정에서 실행한다.

```cron
SHELL=/bin/bash
PATH=/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
10,40 * * * * root /usr/sbin/runuser -u spacecube -g adm -- /opt/spacecube/ops/run-venue-job.sh >> /opt/spacecube/logs/venue-schedule.log 2>&1
```

기존 크롤러 예약을 비활성화하고 방식 A timer를 꺼 둔 뒤 활성화한다. `cron` 패키지가 없는 VM은 역할 설치 단계에서 운영 담당이 준비한다.

```bash
sudo systemctl disable --now spacecube-venue-job.timer
sudo chown root:root /etc/cron.d/spacecube-venue-job
sudo chmod 0644 /etc/cron.d/spacecube-venue-job
sudo systemctl enable --now cron
systemctl status cron
sudo tail -n 50 /opt/spacecube/logs/venue-schedule.log
```

timer unit이 아직 없는 신규 VM은 `disable`할 대상이 없는지 확인하고 해당 줄을 생략한다. 로그 파일은 첫 실행 후 생긴다. 이 cron 줄을 사용자 `crontab -e`에 그대로 붙이지 않는다. 사용자 crontab은 사용자 열이 없는 다른 형식이다.

`venue-schedule.log`에는 운영 환경의 로그 순환을 적용한다. `logs/venue-pipeline-*`, `logs/venue-supplement-*`의 재개용 계획·상태는 일반 실행 로그와 구분해 배포·정리 시 보존한다.

## 6. 수동 대체·전환·재배포 확인

- **#100 전:** 공통 진입점으로 크롤러를 실행한 뒤 #99 단독 CLI에 이번 실행의 유형별 신규 등록 수를 전달해 계획 확인·등록을 진행한다. `--newly-registered-by-category` 입력은 다섯 유형 전체를 포함한다.
- **#100 장애 시:** 크롤러 실적을 받지 못하면 `--manual --dry-run --save-plan`으로 유형별 6개씩 총 30개 계획을 저장·확인한 뒤 같은 `run_id`를 `--apply --resume <run_id>`로 적용한다. 중단돼도 같은 명령으로 재개한다. 수동 실행을 새로 반복하면 다시 30개가 추가된다. 이 모드는 DB와 `/internal/venues`가 사용 가능할 때 쓴다. 유형별 실제 보충 성공 수와 총합은 stderr의 한국어 요약 및 `report.json`의 `summary_text`에 남고, 크롤러 신규 수는 미확인으로 표시한다.
- **dry-run:** 계획 확인용이다. 크롤러 실적이 없는 수동 모드는 `--manual --dry-run`, 크롤러 입력을 사용하는 모드는 `--dry-run --newly-registered-by-category <JSON>`으로 확인한다. 발표용 정기 호출은 실제 명령이며 dry-run을 예약하지 않는다.
- **재개:** 중단된 실제 실행 기록의 모드·입력·보충 계획·성공 기록으로 처리한다. 이전 실행의 크롤러 수를 새 실행 실적으로 재사용하지 않는다. 응답 유실 실적을 0으로 취급하지 않는다.
- **기존 예약 찾기:** `systemctl list-timers --all`, `/etc/cron.d/`, `/etc/crontab`, root·운영 계정의 `crontab -l`에서 크롤러와 통합 실행기 호출을 확인한다. 109에는 `spacecube-crawler.timer`가 있을 수 있다. 이용 완료·집계·백업 작업은 각 담당 일정으로 유지한다.
- **방식 전환:** 기존 예약만 끄고 진행 중인 공간 작업의 종료·인계를 확인한 다음 새 방식 하나만 켠다. timer를 끄는 것만으로 이미 실행 중인 service가 취소되지는 않는다.
- **재배포:** 운영 담당이 선택 방식·주기·공통 파일의 실제 명령을 기록한다. #95와 협의하여 `infra/vm/lab/install-role.sh`의 설치 경로에서도 선택이 유지되게 한다. `remote109/ops/timers.snippet.sh`의 예전 weekly 타이머를 추가로 켜지 않는다. 설치기는 아직 이 선택 기능을 구현한 상태가 아니다.
- **동작 확인:** #100 공통 진입점이 배포된 뒤에는 같은 계정·설정으로 1회 실행해 다음 :10/:40 로그, 신규·갱신·보충 수, 다섯 유형 준비 상태를 확인한다. #100 전의 단독 수동 대체는 위에서 저장한 계획의 `run_id`를 `--apply --resume <run_id>`로 적용하고 `logs/venue-supplement-<run_id>/report.json`을 확인한다. 공통 진입점의 원격 확인은 `sudo -u spacecube -g adm /opt/spacecube/ops/run-venue-job.sh`를 사용하며, 원격 작업은 노트북 주인과 운영 담당이 수행한다.

## 7. #100과 담당별 요청에 반영할 내용

| 담당 | 요청 |
| --- | --- |
| B | #99 입력 계약 연결, 계획 저장 후 자동 apply, 재개·공통 잠금, 확정 CLI를 이 안내에 반영 |
| DB | HTTP 201 전용 유형별 신규 수와 부분 결과 전달, bootstrap·출처 준비, 시드·초기화 절차 |
| A·api1 노트북 주인 | 실제 Python/계정/보호 설정 경로·권한 확인, api1 단독 실행·현장 이름 해석 확인 |
| PM | 초기 준비 기준과 변경 #99 정책 관계 확인, 확정된 매시 :10/:40 주기의 시연 환경·운영 담당 확인 |
| 공동·#95 담당 | 확정된 cron 설정과 공통 실행 파일을 재배포 후에도 보존, IP 대신 이름으로 설정 |

통합 실행기·자동화가 늦어져도 월요일 시연은 크롤러 → 보충기 수동 순서로 준비한다. 장애 알림 확장·발표 이후 상시 주기 정착은 후속 작업으로 둔다.

설정 문법 근거: [Ubuntu systemd.timer](https://manpages.ubuntu.com/manpages/noble/man5/systemd.timer.5.html), [systemd 시간 표현](https://manpages.ubuntu.com/manpages/noble/man7/systemd.time.7.html), [cron 표 형식](https://manpages.ubuntu.com/manpages/noble/man5/crontab.5.html). 문서 예시의 실제 VM 실행은 별도 검증 대상이다.
