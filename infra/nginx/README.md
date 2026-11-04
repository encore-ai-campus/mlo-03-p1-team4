# nginx — 리버스 프록시 (담당: B)

지금 설계는 Nginx EC2(public-a, 탄력적 IP) 한 대가 받아 FastAPI 두 대로 나눠 보냅니다. 무료 Nginx는 수동 헬스체크만 되고 한 대라 단일 장애점입니다.

> **1차 (11-03 방향: 먼저 띄우고 잰 뒤 더함):** 이 Nginx 한 대를 그대로 쓰고 아래 '1차 보강'만 넣는다. ALB·HAProxy 교체는 띄운 뒤 조건을 넘을 때(`docs/인프라_트래픽_안정성_검토.md` 1-1절, `STATE.md` B1).
> - 교체할 때 A안(권장): ALB가 받고 앱 서버마다 Nginx(`upstream`을 `127.0.0.1:8000` 하나로), ALB 헬스체크 `/api/health`.
> - B안: 이 자리를 HAProxy로(`option httpchk GET /health`, `balance leastconn`, 서버별 `maxconn 50`, 통계·Prometheus 지표). 정적 파일은 Nginx가 따로.

### 1차 보강 (아래 초안에 넣음)

```nginx
upstream fastapi {
    server 10.11.1.11:8000 max_fails=2 fail_timeout=10s;
    server 10.11.2.11:8000 max_fails=2 fail_timeout=10s;
    keepalive 16;
}
# location /api/ 안에
proxy_connect_timeout 2s;          # 죽은 서버를 오래 기다리지 않음
proxy_read_timeout 30s;
proxy_next_upstream error timeout http_502 http_503;   # GET 등 안전한 요청만 다른 서버로 다시 보냄(POST는 다시 보내지 않음)
proxy_next_upstream_tries 2;
proxy_http_version 1.1;
proxy_set_header Connection "";
# 정적 파일: location /assets/ { expires 1y; add_header Cache-Control "public, immutable"; }
```

## 설정 초안 (`spacecube.conf`, 팀원 n번은 10.1n으로 바꿈)

```nginx
upstream fastapi {
    server 10.11.1.11:8000 max_fails=3 fail_timeout=10s;   # FastAPI #1
    server 10.11.2.11:8000 max_fails=3 fail_timeout=10s;   # FastAPI #2
}

server {
    listen 80;
    server_name _;

    location /api/ {
        proxy_pass http://fastapi/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/internal/ {
        deny all;          # 크롤러는 VPC 안에서 FastAPI로 직접 호출
    }

    location /api/metrics {
        deny all;          # Prometheus는 모니터링 EC2에서 FastAPI:8000으로 직접 긁음
    }

    location / {
        root /var/www/frontend;          # Vue 빌드 결과 (frontend/dist)
        try_files $uri /index.html;
    }
}
```

## 할 일

- [ ] HTTPS: 도메인을 쓸지 정하고, 쓰면 Let's Encrypt 인증서
- [ ] 헬스체크: `/health`가 primary 끊김이면 503, replica·MongoDB 끊김이면 200 degraded(백엔드_A 5-6). 오픈소스 Nginx는 실패한 요청으로만 서버를 빼므로(`max_fails`), `GET /health`를 주기적으로 확인하는 스크립트를 둘지 결정
- [ ] 접근 로그를 JSON 형식으로 남겨 Alloy → Loki로 보내기, nginx exporter(`infra/monitoring`)
- [x] 프론트는 `/`, API는 `/api/`로 나눔(11-01 확인). 위 `proxy_pass http://fastapi/;`의 끝 `/`가 `/api`를 떼고 넘기므로 FastAPI 경로는 `/venues`처럼 접두사 없이 만든다. 개발 서버도 같은 방식(`frontend/vite.config.js`의 `rewrite`)
