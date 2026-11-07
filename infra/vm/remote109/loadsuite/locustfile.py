"""F-12~60: 전용 합성 계정·시간 자원으로 실행하는 실제 HTTP 시나리오."""

import itertools
import json
import os
import random
import time
from pathlib import Path
from uuid import uuid4

import gevent
from locust import HttpUser, between, events, task
from locust.exception import StopUser
from logic import build_event_batch, check_reservation, classify_status

FIXTURE = json.loads(Path(os.environ["SPACE_FIXTURE"]).read_text(encoding="utf-8"))
MODE = os.environ["SPACE_MODE"]
REPORT = Path(os.environ["SPACE_RUN_DIR"])
BOOT = time.time()
READY = None
WARMUP = float(os.environ.get("SPACE_WARMUP", "10"))
MEASURE = float(os.environ.get("SPACE_MEASURE", "60"))
COUNTERS = {}
REQUESTS = (REPORT / "requests.jsonl").open("w", encoding="utf-8", buffering=1)
TRANSACTIONS = (REPORT / "transactions.jsonl").open("w", encoding="utf-8", buffering=1)


def emit_transaction(kind, **fields):
    TRANSACTIONS.write(json.dumps({"time": time.time(), "kind": kind, **fields}) + "\n")


def phase(started, finished):
    if READY is None:
        return "ramp"
    if started >= READY + WARMUP and finished <= READY + WARMUP + MEASURE:
        return "measure"
    return "warmup" if finished < READY + WARMUP else "boundary_or_drain"


@events.spawning_complete.add_listener
def spawning_complete(user_count, **_kwargs):
    global READY
    if READY is None:
        READY = time.time()
        (REPORT / "phase.json").write_text(
            json.dumps(
                {
                    "spawned": user_count,
                    "ready": READY,
                    "measurement_start": READY + WARMUP,
                    "measurement_end": READY + WARMUP + MEASURE,
                }
            ),
            encoding="utf-8",
        )
        gevent.spawn_later(WARMUP + MEASURE, active_environment.runner.quit)


active_environment = None


@events.init.add_listener
def initialize(environment, **_kwargs):
    global active_environment
    active_environment = environment


@events.request.add_listener
def request_record(
    request_type,
    name,
    response_time,
    response_length,
    response=None,
    exception=None,
    context=None,
    start_time=None,
    **_kwargs,
):
    context = context or {}
    finished = time.time()
    started = start_time if start_time is not None else finished - response_time / 1000
    REQUESTS.write(
        json.dumps(
            {
                "started": started,
                "finished": finished,
                "method": request_type,
                "name": name,
                "ms": response_time,
                "bytes": response_length,
                "status": response.status_code if response is not None else 0,
                "code": context.get("code"),
                "verdict": context.get("verdict", "availability" if exception else "ok"),
                "failed": exception is not None,
                "phase": "setup" if context.get("setup") else phase(started, finished),
                "request_id": response.headers.get("X-Request-Id")
                if response is not None
                else None,
            }
        )
        + "\n"
    )
    if exception is not None and not (REPORT / "abort.json").exists():
        # 준비/예열 실패도 본 측정 전에 중단한다. 본문·토큰은 기록하지 않는다.
        (REPORT / "abort.json").write_text(
            json.dumps(
                {
                    "time": finished,
                    "method": request_type,
                    "name": name,
                    "phase": "setup" if context.get("setup") else phase(started, finished),
                    "status": response.status_code if response is not None else 0,
                }
            ),
            encoding="utf-8",
        )
        gevent.spawn(active_environment.runner.quit)


class ScenarioUser(HttpUser):
    abstract = True
    wait_time = between(1, 5)
    weight = 1

    def on_start(self):
        self.session_id = str(uuid4())
        self.client.headers.update(
            {
                "X-Synthetic": "1",
                "X-Synthetic-Key": os.environ["SPACE_SYNTHETIC_KEY"],
                "X-Session-Id": self.session_id,
            }
        )
        self.pending = set()
        self.account = None
        self.review_pool = []
        self.book_cursor = 0
        self.event_sequence = 1
        if MODE not in {"public", "events"} and type(self).__name__ != "Browser":
            offset = 45 if type(self).__name__ == "Reviewer" and MODE == "mixed" else 0
            iterator = COUNTERS.setdefault(type(self).__name__, itertools.count())
            index = offset + next(iterator)
            if index >= len(FIXTURE["accounts"]):
                emit_transaction("fixture_exhausted", scope="account")
                raise StopUser
            self.account = FIXTURE["accounts"][index]
            token = self.call(
                "POST",
                "/auth/login",
                {200},
                json={
                    "email": f"{FIXTURE['email_prefix']}.{index}@load.invalid",
                    "password": os.environ["SPACE_ACCOUNT_PASSWORD"],
                },
                setup=True,
            )
            if not token or not token.get("access_token"):
                raise StopUser
            self.client.headers["Authorization"] = "Bearer " + token["access_token"]
            if MODE in {"review", "mixed"}:
                data = self.call(
                    "GET",
                    "/reservations/me",
                    {200},
                    params={"status": "completed", "size": 50},
                    setup=True,
                )
                self.review_pool = [
                    x["reservation_id"]
                    for x in (data or {}).get("items", [])
                    if x["review_id"] is None
                    and x["reservation_id"] in self.account["review_fixtures"]
                ]

    def call(
        self,
        method,
        route,
        statuses,
        *,
        name=None,
        expected=None,
        validate=None,
        setup=False,
        **kwargs,
    ):
        context = {"setup": setup}
        with self.client.request(
            method,
            "/api" + route,
            name=name or route,
            catch_response=True,
            context=context,
            timeout=(5, 20),
            **kwargs,
        ) as response:
            context = response.request_meta["context"]
            try:
                data = response.json() if response.content else {}
            except ValueError:
                data = {}
                response.failure("invalid_json")
                context["verdict"] = (
                    "availability"
                    if response.status_code == 0 or response.status_code >= 500
                    else "contract"
                )
                return None
            code = data.get("code") if isinstance(data, dict) else None
            context.update(
                code=code, verdict=classify_status(response.status_code, code, expected or {})
            )
            if context["verdict"] == "expected":
                response.success()
                return data
            if response.status_code not in statuses:
                response.failure(f"HTTP_{response.status_code}_{code or 'no_code'}")
                if context["verdict"] == "ok":
                    context["verdict"] = "contract"
                return None
            try:
                if (
                    method == "GET"
                    and route
                    in {
                        "/venues",
                        "/venues/new",
                        "/reviews",
                        "/reservations/me",
                        "/users/me/reviews",
                    }
                    and not {"items", "page", "size", "total"}.issubset(data)
                ):
                    raise ValueError("page_shape")
                if validate:
                    validate(data)
            except (ValueError, KeyError, TypeError) as error:
                context["verdict"] = "contract"
                response.failure("contract_" + str(error)[:60])
                return None
            return data

    def pause(self):
        gevent.sleep(random.uniform(1, 5))  # noqa: S311 부하 시나리오 생각 시간이며 비밀값이 아님

    def venue(self):
        return random.choice(FIXTURE["venues"])  # noqa: S311 공간 트래픽 분포

    def public_request(self):
        venue = self.venue()
        draw = random.randrange(100)  # noqa: S311 시나리오 가중 선택
        ident = venue["venue_id"]
        if draw < 3:
            return self.call("GET", "/categories", {200})
        if draw < 5:
            return self.call(
                "GET",
                "/regions",
                {200},
                params={"sido": venue["region"]["sido"]} if draw == 4 else {},
            )
        if draw < 6:
            return self.call("GET", "/facilities", {200})
        if draw < 36:
            variant = random.randrange(6)  # noqa: S311 검색 조건 분산
            params = {"page": 1, "size": 10}
            if variant == 0:
                params["category"] = venue["category"]["code"]
            elif variant == 1:
                params.update(venue["region"])
            elif variant == 2:
                params.update(
                    date=FIXTURE["tomorrow"],
                    start_hour=venue["open_hour"],
                    hours=venue["min_hours"],
                    people=1,
                )
            elif variant == 3 and venue["facilities"]:
                params["facilities"] = str(venue["facilities"][0]["facility_id"])
            elif variant == 4:
                params["sort"] = random.choice(["price", "popular", "rating"])  # noqa: S311 정렬 분포
            else:
                params["q"] = venue["category"]["name"]
            return self.call("GET", "/venues", {200}, params=params)
        if draw < 40:
            return self.call("GET", "/venues/new", {200}, params={"size": 10})
        if draw < 60:
            return self.call("GET", f"/venues/{ident}", {200}, name="/venues/{id}")
        if draw < 70:
            return self.call(
                "GET",
                f"/venues/{ident}/available-dates",
                {200},
                params={"offset": 0, "days": 14},
                name="/venues/{id}/available-dates",
            )
        if draw < 85:
            return self.call(
                "GET",
                f"/venues/{ident}/slots",
                {200},
                params={"date": FIXTURE["tomorrow"]},
                name="/venues/{id}/slots",
            )
        if draw < 90:
            return self.call(
                "GET",
                f"/venues/{ident}/reviews",
                {200},
                params={"size": 10},
                name="/venues/{id}/reviews",
            )
        return self.call(
            "GET",
            "/reviews",
            {200},
            params={"category": venue["category"]["code"], "sort": "recent", "size": 10},
        )

    def private_request(self):
        draw = random.randrange(100)  # noqa: S311 요청 분포
        if draw < 50:
            return self.call("GET", "/reservations/me", {200}, params={"size": 10})
        if draw < 70:
            return self.call(
                "GET",
                f"/reservations/{self.account['private_reservation']}",
                {200},
                name="/reservations/{id}",
            )
        if draw < 85:
            return self.call("GET", "/users/me", {200})
        return self.call("GET", "/users/me/reviews", {200}, params={"size": 10})

    def cancel(self, ident):
        def check(data):
            if (
                data.get("status") != "cancelled"
                or data.get("payment", {}).get("status") != "refunded"
            ):
                raise ValueError("cancelled/refunded")

        result = self.call(
            "POST",
            f"/reservations/{ident}/cancel",
            {200},
            name="/reservations/{id}/cancel",
            validate=check,
        )
        if result:
            self.pending.discard(ident)
        return result

    def booking_journey(self):
        started = time.time()
        blocks = self.account["booking_blocks"]
        if self.book_cursor >= len(blocks):
            emit_transaction("fixture_exhausted", scope="booking")
            raise StopUser
        body = blocks[self.book_cursor]
        price = FIXTURE["prices"][str(body["venue_id"])]
        self.call(
            "GET",
            "/venues",
            {200},
            params={"category": FIXTURE["categories_by_id"][str(body["venue_id"])]},
        )
        self.pause()
        self.call("GET", f"/venues/{body['venue_id']}", {200}, name="/venues/{id}")
        self.pause()
        self.call(
            "GET",
            f"/venues/{body['venue_id']}/slots",
            {200},
            params={"date": body["date"]},
            name="/venues/{id}/slots",
        )
        self.pause()
        receipt = self.call(
            "POST",
            "/reservations",
            {201},
            json=body,
            validate=lambda data: check_reservation(body, data, price, "confirmed"),
        )
        if not receipt:
            emit_transaction("booking_failed", started=started)
            return
        ident = receipt["reservation_id"]
        self.pending.add(ident)
        self.pause()
        self.call("GET", f"/reservations/{ident}", {200}, name="/reservations/{id}")
        cancel = MODE != "mixed" or random.random() < 0.2  # noqa: S311 실사용형 취소 20% 가정
        if cancel:
            self.pause()
            if not self.cancel(ident):
                return
            self.call("GET", f"/reservations/{ident}", {200}, name="/reservations/{id}")
        else:
            self.pending.discard(ident)
            self.book_cursor += 1
        emit_transaction("booking_ok", started=started, reservation_id=ident, cancelled=cancel)

    def review_journey(self):
        if not self.review_pool:
            emit_transaction("fixture_exhausted", scope="review")
            raise StopUser
        started = time.time()
        reservation = self.review_pool.pop()
        created = self.call(
            "POST",
            f"/reservations/{reservation}/review",
            {201},
            name="/reservations/{id}/review",
            json={"rating": 5, "content": "합성 부하 시험 후기"},
        )
        if not created:
            return
        ident = created["review_id"]
        self.pause()
        self.call("GET", "/users/me/reviews", {200})
        self.pause()
        self.call(
            "PATCH",
            f"/reviews/{ident}",
            {200},
            name="/reviews/{id}",
            json={"rating": 4, "content": "합성 부하 시험 후기 수정"},
        )
        self.pause()
        self.call("GET", "/users/me/reviews", {200})
        self.pause()
        deleted = self.call("DELETE", f"/reviews/{ident}", {204}, name="/reviews/{id}")
        if deleted is not None:

            def check_deleted(data):
                if any(item["review_id"] == ident for item in data["items"]):
                    raise ValueError("deleted_review_visible")

            self.call("GET", "/users/me/reviews", {200}, validate=check_deleted)
            emit_transaction("review_ok", started=started, review_id=ident)

    def on_stop(self):
        for ident in list(getattr(self, "pending", set())):
            self.cancel(ident)


class Scenario(ScenarioUser):
    @task
    def execute(self):
        if MODE == "public":
            self.public_request()
        elif MODE == "private":
            self.private_request()
        elif MODE == "book":
            self.booking_journey()
        elif MODE == "review":
            self.review_journey()
        elif MODE == "profile":
            value = bool(random.getrandbits(1))
            self.call("PATCH", "/users/me", {200}, json={"marketing_agreed": value})

            def check(data):
                if data.get("marketing_agreed") is not value:
                    raise ValueError("marketing_agreed")

            self.call("GET", "/users/me", {200}, validate=check)
        elif MODE == "events":
            count = int(os.environ.get("SPACE_EVENT_BATCH", "10"))
            batch = build_event_batch(self.session_id, count, self.event_sequence)
            self.event_sequence += count

            def check(data):
                if data.get("accepted") != count or data.get("ignored"):
                    raise ValueError("event_accepted")

            self.call("POST", "/events", {202}, json=batch, validate=check)


class Browser(ScenarioUser):
    weight = 60

    @task
    def execute(self):
        for _ in range(4):
            self.public_request()
            self.pause()


class Booker(ScenarioUser):
    weight = 30

    @task
    def execute(self):
        self.booking_journey()


class Reviewer(ScenarioUser):
    weight = 10

    @task
    def execute(self):
        self.review_journey()
