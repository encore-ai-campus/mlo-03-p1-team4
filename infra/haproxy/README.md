# HAProxy 정문 설정 (담당: B)

1차 로컬 VM 구성의 `gw`에서 사용합니다. 브라우저 요청을 `api1:80`과 `api2:80`의 Nginx로 라운드로빈 분산합니다. 각 VM의 `/etc/hosts`에 `api1`, `api2` 주소를 등록합니다.

- `GET /api/health`를 2초마다 확인하고 두 번 실패하면 해당 서버를 제외합니다. Nginx는 `/api/`를 제거해 FastAPI `/health`로 전달합니다. 기준 문서의 `GET /health` 표기는 현재 Nginx 라우팅과 맞지 않아 확인이 필요합니다.
- `/api/internal`과 `/api/metrics` 및 하위 경로는 정문에서 거절합니다. `/api/internalized`처럼 접두어만 같은 다른 경로는 통과합니다.
- `retries 0`으로 예약·결제 POST를 다른 서버로 다시 보내지 않습니다. HAProxy 접근 로그는 메서드·상태·처리 시간·백엔드만 남기고 요청 경로·쿼리·IP·헤더를 제외합니다.
- `gw:8404/stats`와 `gw:8404/metrics`는 모니터링 VM에서만 접근하도록 `ufw`로 제한합니다. 통계 화면은 인증이 없으므로 공유기 전체에 열지 않습니다.

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
```

서버 장애 시 `/api/health`가 503을 반환하는지와, 한 대를 중지한 뒤 정상 서버로 요청이 가는지는 실제 VM에서 확인해야 합니다.
