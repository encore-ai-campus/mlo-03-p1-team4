# nginx — api VM 공통 설정과 테스트 배포 (담당: B)

이 설정은 #54의 Nginx 정적 파일·API 전달을 담당한다. 프로젝트 기본 구성은 api1·api2 각 VM에 Nginx와 FastAPI를 함께 설치하고, Nginx가 같은 VM의 loopback으로 요청을 전달한다.

```text
브라우저 → gw HAProxy → api1 Nginx → api1 FastAPI (127.0.0.1:8000)
                    └→ api2 Nginx → api2 FastAPI (127.0.0.1:8000)
```

`spacecube_local_api` upstream은 `127.0.0.1:8000`을 사용한다. `keepalive 16`으로 워커당 유휴 연결을 최대 16개 재사용하고, HTTP/1.1과 빈 `Connection` 헤더를 함께 설정한다. `keepalive_timeout 4s`는 테스트 API의 Uvicorn 유휴 만료 5초보다 짧다. 이 풀 크기는 활성 연결 수 제한이 아니다. 근거: [Nginx upstream keepalive](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#keepalive).

## 설치 위치와 기본 사이트

VM 기준은 Ubuntu Server 24.04와 apt 설치다. Nginx 패키지 설정이 `/etc/nginx/conf.d/*.conf`를 `http` 블록 안에서 불러오므로, 이 파일을 api1·api2에 같은 경로로 복사한다.

```text
infra/nginx/spacecube.conf → /etc/nginx/conf.d/spacecube.conf
```

Ubuntu 패키지의 기본 사이트도 `listen 80 default_server`를 사용할 수 있다. 기존 설정을 백업한 뒤 `sites-enabled/default` 링크를 옮기고, 포트 80의 기본 서버가 하나만 남도록 확인한다. `spacecube.conf`의 `server_name _;`와 `default_server`가 호스트 이름이 없거나 일치하지 않는 요청을 받는다.

```bash
backup=/opt/spacecube/backups/nginx-$(date +%Y%m%d)
sudo mkdir -p "$backup"
sudo cp -a /etc/nginx "$backup/nginx"
if [ -L /etc/nginx/sites-enabled/default ]; then
    sudo cp -a /etc/nginx/sites-enabled/default "$backup/sites-enabled-default"
    sudo rm /etc/nginx/sites-enabled/default
fi
```

## Vue 빌드 파일

저장소 루트에서 빌드한다. 생성된 `frontend/dist/` 전체를 api1과 api2 각각의 `/var/www/frontend/`에 복사한다.

```bash
npm --prefix frontend run build
release=/opt/spacecube/releases/fda86e7/frontend
sudo install -d -o root -g root -m 0755 "$release"
sudo cp -a frontend/dist/. "$release/"
sudo ln -s "$release" /var/www/frontend
```

해시가 붙은 `/assets/` 파일은 1년 캐시하고, `/index.html`은 재검증하도록 `no-cache`를 보낸다. `/photos/`는 실제 파일만 응답하고 없는 파일을 Vue 화면으로 넘기지 않는다. `.webp`는 7일 캐시하며 해당 location에 `image/webp` MIME을 명시한다. 사진 안내 문서는 기본 캐시 정책을 따른다. `/assets/`의 `expires`와 `add_header`는 각각 Cache-Control 필드를 보낼 수 있으므로 두 필드를 합쳐 판정한다. 근거: [Nginx 응답 헤더](https://nginx.org/en/docs/http/ngx_http_headers_module.html#expires).

## 경로와 접근 경계

| 요청 경로 | 처리 |
| --- | --- |
| `/`와 Vue 화면 경로 | `/var/www/frontend` 파일, 없으면 `index.html` |
| `/assets/*` | 정적 파일, 없으면 404 |
| `/photos/*` | 정적 파일만 제공, 없으면 404. `.webp`는 7일 캐시 |
| `/api/health` | 독립 헬스 프로세스 `127.0.0.1:8001/health`로 전달 |
| 나머지 `/api/*` | 같은 VM의 업무 API `127.0.0.1:8000`으로 전달 |
| `/api/internal`, `/api/internal/*` | 404 `NOT_FOUND` |
| `/api/metrics`, `/api/metrics/*` | 404 `NOT_FOUND` |
| 외부 `/stub_status` | 404 `NOT_FOUND` |
| `127.0.0.1:8080/stub_status` | 로컬 nginx exporter용 `stub_status`; 루프백에서만 접근 가능 |

HAProxy도 `/api/internal`과 `/api/metrics`를 차단한다. Nginx의 차단은 정문 설정을 우회했을 때의 추가 경계다. FastAPI 오류 본문은 Nginx가 가공하지 않으며, Nginx와 FastAPI 사이의 연결 실패는 FastAPI 라우트의 오류가 아니다.

FastAPI의 `/metrics`는 공개 포트 80으로 전달하지 않는다. FastAPI는 loopback에 바인딩하고, 모니터링 경로는 이 테스트 배포 범위가 아니다.

전달 헤더는 HAProxy를 유일한 외부 진입점으로 둔 현재 구조에 맞춘다. Nginx가 보는 `$remote_addr`와 `X-Real-IP`는 바로 앞의 `gw` 주소이며, `X-Forwarded-For`에는 기존 체인에 그 주소를 덧붙인다. 브라우저 원 IP가 필요한 소비자는 HAProxy가 클라이언트 제공 `X-Forwarded-For`를 정리한 뒤 체인을 설정하는지 확인해야 한다. 현재 VM 흐름은 HTTP라 `X-Forwarded-Proto`에는 Nginx가 받은 scheme을 전달한다. `Authorization`, `X-Session-Id`, `X-Synthetic`, `X-Synthetic-Key` 등 나머지 요청 헤더는 기본 동작으로 전달된다.

## 접근 로그와 진단

JSON 접근 로그에는 시각·요청 ID·메서드·상태·처리 시간·upstream 상태만 기록한다. URI, 쿼리 문자열, IP, 요청 헤더, 토큰, 본문은 기록하지 않는다. `error_log /dev/null`은 Nginx 오류 로그가 요청 원문을 포함할 수 있어 꺼 두었다. 따라서 upstream 실패의 상세 메시지는 남지 않고, 상태 코드·upstream 지표·FastAPI 로그로 확인한다. 로컬 `stub_status`는 Alloy가 보내는 nginx exporter 지표의 원본이다.

PR #66 후속 헬스 분리는 [HAProxy README](../haproxy/README.md)의 독립 헬스 프로세스를 사용한다. 8001 프로세스 없이 이 설정을 적용하면 헬스 경로는 502가 된다. 2026-11-07 자체 구성 테스트 VM에서 재배포하고 #67 정적·캐시 확인과 함께 검사했다.

## 설정 검사

VM에 파일을 복사하고 기본 사이트 중복을 확인한 뒤 문법을 검사한다. 이 명령은 설정을 적용하거나 서비스를 재시작하지 않는다.

```bash
sudo nginx -t
```

문법 검사 통과 후 `sudo systemctl reload nginx`로 적용한다. 이 저장소의 테스트 VM 배포는 이 절차를 거쳐 적용했다.

## PR #67 적용 후 확인

각 api VM에서 수행한다. 파일명은 배포된 빌드에 존재하는 경로를 골라 사용한다.

```bash
# 각 VM 안에서 실행한다. 접근 로그에 검색어나 인증정보를 넣지 않는다.
asset=$(find /var/www/frontend/assets -maxdepth 1 -type f -name '*.js' -printf '%f\n' | head -n 1)
photo=$(find /var/www/frontend/photos -type f -name '*.webp' -printf '%P\n' | head -n 1)
test -n "$asset" && curl -sSI "http://127.0.0.1/assets/$asset"
test -n "$photo" && curl -sSI "http://127.0.0.1/photos/$photo"
curl -sSI http://127.0.0.1/index.html
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/photos/not-present.webp
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/assets/not-present.js
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/internal/venues
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/metrics
curl -sS http://127.0.0.1:8080/stub_status
```

| 항목 | 기대 결과 |
| --- | --- |
| `/assets/<파일>.js` | 200, Cache-Control에 `max-age=31536000`·`public`·`immutable` |
| `/photos/<파일>.webp` | 200, `Content-Type: image/webp`, `max-age=604800` |
| `/index.html` | 200, `Cache-Control: no-cache` |
| 없는 사진·asset | 404, SPA HTML이나 장기 캐시 헤더 없음 |
| `/api/health` | 200, FastAPI `/health` 응답 |
| 내부 API·metrics | 404 |
| loopback `stub_status` | 200, Nginx 상태 본문 |

keepalive는 `sudo nginx -T`로 풀·HTTP 버전·Connection 헤더 설정을 확인하고, `/api/health`를 연속 호출한 뒤 `ss -ntp state established`에서 loopback 8000번 연결이 유휴 상태로 남는지 확인한다.

HAProxy 정문·통계·서버 제외/복귀는 2026-11-07 자체 구성 테스트 VM에서 확인했다. 결과와 한계는 [HAProxy 시험 기록](../haproxy/README.md)에 적었다.

## 이전 후보안 검증 기록 (d715a6a)

아래 결과는 keepalive 풀·WebP MIME 보완 전 설정의 기록이다. 현재 수정본의 `nginx -t`·HTTP 검증 결과로 대신하지 않는다.

- `git diff --check`: 추적 중인 수정 파일 통과.
- 정적 확인: 새 `spacecube.conf`를 포함한 수정 파일에 끝 공백이 없고, 필수 경로·접근 경계·loopback 전달·로그 필드가 맞는지 확인해 통과.
- `nginx -t`: 사용자 제공 Ubuntu 24.04.4 VM의 Nginx 1.24.0에서 통과(exit 0). 원본 후보 파일의 SHA256 일치를 확인하고 `/tmp`의 별도 최상위 설정에서 include해 검사했다. 후보의 포트·경로·upstream은 치환하지 않았다. 기존 운영 설정 전체와의 충돌 검사는 별도다. 임시 파일 정리 완료, 서비스 적용·reload 없음.
- HTTP 요청, `api1`·`api2` 실제 파일 배포, HAProxy 연동: 미검증.

- 커밋 전 전체 검증: Ruff 린트·90파일 포맷·pytest 362건 통과(경고 1). 프론트 verify는 이 워크트리의 의존성 미설치로 run-s를 찾지 못해 실패해 전체 verify.ps1은 exit 1. 프론트 코드 변경 없음.

## 로컬 코드 검증 기록 (fda86e7, 2026-11-07)

- develop 1583778 통합 및 STATE 충돌 해결.
- verify.ps1 전체 통과(exit 0): Ruff 린트·115파일 포맷, pytest 451건, FE 단위 67건·린트·색 검사·빌드. 기존 Starlette 사용 중단 경고와 FE 조건문 린트 경고 각 1건.
- git diff --check 통과.
- 이 커밋 시점에는 Windows에 Nginx 실행 환경이 없어 새 설정의 nginx -t·HTTP 검증을 하지 않았다. 아래 분리 VM 배포에서 수정본 검증을 완료했다.

## 이전 분리 배치 기록 (2026-11-07)

아래는 Nginx와 FastAPI를 다른 VM에 둔 초기 사전 시험 기록이다. 현재 시험 구성은 api1·api2 동배치이며, 아래 `동배치 재배포` 절의 상태가 최신이다.

| 역할 | 주소 | 설치·설정 |
| --- | --- | --- |
| 이전 Nginx 호스트 | `192.168.0.232` | Nginx 1.24.0, `/etc/nginx/conf.d/spacecube.conf`, `api-backend → 192.168.0.234`, 프론트 릴리스 |
| 이전 Nginx 호스트 | `192.168.0.233` | Nginx 1.24.0, 같은 설정, `api-backend → 192.168.0.235`, 프론트 릴리스 |
| 이전 API 호스트 | `192.168.0.234` | Python 3.12 venv, FastAPI 0.162.0/Uvicorn 0.54.0 등 `environment.yml` 런타임 핀, `spacecube-api.service`, workers 2·동시성 100·유휴 연결 5초 |
| 이전 API 호스트 | `192.168.0.235` | 같은 코드·패키지·서비스 설정, 별도 `SERVER_NAME`·bind IP |
| MariaDB primary | `192.168.0.212` | SSH 접속·DDL·쓰기 없음. API에서 `spacecube` 연결과 읽기 조회만 확인 |

FastAPI 설정 비밀값은 저장소나 평문 `.env`에 두지 않는다. systemd credential host key를 VM별로 만들고, API 설정은 `/etc/credstore.encrypted/spacecube-backend.cred`에 암호화해 둔다. 서비스는 `LoadCredentialEncrypted`로 `/run/credentials`에 읽기 전용으로 받아 `start-api.sh`가 환경변수로 적재한다. 이 API credential에는 primary DB 연결, JWT·내부 API·가상 데이터 키가 있다. 값은 로그·기록에 넣지 않는다. `MONGO_URL`은 제공되지 않아 비워 두었으며 이벤트 MongoDB 상태는 down/degraded로 표시된다.

API 배포 파일은 `/opt/spacecube/releases/fda86e7/backend.tar.gz`, `/opt/spacecube/deploy/requirements-api.txt`, `/opt/spacecube/deploy/start-api.sh`에 남아 있다. 서비스는 부팅 때 자동 시작한다. Nginx 원 설정과 기존 `/var/www/html`·기본 사이트 링크는 각 VM의 `/opt/spacecube/backups/pr67-before-20261107/` 아래에 보존했다.

### 당시 분리 배치 확인 결과

- api1·api2 각각 `systemd-analyze verify` 통과, `spacecube-api` active, `/health`와 읽기 전용 `/categories`가 200. `/health`는 `{"status":"degraded","mongo":"down"}`이며 MariaDB primary 상태는 정상이다.
- 당시 Nginx 호스트 `.232`·`.233` 각각 `nginx -t` 통과, reload 후 active. 홈페이지 200, `/assets/*.js` 200·1년 immutable, WebP 200·`image/webp`·7일, `/index.html` no-cache, 없는 asset·사진 404, 내부 API·공개 metrics 404.
- 두 Nginx에서 API health 8회 연속 호출 후 `ss`로 짝 API의 유휴 TCP keepalive 연결을 확인했다.
- 당시 별도 API 호스트 `.234`를 잠시 중지했을 때 Nginx 호스트 `.232`의 `/api/health`는 502, `.233`의 응답은 200이었다. `.234` 복구 뒤 양쪽 health가 다시 200이다. 이는 HAProxy 장애 제외·복귀 시험이 아니다.
- MariaDB 연결을 검증하며 실행한 업무 쿼리는 health 확인과 `GET /categories`뿐이다. 스키마 변경·INSERT·SSH는 하지 않았다.
- HAProxy VM은 이 브랜치에 설정이 없어 변경·적용하지 않았다. api1 직접 중지 확인은 HAProxy 시험이 아니며, #66 정문 분산·장애 제외/복귀 검증에 포함하지 않는다.

## 동배치 재배포 (2026-11-07)

| VM | 주소 | 설치·설정 |
| --- | --- | --- |
| api1 | `192.168.0.232` | Nginx 1.24.0 + FastAPI 0.162.0, Uvicorn 0.54.0, 프론트 `e7db36f`, upstream `127.0.0.1:8000` |
| api2 | `192.168.0.233` | api1과 같은 Nginx·FastAPI·프론트 구성, upstream `127.0.0.1:8000` |
| gw | `192.168.0.231` | HAProxy는 이 배포에서 변경·시험하지 않음 |
| MariaDB primary | `192.168.0.212` | 원격 서비스로만 사용. SSH·DDL·쓰기 없음 |

develop `e7db36f` 병합 뒤 최신 프론트 빌드를 `/opt/spacecube/releases/e7db36f/frontend`에 배포해 `/var/www/frontend` symlink를 갱신했다. 이전 `fda86e7` 프론트 릴리스는 보존하고, 교체 전 symlink는 백업 디렉터리에 남겼다. 기존 분리 시험의 `.234`·`.235` API 설치와 서비스는 변경하지 않았다. 현재 api1·api2 Nginx는 같은 VM의 loopback FastAPI로 연결한다. 각 VM의 백엔드 릴리스는 `/opt/spacecube/releases/fda86e7/backend`, 가상환경은 `/opt/spacecube/venv`, 배포 스크립트·요구사항은 `/opt/spacecube/deploy/`에 둔다. 서비스는 부팅 시 자동 시작한다.

이 시험에서는 FastAPI를 loopback에만 바인딩했고 api1·api2의 UFW는 비활성 상태다. 따라서 Nginx 로컬 프록시는 확인했지만, 원격 `mon`의 8000번 `/metrics` 수집과 UFW 허용 규칙은 #15에서 별도로 맞춰야 한다.

재배포 직전 Nginx 설정과 `/etc/hosts`는 `/opt/spacecube/backups/pr67-before-colocated-20261107/`에 백업했다. 기본 사이트·`/var/www/html`의 기존 백업은 이전 배포의 `/opt/spacecube/backups/pr67-before-20261107/` 아래에 보존했다.

DB·JWT·내부 API·가상 데이터 키는 VM별 systemd host credential로 암호화해 `/etc/credstore.encrypted/spacecube-backend.cred`에 저장한다. 평문 임시 credential은 암호화 후 제거했다. 두 API는 검증을 위해 같은 JWT·내부 API·가상 데이터 키를 사용한다. `MONGO_URL`은 제공되지 않아 health 응답은 HTTP 200, 본문 `degraded`/`mongo: down`이다.

### 동배치 확인 결과

- api1·api2 각각 `systemd-analyze verify` 통과, `spacecube-api` active, Uvicorn은 `127.0.0.1:8000`에만 listen한다.
- 각 VM에서 `/api/health` 200, 읽기 전용 `/api/categories` 200(198 bytes). MariaDB primary에는 health 확인과 `GET /categories`만 실행했다.
- 작업 PC에서 api1·api2의 `/`, `/venues`, `/api/health`를 직접 요청해 모두 200을 확인했다.
- 최신 프론트 빌드의 `AuthPage-ChvXJtYP.js`도 두 VM에서 200·1년 immutable로 응답한다.
- 두 VM 모두 `nginx -t` 통과 후 reload·active. `/`·`/venues` 200, `/assets/*.js` 200·1년 immutable, WebP 200·`image/webp`·7일, `/index.html` no-cache.
- 없는 asset·사진, 공개 `/stub_status`, `/api/internal/*`, `/api/metrics`는 404. loopback `127.0.0.1:8080/stub_status`는 200.
- 각 VM에서 `/api/health` 8회 호출 후 `ss`로 loopback 8000번 유휴 keepalive 연결 1개를 확인했다.
- 접근 로그는 `/var/log/nginx/spacecube_access.log`. 실제 JSON 필드는 시각·요청 ID·메서드·상태·처리 시간·upstream 주소·상태·응답 시간이며, URI·쿼리·IP·요청 헤더·토큰·본문은 기록하지 않는다.
- 최신 develop `e7db36f` 병합 후 `verify.ps1` 통과: Ruff, pytest 451건, 프론트 린트·색상 검사·단위 67건·빌드. 기존 Starlette deprecation 및 Playwright conditional-test 린트 경고 각 1건. E2E는 미실행.
- HAProxy 장애 제외·복귀 시험은 #66에서 진행한다.
