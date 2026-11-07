# nginx — api VM 공통 후보 설정 (담당: B)

이 문서는 #54와 [`docs/로컬_VM_구성.md`](../../docs/로컬_VM_구성.md)의 11-06 B안에 맞춘 **검토용 후보안**이다. 실제 `api1`·`api2`에는 적용하지 않았다.

```text
브라우저 → gw HAProxy:80 → api1 또는 api2 Nginx:80 → 해당 VM의 FastAPI 127.0.0.1:8000
```

HAProxy가 서버 선택과 `/api/health` 확인을 담당한다. 각 VM의 Nginx는 Vue 파일 제공과 로컬 FastAPI 전달만 맡으며, api1·api2를 upstream으로 두거나 다른 VM으로 재시도하지 않는다.

로컬 `spacecube_local_api` upstream은 `127.0.0.1:8000` 하나만 사용한다. `keepalive 16`으로 워커당 유휴 연결을 최대 16개 재사용하고, HTTP/1.1과 빈 `Connection` 헤더를 함께 설정한다. `keepalive_timeout 4s`는 Uvicorn 기본 유휴 만료 5초보다 짧다. 실제 Uvicorn 설정이 더 짧으면 Nginx 쪽도 맞춰야 한다. 이 풀 크기는 활성 연결 수 제한이 아니다. 근거: [Nginx upstream keepalive](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#keepalive).

## 설치 위치와 기본 사이트

로컬 VM 기준은 Ubuntu Server 24.04와 apt 설치다. Nginx 패키지 설정이 `/etc/nginx/conf.d/*.conf`를 `http` 블록 안에서 불러오므로, 이 파일을 두 서버에 같은 경로로 복사한다.

```text
infra/nginx/spacecube.conf → /etc/nginx/conf.d/spacecube.conf
```

Ubuntu 패키지의 기본 사이트도 `listen 80 default_server`를 사용할 수 있다. `sites-enabled/default` 링크가 있으면 비활성화하고, 포트 80의 기본 서버가 하나만 남도록 확인한다. `spacecube.conf`의 `server_name _;`와 `default_server`가 호스트 이름이 없거나 일치하지 않는 요청을 받는다.

```bash
if [ -L /etc/nginx/sites-enabled/default ]; then
    sudo unlink /etc/nginx/sites-enabled/default
fi
```

## Vue 빌드 파일

저장소 루트에서 빌드한다. 생성된 `frontend/dist/` 전체를 api1과 api2 각각의 `/var/www/frontend/`에 복사한다.

```bash
npm --prefix frontend run build
sudo install -d -o root -g root -m 0755 /var/www/frontend
sudo cp -a /tmp/spacecube-dist/. /var/www/frontend/
```

`/tmp/spacecube-dist/`는 각 VM으로 전송한 `frontend/dist/` 내용의 임시 위치다. 해시가 붙은 `/assets/` 파일은 1년 캐시하고, `/index.html`은 재검증하도록 `no-cache`를 보낸다. `/photos/`는 실제 파일만 응답하고 없는 파일을 Vue 화면으로 넘기지 않는다. `.webp`는 7일 캐시하며 해당 location에 `image/webp` MIME을 명시한다. 사진 안내 문서는 기본 캐시 정책을 따른다. `/assets/`의 `expires`와 `add_header`는 각각 Cache-Control 필드를 보낼 수 있으므로 두 필드를 합쳐 판정한다. 근거: [Nginx 응답 헤더](https://nginx.org/en/docs/http/ngx_http_headers_module.html#expires).

## 경로와 접근 경계

| 요청 경로 | 처리 |
| --- | --- |
| `/`와 Vue 화면 경로 | `/var/www/frontend` 파일, 없으면 `index.html` |
| `/assets/*` | 정적 파일, 없으면 404 |
| `/photos/*` | 정적 파일만 제공, 없으면 404. `.webp`는 7일 캐시 |
| `/api/*` | 같은 VM의 `127.0.0.1:8000`으로 전달. `/api/health`는 FastAPI `/health`가 됨 |
| `/api/internal`, `/api/internal/*` | 404 `NOT_FOUND` |
| `/api/metrics`, `/api/metrics/*` | 404 `NOT_FOUND` |
| 외부 `/stub_status` | 404 `NOT_FOUND` |
| `127.0.0.1:8080/stub_status` | 로컬 nginx exporter용 `stub_status`; 루프백에서만 접근 가능 |

HAProxy도 `/api/internal`과 `/api/metrics`를 차단한다. Nginx의 차단은 정문 설정을 우회했을 때의 추가 경계다. FastAPI 오류 본문은 Nginx가 가공하지 않으며, Nginx와 FastAPI 사이의 연결 실패는 FastAPI 라우트의 오류가 아니다.

FastAPI의 `/metrics`는 공개 포트 80으로 전달하지 않는다. API 프로세스가 `127.0.0.1:8000`에만 바인딩된다는 구조와 모니터링 VM `mon`이 서버의 8000 포트를 직접 읽는 방화벽 표기가 함께 있다. 루프백 바인딩이면 원격 `mon`은 접속할 수 없으므로, 실제 배포 전에는 각 API VM의 로컬 Alloy가 scrape하는 방식인지 모니터링 경로를 확인해야 한다. 이 후보안은 Nginx에서 포트 8000을 외부에 열지 않는다.

전달 헤더는 HAProxy를 유일한 외부 진입점으로 둔 현재 구조에 맞춘다. Nginx가 보는 `$remote_addr`와 `X-Real-IP`는 바로 앞의 `gw` 주소이며, `X-Forwarded-For`에는 기존 체인에 그 주소를 덧붙인다. 브라우저 원 IP가 필요한 소비자는 HAProxy가 클라이언트 제공 `X-Forwarded-For`를 정리한 뒤 체인을 설정하는지 확인해야 한다. 현재 VM 흐름은 HTTP라 `X-Forwarded-Proto`에는 Nginx가 받은 scheme을 전달한다. `Authorization`, `X-Session-Id`, `X-Synthetic`, `X-Synthetic-Key` 등 나머지 요청 헤더는 기본 동작으로 전달된다.

## 접근 로그와 진단

JSON 접근 로그에는 시각·요청 ID·메서드·상태·처리 시간·upstream 상태만 기록한다. URI, 쿼리 문자열, IP, 요청 헤더, 토큰, 본문은 기록하지 않는다. `error_log /dev/null`은 Nginx 오류 로그가 요청 원문을 포함할 수 있어 꺼 두었다. 따라서 upstream 실패의 상세 메시지는 남지 않고, 상태 코드·upstream 지표·FastAPI 로그로 확인한다. 로컬 `stub_status`는 Alloy가 보내는 nginx exporter 지표의 원본이다.

## 설정 검사

VM에 파일을 복사하고 기본 사이트 중복을 확인한 뒤 문법을 검사한다. 이 명령은 설정을 적용하거나 서비스를 재시작하지 않는다.

```bash
sudo nginx -t
```

문법 검사 통과 후 실제 적용은 VM 소유자가 한다. 이번 작업에서는 서버 적용이나 reload를 하지 않았다.

## PR #67 적용 후 확인

각 VM 소유자가 설정·빌드를 배치하고 `sudo nginx -t` 통과 후 reload한다. 다음 검사는 **api1·api2 각각**에서 수행하고 응답 헤더와 검사 시각을 남긴다. 파일명은 배포된 빌드에 존재하는 경로를 골라 사용한다.

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

keepalive는 `sudo nginx -T`로 풀·HTTP 버전·Connection 헤더 설정을 확인한 뒤, 다른 트래픽을 배제한 상태에서 `/api/health`를 연속 호출하고 `ss -ntp`의 로컬 8000 연결이 재사용되는지 확인한다. `nginx -t` 통과만으로 실제 연결 재사용을 검증했다고 기록하지 않는다.

정문 검증은 #66 담당자·각 VM 소유자와 함께 진행한다. `gw`에서 두 서버 정상 응답과 내부 API 차단을 확인한 뒤 api2 중단·복구 시 HAProxy 제외(4초 이내)·재편입을 확인한다. 노트북 종료·오류율·중복 예약 시험은 #54 완료 조건과 A7(#16)에 따른다. 두 서버 적용과 장애 시험이 끝나기 전에는 PR #67을 Draft로 유지한다.

## 이전 후보안 검증 기록 (d715a6a)

아래 결과는 keepalive 풀·WebP MIME 보완 전 설정의 기록이다. 현재 수정본의 `nginx -t`·HTTP 검증 결과로 대신하지 않는다.

- `git diff --check`: 추적 중인 수정 파일 통과.
- 정적 확인: 새 `spacecube.conf`를 포함한 수정 파일에 끝 공백이 없고, 필수 경로·접근 경계·loopback 전달·로그 필드가 맞는지 확인해 통과.
- `nginx -t`: 사용자 제공 Ubuntu 24.04.4 VM의 Nginx 1.24.0에서 통과(exit 0). 원본 후보 파일의 SHA256 일치를 확인하고 `/tmp`의 별도 최상위 설정에서 include해 검사했다. 후보의 포트·경로·upstream은 치환하지 않았다. 기존 운영 설정 전체와의 충돌 검사는 별도다. 임시 파일 정리 완료, 서비스 적용·reload 없음.
- HTTP 요청, `api1`·`api2` 실제 파일 배포, HAProxy 연동: 미검증.

- 커밋 전 전체 검증: Ruff 린트·90파일 포맷·pytest 362건 통과(경고 1). 프론트 verify는 이 워크트리의 의존성 미설치로 run-s를 찾지 못해 실패해 전체 verify.ps1은 exit 1. 프론트 코드 변경 없음.

## PR #67 후속 수정 로컬 검증 (2026-11-07)

- develop 1583778 통합 및 STATE 충돌 해결.
- verify.ps1 전체 통과(exit 0): Ruff 린트·115파일 포맷, pytest 451건, FE 단위 67건·린트·색 검사·빌드. 기존 Starlette 사용 중단 경고와 FE 조건문 린트 경고 각 1건.
- git diff --check 통과.
- Windows에 Nginx 실행 환경이 없어 수정본 nginx -t·HTTP 캐시/MIME/keepalive 검증은 미실행. api1·api2 실적용·HAProxy 장애 시험·브라우저 E2E도 미실행.
- 실제 SSH 접속 정보와 각 VM 소유자의 적용 가능 여부를 확인한 뒤 위 절차로 검증하고 Ready로 전환한다.
