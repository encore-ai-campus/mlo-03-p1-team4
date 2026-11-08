"""재배포 이후 설정을 고정한 예약 생성/취소 100·200·400명 시험."""

import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from logic import allocate_blocks, check_reservation, require_clean_stage
from runner import HERE, ROOT, Suite, remote, save


class WriteSuite(Suite):
    def prepare(self):
        self.phase_name = "fixture_prepare"
        self.key = remote(
            "from pathlib import Path;v=dict(l.split('=',1) for l in (Path.home()/'.config/spacecube109/app/.env').read_text().splitlines() if '=' in l);print(v['SYNTHETIC_API_KEY'])"
        ).strip()
        health = self.api("GET", "/health")
        if health.get("status") != "ok":
            raise RuntimeError("health_degraded")
        save(self.report / "openapi.json", self.api("GET", "/openapi.json"))
        data = self.api("GET", "/venues", params={"size": 50})
        details = [self.api("GET", f"/venues/{v['venue_id']}") for v in data["items"]]
        dates = self.api(
            "GET",
            f"/venues/{details[0]['venue_id']}/available-dates",
            params={"offset": 0, "days": 1},
        )
        today = date.fromisoformat(dates["dates"][0]["date"])
        cache = {}
        available = []
        for body in allocate_blocks(details, (today + timedelta(days=5)).isoformat(), 70):
            key = (body["venue_id"], body["date"])
            if key not in cache:
                cache[key] = self.api(
                    "GET", f"/venues/{body['venue_id']}/slots", params={"date": body["date"]}
                )
            occupied = {v["hour"] for v in cache[key] if v["taken"]}
            if not occupied.intersection(
                range(body["start_hour"], body["start_hour"] + body["hours"])
            ):
                available.append(body)
            if len(available) >= 400:
                break
        if len(available) < 400:
            raise RuntimeError("insufficient_unique_slots")
        self.available = available
        self.fixture = {
            "venues": details,
            "prices": {str(v["venue_id"]): v["price_per_hour"] for v in details},
            "categories_by_id": {str(v["venue_id"]): v["category"]["code"] for v in details},
            "tomorrow": (today + timedelta(days=1)).isoformat(),
            "email_prefix": "synthetic.write." + uuid4().hex[:12],
            "accounts": [],
        }
        self.stage_remote_sampler()
        self.sampler = threading.Thread(target=self.sample_loop, daemon=True)
        self.sampler.start()
        save(
            self.report / "fixture_summary.json",
            {
                "accounts": 0,
                "venue_count": len(details),
                "slot_count": 400,
                "credentials": "process_memory_only",
                "prepared_completed_reservations": 0,
            },
        )

    def provision_accounts(self, total):
        self.phase_name = "fixture_prepare"
        for index in range(len(self.fixture["accounts"]), total):
            email = f"{self.fixture['email_prefix']}.{index}@load.invalid"
            response = self.api(
                "POST",
                "/auth/signup",
                status=201,
                json={
                    "email": email,
                    "password": self.password,
                    "name": "합성쓰기시험회원",
                    "phone": "01000000000",
                    "birth": "000101",
                    "gender_digit": "3",
                    "marketing_agreed": False,
                    "terms_agreed": True,
                    "privacy_agreed": True,
                },
            )
            self.tokens[index] = self.api(
                "POST", "/auth/login", json={"email": email, "password": self.password}
            )["access_token"]
            self.fixture["accounts"].append(
                {
                    "user_id": response["user_id"],
                    "booking_blocks": [self.available[index]],
                    "review_fixtures": [],
                }
            )
            if (index + 1) % 25 == 0:
                print(f"FIXTURE accounts={index + 1}/{total}", flush=True)
        save(self.report / "fixtures.json", self.fixture)
        save(
            self.report / "fixture_summary.json",
            {
                "accounts": total,
                "venue_count": len(self.fixture["venues"]),
                "slot_count": 400,
                "credentials": "process_memory_only",
                "prepared_completed_reservations": 0,
            },
        )

    def smoke(self):
        body = self.available[0]
        response = self.api("POST", "/reservations", account=0, status=201, json=body)
        check_reservation(
            body, response, self.fixture["prices"][str(body["venue_id"])], "confirmed"
        )
        cancelled = self.api(
            "POST", f"/reservations/{response['reservation_id']}/cancel", account=0
        )
        if (
            cancelled.get("status") != "cancelled"
            or cancelled.get("payment", {}).get("status") != "refunded"
        ):
            raise RuntimeError("smoke_cancel_contract")
        save(
            self.report / "write-smoke.json",
            {
                "created_reservation": response["reservation_id"],
                "created_status": 201,
                "cancelled": True,
            },
        )
        print("WRITE_SMOKE create201/cancel200 passed", flush=True)

    def clean_own_confirmed(self):
        self.phase_name = "cleanup"
        if not self.tokens:
            return
        health = self.api("GET", "/health")
        if health.get("status") != "ok":
            raise RuntimeError("cleanup_health_degraded")
        found = 0
        cancelled = 0
        for index, account in enumerate(self.fixture.get("accounts", [])):
            response = self.api(
                "GET", "/reservations/me", account=index, params={"status": "confirmed", "size": 50}
            )
            body = account["booking_blocks"][0]
            for row in response["items"]:
                if (
                    row.get("venue_id") == body["venue_id"]
                    and row.get("date") == body["date"]
                    and row.get("start_hour") == body["start_hour"]
                ):
                    found += 1
                    self.api("POST", f"/reservations/{row['reservation_id']}/cancel", account=index)
                    cancelled += 1
        save(
            self.report / "cleanup.json",
            {
                "own_confirmed_found": found,
                "cancelled": cancelled,
                "accounts_checked": len(self.fixture.get("accounts", [])),
            },
        )


def main():
    stamp = datetime.fromtimestamp(time.time(), ZoneInfo("Asia/Seoul")).strftime("%Y%m%d-%H%M%S")
    suite = WriteSuite("http://192.168.219.218", ROOT / "logs" / ("write-high-" + stamp))
    print("REPORT " + str(suite.report), flush=True)
    error = None
    try:
        suite.claim()
        board = remote(
            "from pathlib import Path;print((Path('/home/playdata/spacecube109')/'SERVER_WORK_BOARD.md').read_text())"
        )
        (suite.report / "deployment-handoff.md").write_text(board, encoding="utf-8")
        suite.prepare()
        observer = subprocess.Popen(  # noqa: S603 고정 보조 수집기·현재 실행 디렉터리만 전달
            [sys.executable, str(HERE / "observe_generator_host.py"), str(suite.report)],
            stdout=(suite.report / "host-observer.log").open("w"),
            stderr=subprocess.STDOUT,
        )
        save(suite.report / "host-observer.json", {"pid": observer.pid})
        suite.provision_accounts(100)
        suite.smoke()
        subprocess.run(  # noqa: S603 고정 읽기 전용 수집기
            [
                sys.executable,
                str(HERE / "collect_server_evidence.py"),
                str(suite.report),
                "--label",
                "before",
            ],
            check=True,
        )
        for users in [100, 200, 400]:
            if users > 100:
                suite.provision_accounts(users)
            result = suite.run_phase("book", users, 180, 60)
            require_clean_stage(result)
            suite.recover(120)
    except Exception as exception:
        error = str(exception)
        print("STOP " + error, flush=True)
    finally:
        if suite.tokens:
            try:
                suite.recover(30)
                suite.clean_own_confirmed()
            except Exception as cleanup_error:
                save(suite.report / "cleanup-error.json", {"error": str(cleanup_error)})
        suite.finish(error)
    print("WRITE_FINISHED " + str(suite.report / "RESULTS.md"), flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
