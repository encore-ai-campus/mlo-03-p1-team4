"""#20: 네 페르소나가 실제 API를 이용하는 매일 실행 시나리오."""

import json
import os
import random
from collections import Counter, deque
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from locust import HttpUser, between, events, task
from locust.exception import StopUser
from locust.runners import MasterRunner, WorkerRunner

from app.core.clock import get_event_time

SEOUL = ZoneInfo("Asia/Seoul")
PROFILES = {
    "Student": {"categories": ("studyroom", "lectureroom"), "hours": (1, 2), "people": 2},
    "Worker": {"categories": ("studyroom", "studio"), "hours": (1, 2), "people": 2},
    "Gathering": {
        "categories": ("partyroom", "cafe", "lectureroom"),
        "hours": (2, 3, 4),
        "people": 6,
    },
    "Explorer": {"categories": (), "hours": (), "people": 0},
}
DAILY_USER_LIMITS = {"Student": 20, "Worker": 15, "Gathering": 10, "Explorer": 5}
RUN = None


def load_accounts(path: str) -> deque:
    """가상 회원은 파일에서만 읽고 결과·오류에는 자격 증명을 남기지 않는다."""
    if not path:
        raise ValueError("LOCUST_ACCOUNTS_FILE 경로가 필요합니다.")
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            raise ValueError
        accounts = [(row["email"], row["password"]) for row in rows]
        if any(
            not isinstance(email, str) or not isinstance(password, str)
            for email, password in accounts
        ):
            raise ValueError
        if any(not email or not password for email, password in accounts):
            raise ValueError
        if len({email.casefold() for email, _ in accounts}) != len(accounts):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(
            "가상 회원 파일은 중복 없는 email/password JSON 배열이어야 합니다."
        ) from None
    random.shuffle(accounts)
    return deque(accounts)


def load_dates(raw: str) -> list[str]:
    try:
        values = [value.strip() for value in raw.split(",") if value.strip()]
        if (
            not values
            or len(set(values)) != len(values)
            or any(datetime.fromisoformat(value).date().isoformat() != value for value in values)
        ):
            raise ValueError
    except ValueError:
        raise ValueError("LOCUST_DATES에는 중복 없는 실제 YYYY-MM-DD 날짜를 지정하세요.") from None
    return values


def candidate_hours(slots: list[dict], hours: int) -> list[int]:
    free = {slot["hour"] for slot in slots if slot.get("taken") is False}
    return sorted(hour for hour in free if all(hour + offset in free for offset in range(hours)))


def preferred_hours(profile: str, booking_date: str, starts: list[int], hours: int) -> list[int]:
    weekend = date.fromisoformat(booking_date).weekday() >= 5
    if profile == "Student":
        window = (14, 18) if not weekend else None
    elif profile == "Worker":
        window = (10, 12) if weekend else (19, 22)
    elif profile == "Gathering":
        window = (13, 18) if weekend else None
    else:
        window = (9, 23)
    if window is None:
        return []
    return [hour for hour in starts if window[0] <= hour and hour + hours <= window[1]]


def now_kst() -> str:
    return get_event_time().astimezone(SEOUL).isoformat(timespec="seconds")


def booking_outcome(status: int, body: object) -> str:
    """예상 칸 충돌만 허용하고 인증·검증 실패는 정상 예약으로 숨기지 않는다."""
    if not isinstance(body, dict):
        return "error"
    if status == 409 and body.get("code") == "SLOT_TAKEN":
        return "conflict"
    identifier = body.get("reservation_id")
    if status in (200, 201) and type(identifier) is int and identifier > 0:
        return "created" if status == 201 else "replayed"
    return "error"


class DailyRun:
    def __init__(self, environment):
        self.environment = environment
        self.run_id = str(uuid4())
        self.started_at = now_kst()
        if len(environment.user_classes) != 1:
            raise ValueError(
                "매일 실행은 Student/Worker/Gathering/Explorer 중 한 클래스만 선택하세요."
            )
        self.profile = environment.user_classes[0].__name__
        if self.profile not in PROFILES:
            raise ValueError("알 수 없는 페르소나 클래스입니다.")
        self.key = os.environ.get("SYNTHETIC_API_KEY", "")
        if not self.key:
            raise ValueError("SYNTHETIC_API_KEY가 필요합니다.")
        flag = os.environ.get("LOCUST_ALLOW_WRITES", "0")
        if flag not in {"0", "1"}:
            raise ValueError("LOCUST_ALLOW_WRITES는 0 또는 1만 허용합니다.")
        self.allow_writes = flag == "1"
        self.target_users = environment.parsed_options.num_users
        if (
            type(self.target_users) is not int
            or not 1 <= self.target_users <= DAILY_USER_LIMITS[self.profile]
        ):
            raise ValueError(
                "일일 페르소나 인원 상한을 넘었습니다. 한계 시험은 별도 실행기를 사용하세요."
            )
        if isinstance(environment.runner, (MasterRunner, WorkerRunner)):
            raise ValueError(
                "매일 실행은 단일 프로세스만 지원합니다. 계정 배분을 보장할 수 없습니다."
            )
        self.max_bookings_per_user = 1
        self.peak_users = 0
        self.server_errors = 0
        self.outcomes = Counter()
        self.dates = load_dates(os.environ.get("LOCUST_DATES", ""))
        if self.profile != "Explorer":
            self.dates = [
                value
                for value in self.dates
                if preferred_hours(self.profile, value, list(range(9, 23)), 1)
            ]
            if not self.dates:
                raise ValueError("페르소나의 선호 요일에 맞는 LOCUST_DATES가 없습니다.")
        if self.allow_writes and self.profile != "Explorer" and len(self.dates) < 2:
            raise ValueError(
                "쓰기 모드는 페르소나 요일에 맞는 서로 다른 LOCUST_DATES를 2개 이상 지정하세요."
            )
        self.accounts = (
            deque()
            if self.profile == "Explorer" or not self.allow_writes
            else load_accounts(os.environ.get("LOCUST_ACCOUNTS_FILE", ""))
        )
        self.target_users = environment.parsed_options.num_users
        if (
            self.allow_writes
            and self.profile != "Explorer"
            and len(self.accounts) < self.target_users
        ):
            raise ValueError("가상 회원 수가 동시 사용자 수보다 적습니다.")
        self.statuses = Counter()
        self.issues = Counter()
        self.date_visits = Counter()
        self.date_cursor = random.randrange(len(self.dates))  # noqa: S311 -- 실행별 날짜 배정 순환점
        self.claimed_slots = set()

    def finish(self):
        stats = self.environment.stats.total
        result = {
            "event": "daily_locust_run",
            "run_id": self.run_id,
            "profile": self.profile,
            "started_at": self.started_at,
            "finished_at": now_kst(),
            "target_users": self.target_users,
            "actual_peak_users": self.peak_users,
            "mode": "persona-write" if self.allow_writes else "read-only",
            "max_bookings_per_user": self.max_bookings_per_user,
            "duration_seconds": max(
                0,
                (
                    datetime.fromisoformat(now_kst()) - datetime.fromisoformat(self.started_at)
                ).total_seconds(),
            ),
            "average_ms": stats.avg_response_time,
            "p95_ms": stats.get_response_time_percentile(0.95),
            "p99_ms": stats.get_response_time_percentile(0.99),
            "server_errors": self.server_errors,
            "server_error_rate": self.server_errors / stats.num_requests
            if stats.num_requests
            else None,
            "outcomes": dict(self.outcomes),
            "date_visits": dict(self.date_visits),
            "local_slot_claims": len(self.claimed_slots),
            "performance_verdict": "not_evaluated_daily_run",
            "requests": stats.num_requests,
            "failures": stats.num_failures,
            "statuses": dict(self.statuses),
            "issues": dict(self.issues),
            "result": "success"
            if stats.num_requests
            and not stats.num_failures
            and not self.issues
            and self.peak_users >= self.target_users
            else "failure",
        }
        if result["result"] == "failure":
            self.environment.process_exit_code = 1
        line = json.dumps(result, ensure_ascii=False)
        loki_url = os.environ.get("LOCUST_LOKI_PUSH_URL", "")
        result["loki_delivery"] = "disabled"
        if loki_url:
            parts = urlsplit(loki_url)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                self.environment.process_exit_code = 1
                result["loki_delivery"] = "failure"
            else:
                payload = {
                    "streams": [
                        {
                            "stream": {"job": "locust_daily", "profile": self.profile},
                            "values": [
                                [str(int(get_event_time().timestamp() * 1_000_000_000)), line]
                            ],
                        }
                    ]
                }
                request = Request(  # noqa: S310 -- HTTP(S) 검사 완료
                    loki_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urlopen(request, timeout=5) as response:  # noqa: S310 -- HTTP(S) 검사 완료
                        if response.status != 204:
                            raise OSError(f"Loki HTTP {response.status}")
                    result["loki_delivery"] = "success"
                except OSError:
                    self.environment.process_exit_code = 1
                    result["loki_delivery"] = "failure"
                    print("Locust 실행 기록을 Loki로 보내지 못했습니다.", flush=True)
        output = Path(os.environ.get("LOCUST_RUN_LOG", "simulator/locust/logs/daily-runs.jsonl"))
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(json.dumps(result, ensure_ascii=False), flush=True)

    def assign_date_offset(self) -> int:
        """여러 실제 날짜에 사용자를 순환 배정해 한 날짜 쏠림을 줄인다."""
        offset = self.date_cursor
        self.date_cursor = (self.date_cursor + 1) % len(self.dates)
        return offset

    def claim_slots(self, venue_id: int, booking_date: str, start_hour: int, hours: int) -> bool:
        """같은 Locust 프로세스 사용자가 겹치는 칸을 동시에 고르지 않게 한다."""
        slots = tuple(
            (venue_id, booking_date, hour) for hour in range(start_hour, start_hour + hours)
        )
        if any(slot in self.claimed_slots for slot in slots):
            return False
        self.claimed_slots.update(slots)
        return True

    def release_slots(self, venue_id: int, booking_date: str, start_hour: int, hours: int):
        slots = ((venue_id, booking_date, hour) for hour in range(start_hour, start_hour + hours))
        self.claimed_slots.difference_update(slots)


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    global RUN
    RUN = None
    try:
        RUN = DailyRun(environment)
    except ValueError as error:
        raise SystemExit(str(error)) from None


@events.request.add_listener
def on_request(response=None, exception=None, **_kwargs):
    if RUN is not None:
        status = response.status_code if response is not None else 0
        RUN.statuses[str(status)] += 1
        RUN.server_errors += int(status == 0 or status >= 500)
        RUN.peak_users = max(RUN.peak_users, RUN.environment.runner.user_count)


@events.spawning_complete.add_listener
def on_spawning_complete(user_count, **_kwargs):
    if RUN is not None:
        RUN.peak_users = max(RUN.peak_users, user_count)


@events.user_error.add_listener
def on_user_error(user_instance, exception, tb, **_kwargs):
    # 예외 본문에는 입력값이 섞일 수 있으므로 종류별 상세 대신 건수만 기록한다.
    if RUN is not None:
        RUN.issues["task_exception"] += 1


@events.test_stop.add_listener
def on_test_stop(**_kwargs):
    if RUN is not None:
        RUN.finish()


class Persona(HttpUser):
    abstract = True
    wait_time = between(1, 5)
    profile = ""

    def on_start(self):
        self.session_id = str(uuid4())
        self.anonymous_id = f"locust_{uuid4()}"
        self.event_sequence = 0
        self.current_page = None
        self.date_offset = RUN.assign_date_offset()
        self.visit_count = 0
        host = urlsplit(self.host)
        if (
            host.scheme not in {"http", "https"}
            or not host.netloc
            or not host.hostname
            or host.username
            or host.password
        ):
            RUN.issues["invalid_gateway"] += 1
            raise StopUser()
        self.site_origin = f"{host.scheme}://{host.netloc}"
        self.site_hostname = host.hostname
        self.landing_url = urljoin(self.site_origin, "/")
        self.headers = {
            "X-Synthetic": "1",
            "X-Synthetic-Key": RUN.key,
            "X-Session-Id": self.session_id,
        }
        self.token = ""
        self.bookings = 0
        if RUN.allow_writes and self.profile != "Explorer":
            if not RUN.accounts:
                RUN.issues["missing_account"] += 1
                raise StopUser()
            email, password = RUN.accounts.popleft()
            with self.client.post(
                "/api/auth/login",
                json={"email": email, "password": password},
                headers=self.headers,
                name="POST /auth/login",
                catch_response=True,
            ) as response:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                if (
                    response.status_code != 200
                    or not isinstance(body, dict)
                    or not body.get("access_token")
                ):
                    RUN.issues["login_failed"] += 1
                    response.failure("가상 회원 로그인 실패")
                    raise StopUser()
                self.token = body["access_token"]
                self.headers["Authorization"] = f"Bearer {self.token}"

    def booking_budget_available(self) -> bool:
        return self.bookings < RUN.max_bookings_per_user

    def event(
        self,
        event_name: str,
        *,
        page_type: str,
        path: str,
        product_id: int | None = None,
        properties: dict | None = None,
    ):
        if not RUN.allow_writes:
            return True
        self.event_sequence += 1
        page_view_id = str(uuid4())
        page_url = urljoin(self.site_origin, path)
        target_page = {
            "page_view_id": page_view_id,
            "site_id": "main",
            "url": page_url,
            "path": path,
        }
        item = {
            "schema_version": 1,
            "event_name": event_name,
            "occurred_at": now_kst(),
            "user": {
                "anonymous_id": self.anonymous_id,
                "session_id": self.session_id,
                "session_sequence": self.event_sequence,
            },
            "site": {
                "site_id": "main",
                "hostname": self.site_hostname,
                "platform": "desktop_web",
            },
            "acquisition": {
                "landing_url": self.landing_url,
                "referrer_url": self.current_page["url"] if self.current_page else None,
                "utm_source": None,
                "utm_medium": None,
                "utm_campaign": None,
            },
            "page": {
                "page_view_id": page_view_id,
                "page_type": page_type,
                "url": page_url,
                "path": path,
                "title": page_type,
            },
            "navigation": {
                "from": self.current_page,
                "to": target_page,
                "navigation_type": "internal" if self.current_page else "direct",
            },
            "products": [{"product_id": str(product_id)}] if product_id is not None else [],
            "properties": properties or {},
        }
        with self.client.post(
            "/api/events",
            json={"session_id": self.session_id, "events": [item]},
            headers=self.headers,
            name="POST /events",
            catch_response=True,
        ) as response:
            try:
                body = response.json()
            except ValueError:
                body = {}
            if (
                response.status_code != 202
                or not isinstance(body, dict)
                or body.get("accepted") != 1
            ):
                RUN.issues["event_failed"] += 1
                response.failure("가상 이벤트 수집 실패")
                return False
            self.current_page = target_page
            return True

    def get_json(self, path: str, *, params=None, name: str):
        with self.client.get(
            "/api" + path,
            params=params,
            headers=self.headers,
            name=name,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                RUN.issues["read_failed"] += 1
                response.failure("공개 조회 실패")
                return None
            try:
                return response.json()
            except ValueError:
                RUN.issues["invalid_json"] += 1
                response.failure("응답 JSON 형식 오류")
                return None

    @task
    def visit(self):
        profile = PROFILES[self.profile]
        category = random.choice(profile["categories"]) if profile["categories"] else None  # noqa: S311 -- 시나리오 선택
        date = RUN.dates[(self.date_offset + self.visit_count) % len(RUN.dates)]
        self.visit_count += 1
        RUN.date_visits[date] += 1
        params = {"page": 1, "size": 10, "date": date}
        if category:
            params["category"] = category
        if not self.event(
            "search_submit",
            page_type="search_results",
            path="/search",
            properties={"date": date, "category": category} if category else {"date": date},
        ):
            return
        listing = self.get_json("/venues", params=params, name="GET /venues")
        if (
            not isinstance(listing, dict)
            or not isinstance(listing.get("items"), list)
            or type(listing.get("total")) is not int
            or listing["total"] < 0
        ):
            RUN.issues["invalid_listing"] += 1
            return
        page_count = max(1, (listing["total"] + params["size"] - 1) // params["size"])
        page = random.randint(1, page_count)  # noqa: S311 -- 결과 공간 페이지 분산
        if page > 1:
            params["page"] = page
            listing = self.get_json("/venues", params=params, name="GET /venues")
            if (
                not isinstance(listing, dict)
                or not isinstance(listing.get("items"), list)
                or type(listing.get("total")) is not int
                or listing["total"] < 0
            ):
                RUN.issues["invalid_listing"] += 1
                return
        if not listing["items"]:
            return
        venues = listing["items"]
        random.shuffle(venues)
        attempts = 1 if self.profile == "Explorer" else 3
        for venue in venues[:attempts]:
            if not isinstance(venue, dict):
                RUN.issues["invalid_venue"] += 1
                return
            venue_id = venue.get("venue_id")
            if not isinstance(venue_id, int):
                RUN.issues["invalid_venue"] += 1
                return
            venue_path = f"/venues/{venue_id}"
            if not self.event(
                "product_view",
                page_type="product_detail",
                path=venue_path,
                product_id=venue_id,
            ):
                return
            detail = self.get_json(f"/venues/{venue_id}", name="GET /venues/{id}")
            if not isinstance(detail, dict):
                RUN.issues["invalid_detail"] += 1
                continue
            if not self.event(
                "availability_view",
                page_type="product_detail",
                path=venue_path,
                product_id=venue_id,
            ):
                return
            slots = self.get_json(
                f"/venues/{venue_id}/slots",
                params={"date": date},
                name="GET /venues/{id}/slots",
            )
            if not isinstance(slots, list) or any(
                not isinstance(slot, dict)
                or type(slot.get("hour")) is not int
                or type(slot.get("taken")) is not bool
                for slot in slots
            ):
                RUN.issues["invalid_slots"] += 1
                continue
            if (
                self.profile == "Explorer"
                or not RUN.allow_writes
                or not self.booking_budget_available()
            ):
                return
            min_hours = detail.get("min_hours")
            capacity = detail.get("capacity_max")
            if type(min_hours) is not int or type(capacity) is not int:
                RUN.issues["invalid_detail"] += 1
                continue
            hours = max(random.choice(profile["hours"]), min_hours)  # noqa: S311 -- 시나리오 선택
            if hours > 4 or capacity < profile["people"]:
                continue
            starts = preferred_hours(self.profile, date, candidate_hours(slots, hours), hours)
            if not starts:
                continue
            random.shuffle(starts)
            start = next(
                (hour for hour in starts if RUN.claim_slots(venue_id, date, hour, hours)),
                None,
            )
            if start is None:
                continue
            booking_properties = {"date": date, "start_hour": start, "hours": hours}
            if not self.event(
                "rental_slot_select",
                page_type="product_detail",
                path=venue_path,
                product_id=venue_id,
                properties=booking_properties,
            ) or not self.event(
                "reservation_start",
                page_type="checkout",
                path="/reserve",
                product_id=venue_id,
                properties=booking_properties,
            ):
                RUN.release_slots(venue_id, date, start, hours)
                return
            body = {
                "venue_id": venue_id,
                "date": date,
                "start_hour": start,
                "hours": hours,
                "headcount": profile["people"],
                "method": "card",
            }
            with self.client.post(
                "/api/reservations",
                json=body,
                headers=self.headers,
                name="POST /reservations",
                catch_response=True,
            ) as response:
                try:
                    result = response.json()
                except ValueError:
                    result = {}
                outcome = booking_outcome(response.status_code, result)
                RUN.outcomes[outcome] += 1
                if outcome in {"created", "replayed"}:
                    self.bookings += 1
                    response.success()
                    return
                if outcome == "conflict":
                    RUN.release_slots(venue_id, date, start, hours)
                    response.success()
                    continue
                RUN.release_slots(venue_id, date, start, hours)
                RUN.issues["reservation_failed"] += 1
                response.failure("예약 응답 오류")
                return


class Student(Persona):
    profile = "Student"


class Worker(Persona):
    profile = "Worker"


class Gathering(Persona):
    profile = "Gathering"


class Explorer(Persona):
    profile = "Explorer"
