"""109 서버 API 종단 점검 (11-07 Claude). 정문 gw를 거쳐 회원→검색→예약·결제→취소→후기→이벤트를 확인한다.
- 테스트 계정은 X-Synthetic(가상 데이터)으로 만들고 마지막에 탈퇴한다. 비밀번호는 실행마다 새로 만들고 출력하지 않는다.
- 결과는 단계별 PASS/FAIL 한 줄. 개인정보·토큰은 출력하지 않는다.
"""

import os
import secrets
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

BASE = os.environ.get("E2E_BASE", "http://192.168.219.218/api")
KST = timezone(timedelta(hours=9))
SYN = {"X-Synthetic": "1", "X-Synthetic-Key": os.environ["SYNTHETIC_API_KEY"]}
SESSION = str(uuid.uuid4())
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    return ok


c = httpx.Client(base_url=BASE, timeout=20, headers={"X-Session-Id": SESSION})


def call(method, path, token=None, **kw):
    headers = dict(SYN)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return c.request(method, path, headers=headers, **kw)


# 1. 공개 조회
r = c.get("/health")
check("헬스체크", r.status_code == 200 and r.json().get("status") == "ok", r.text[:80])
for p in ("/categories", "/regions", "/facilities", "/venues/new"):
    r = c.get(p)
    check(f"GET {p}", r.status_code == 200)
r = c.get("/venues", params={"category": "studyroom", "sort": "popular", "size": 50})
venues = r.json().get("items", []) if r.status_code == 200 else []
check("검색·정렬(스터디룸 인기순)", r.status_code == 200 and len(venues) > 0, f"{len(venues)}곳")
for sort in ("default", "price", "rating"):
    check(f"정렬 {sort}", c.get("/venues", params={"sort": sort}).status_code == 200)
now = datetime.now(KST)
venue = next((v for v in venues if v.get("close_hour", 23) - v.get("open_hour", 9) >= 4), venues[0])
vid = venue["venue_id"]
detail = c.get(f"/venues/{vid}").json()
check("공간 상세", "min_hours" in detail and detail.get("venue_id") == vid)
mh = detail["min_hours"]
open_h = detail["open_hour"]
check("예약 가능 날짜", c.get(f"/venues/{vid}/available-dates", params={"days": 7}).status_code == 200)


def free_start(day, hours):
    slots = c.get(f"/venues/{vid}/slots", params={"date": day.isoformat()}).json()
    items = slots if isinstance(slots, list) else slots.get("slots", [])
    taken = {s["hour"] for s in items if s.get("taken")}
    for h in range(detail["open_hour"], detail["close_hour"] - hours + 1):
        if all(x not in taken for x in range(h, h + hours)):
            return h
    return None


# 2. 회원
email = f"e2e-{uuid.uuid4().hex[:12]}@example.invalid"
pw = "E2e!" + secrets.token_urlsafe(12)
r = c.get("/auth/email-check", params={"email": email})
check("이메일 중복 확인", r.status_code == 200 and r.json().get("available") is True)
r = call("POST", "/auth/signup", json={
    "email": email, "password": pw, "name": "E2E 점검", "phone": "010-0000-0000", "birth": "000101",
    "gender_digit": "3", "marketing_agreed": False, "terms_agreed": True, "privacy_agreed": True,
})
check("회원가입", r.status_code == 201, str(r.status_code))
r = call("POST", "/auth/login", json={"email": email, "password": pw})
token = r.json().get("access_token") if r.status_code == 200 else None
check("로그인", bool(token), str(r.status_code))
check("내 정보", call("GET", "/users/me", token).status_code == 200)
check("내 정보 수정", call("PATCH", "/users/me", token, json={"marketing_agreed": True}).status_code == 200)

# 3. 예약·결제 (내일, 최소 시간)
tomorrow, h = None, None
for offset in range(1, 30):
    tomorrow = now.date() + timedelta(days=offset)
    h = free_start(tomorrow, mh)
    if h is not None:
        break
body = {"venue_id": vid, "date": tomorrow.isoformat(), "start_hour": h, "hours": mh, "headcount": 1, "method": "card"}
r = call("POST", "/reservations", token, json=body)
rid = r.json().get("reservation_id") if r.status_code == 201 else None
check("예약+모의결제(미래)", r.status_code == 201 and r.json().get("status") == "confirmed", f"{r.status_code} {tomorrow} {h}시 {mh}시간")
r = call("POST", "/reservations", token, json=body)
check("같은 요청 재전송은 기존 예약(200 또는 409)", r.status_code in (200, 409), str(r.status_code))
lst = call("GET", "/reservations/me", token)
check("예약 내역에 바로 보임", lst.status_code == 200 and rid is not None and str(rid) in lst.text)
r = call("GET", f"/reservations/{rid}", token)
check("예약 상세", r.status_code == 200)
r = call("POST", f"/reservations/{rid}/cancel", token)
pay = r.json().get("payment", {}) if r.status_code == 200 else {}
check("예약 취소·환불", r.status_code == 200 and r.json().get("status") == "cancelled" and pay.get("status") == "refunded", str(r.status_code))
check("취소한 칸 다시 예약 가능", free_start(tomorrow, mh) == h)

# 4. 같은 칸 동시 요청 → 1건만 성공
day2, h2 = None, None
for offset in range(2, 30):
    day2 = now.date() + timedelta(days=offset)
    h2 = free_start(day2, mh)
    if h2 is not None:
        break
others = []
for i in range(5):
    e = f"e2e-{uuid.uuid4().hex[:12]}@example.invalid"
    call("POST", "/auth/signup", json={"email": e, "password": pw, "name": "E2E 경합", "phone": "010-0000-0000", "birth": "000101",
         "gender_digit": "4", "marketing_agreed": False, "terms_agreed": True, "privacy_agreed": True})
    t = call("POST", "/auth/login", json={"email": e, "password": pw}).json().get("access_token")
    others.append(t)
rush = {"venue_id": vid, "date": day2.isoformat(), "start_hour": h2, "hours": mh, "headcount": 1, "method": "transfer"}
with ThreadPoolExecutor(5) as pool:
    codes = list(pool.map(lambda t: call("POST", "/reservations", t, json=rush).status_code, others))
check("같은 칸 동시 5건 중 1건만 성공(나머지 409)", codes.count(201) == 1 and codes.count(409) == 4, str(sorted(codes)))

# 5. 지난 시간 예약 → 바로 이용 완료 → 후기
today = now.date()
past_h = None
slots = c.get(f"/venues/{vid}/slots", params={"date": today.isoformat()}).json()
items = slots if isinstance(slots, list) else slots.get("slots", [])
taken = {s["hour"] for s in items if s.get("taken")}
for s in range(open_h, min(now.hour, detail["close_hour"]) - mh + 1):
    if all(x not in taken for x in range(s, s + mh)):
        past_h = s
        break
review_id = None
if past_h is None:
    check("지난 시간 예약(오늘 빈 칸 없음)", False, "건너뜀")
else:
    r = call("POST", "/reservations", token, json={"venue_id": vid, "date": today.isoformat(), "start_hour": past_h, "hours": mh, "headcount": 1, "method": "phone"})
    prid = r.json().get("reservation_id") if r.status_code == 201 else None
    check("지난 시간 예약은 바로 completed", r.status_code == 201 and r.json().get("status") == "completed", str(r.status_code))
    r = call("POST", f"/reservations/{prid}/review", token, json={"rating": 5, "content": "E2E 점검 후기입니다."})
    review_id = r.json().get("review_id") if r.status_code == 201 else None
    check("후기 작성", r.status_code == 201, str(r.status_code))
    check("같은 예약 후기 중복 차단", call("POST", f"/reservations/{prid}/review", token, json={"rating": 4, "content": "중복"}).status_code == 409)
    check("공간 후기 목록에 보임", review_id is not None and str(review_id) in c.get(f"/venues/{vid}/reviews").text)
    check("후기 모아보기", c.get("/reviews", params={"category": detail["category"]["code"], "sort": "recent"}).status_code == 200)
    check("내 후기", str(review_id) in call("GET", "/users/me/reviews", token).text)
    check("후기 수정", call("PATCH", f"/reviews/{review_id}", token, json={"rating": 4, "content": "E2E 수정"}).status_code == 200)
    check("후기 삭제(소프트)", call("DELETE", f"/reviews/{review_id}", token).status_code == 204)

# 6. 이벤트 (FE 형식)
def event(name, product=None, seq=1):
    url = f"http://192.168.219.218/venues/{vid}" if product else "http://192.168.219.218/search"
    return {
        "event_id": str(uuid.uuid4()), "schema_version": 1, "event_name": name, "occurred_at": datetime.now(KST).isoformat(),
        "user": {"anonymous_id": "e2e-anon", "session_id": SESSION, "session_sequence": seq},
        "site": {"site_id": "main", "hostname": "192.168.219.218", "platform": "desktop_web"},
        "acquisition": {"landing_url": "http://192.168.219.218/", "referrer_url": None, "utm_source": None, "utm_medium": None, "utm_campaign": None},
        "page": {"page_view_id": "e2e-page", "page_type": "product_detail" if product else "search_results", "url": url, "path": url[24:], "title": "e2e"},
        "navigation": {"from": None, "to": {"page_view_id": "e2e-page", "site_id": "main", "url": url, "path": url[24:]}, "navigation_type": "direct"},
        "products": [{"product_id": str(product)}] if product else [], "properties": {},
    }
batch = [event("page_view", seq=1), event("product_impression", vid, 2), event("product_section_click", vid, 3), event("product_view", vid, 4)]
r = call("POST", "/events", token, json={"session_id": SESSION, "events": batch})
check("이벤트 4종 수집 202", r.status_code == 202 and r.json().get("accepted") == 4, r.text[:100])

# 7. 정리: 탈퇴
for t in [token, *others]:
    call("DELETE", "/users/me", t, json={"password": pw})
check("탈퇴 후 로그인 불가", call("POST", "/auth/login", json={"email": email, "password": pw}).status_code == 401)
print(f"SESSION {SESSION}")
print(f"합계 {sum(results)}/{len(results)} 통과")
sys.exit(0 if all(results) else 1)
