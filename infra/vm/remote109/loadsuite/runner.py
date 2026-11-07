"""7대 시험 서버의 합성 fixture·Locust 단계·관측·결과 저장을 자동화한다."""

import argparse
import base64
import concurrent.futures
import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests
from logic import allocate_blocks, check_reservation, validate_observation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SSH = shutil.which("ssh")
REMOTE_ROOT = "/home/playdata/spacecube109"
TASK = "CODEX-LOAD-20261107"
QUERIES = {
    "up": "up",
    "mysql_up": 'mysql_up{job="mariadb"}',
    "app_metrics_error": "spacecube_db_app_metrics_error",
    "app_metrics_timestamp": "spacecube_db_app_observed_timestamp_seconds",
    "cpu": '100*(1-avg by(server)(rate(node_cpu_seconds_total{job="nodes",mode="idle"}[1m])))',
    "memory": '100*(1-node_memory_MemAvailable_bytes{job="nodes"}/node_memory_MemTotal_bytes{job="nodes"})',
    "disk_free": 'node_filesystem_avail_bytes{job="nodes",mountpoint="/"}',
    "app_connections": "spacecube_db_app_connections",
    "app_state_age": "spacecube_db_app_state_age_seconds_max",
    "app_lock_waits": "spacecube_db_app_lock_waits",
    "app_lock_seconds": "spacecube_db_app_lock_wait_seconds_max",
    "db_connections": 'mysql_global_status_threads_connected{job="mariadb"}',
    "db_running": 'mysql_global_status_threads_running{job="mariadb"}',
    "db_max_connections": 'mysql_global_variables_max_connections{job="mariadb"}',
    "db_replica_lag": 'mysql_slave_status_seconds_behind_master{job="mariadb"}',
    "backend": 'haproxy_server_status{proxy="apps",state="UP"}',
    "http_status": 'sum by(server,method,status)(rate(http_requests_total{job="api"}[1m]))',
}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remote(code, timeout=45):
    result = subprocess.run(  # noqa: S603 고정 SSH 별칭·stdin 스크립트, shell 실행 없음
        [SSH, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "playdata", "python3 -"],
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("remote_check_failed: " + result.stderr[-350:])
    return result.stdout


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)]


class Suite:
    def __init__(self, gateway, report):
        self.gateway = gateway.rstrip("/")
        if self.gateway != "http://192.168.219.218":
            raise ValueError("이번 승인 대상은 192.168.219.218 정문입니다.")
        self.report = report
        self.report.mkdir(parents=True, exist_ok=False)
        self.run_id = report.name
        self.password = secrets.token_urlsafe(24)
        self.key = ""
        self.tokens = {}
        self.sessions = {}
        self.results = []
        self.phase_name = "preflight"
        self.end_sampling = threading.Event()
        self.fixture = {}
        self.created = []
        self.monitor_errors = 0
        self.claimed = False

    def claim(self):
        script = (
            "run_id="
            + repr(self.run_id)
            + "\n"
            + r"""
from pathlib import Path
import fcntl
root=Path('/home/playdata/spacecube109');task='CODEX-LOAD-20261107';op=root/'.server-operation.lock'
board=root/'SERVER_WORK_BOARD.md'
with (root/'.server-work-board.edit.lock').open('a') as edit:
 fcntl.flock(edit,fcntl.LOCK_EX);text=board.read_text()
 for line in text.splitlines():
  if line.startswith('| ') and ' | Codex | ' not in line and '진행 중' in line and line.count('|')>=6:
   raise SystemExit('another_agent_active')
 if not op.exists():
  op.mkdir();(op/'owner').write_text(task+'\n')
 if (op/'owner').read_text().strip()!=task:raise SystemExit('operation_owned_by_other')
 with (op/'runner').open('x') as f:f.write(run_id)
 text+='\nCodex run 시작: '+run_id+'; 읽기/쓰기 부하·fixture 생성 승인 범위. 설정 변경·추가 부하 금지.\n'
 board.write_text(text)
print('exclusive_run_claimed')
"""
        )
        remote(script)
        self.claimed = True

    def api(self, method, path, *, account=None, status=200, **kwargs):
        headers = {"X-Synthetic": "1", "X-Synthetic-Key": self.key, "X-Session-Id": str(uuid4())}
        if account is not None:
            headers["Authorization"] = "Bearer " + self.tokens[account]
        response = requests.request(
            method, self.gateway + "/api" + path, headers=headers, timeout=(5, 25), **kwargs
        )
        if response.status_code != status:
            try:
                code = response.json().get("code", "no_code")
            except ValueError:
                code = "non_json"
            raise RuntimeError(f"fixture_HTTP_{response.status_code}_{code}_{path.split('?')[0]}")
        return response.json() if response.content else {}

    def stage_remote_sampler(self):
        data = base64.b64encode((HERE / "sample_remote.py").read_bytes()).decode()
        remote(
            "from pathlib import Path;import base64;p=Path('"
            + REMOTE_ROOT
            + "/codex-loadsuite');p.mkdir(exist_ok=True);(p/'sample_remote.py').write_bytes(base64.b64decode('"
            + data
            + "'));print('sampler_ready')"
        )

    def prepare(self):
        self.phase_name = "fixture_prepare"
        self.key = remote(
            "from pathlib import Path;p=Path.home()/'.config/spacecube109/app/.env';v=dict(l.split('=',1) for l in p.read_text().splitlines() if '=' in l);print(v['SYNTHETIC_API_KEY'])"
        ).strip()
        self.api("GET", "/health")
        schema = self.api("GET", "/openapi.json")
        save(self.report / "openapi.json", schema)
        venues = self.api("GET", "/venues", params={"size": 50})
        details = [self.api("GET", f"/venues/{v['venue_id']}") for v in venues["items"]]
        dates = self.api(
            "GET",
            f"/venues/{details[0]['venue_id']}/available-dates",
            params={"offset": 0, "days": 1},
        )
        today = date.fromisoformat(dates["dates"][0]["date"])
        tomorrow = (today + timedelta(days=1)).isoformat()
        future = allocate_blocks(details, (today + timedelta(days=2)).isoformat(), 70)
        available = []
        slots_cache = {}
        for body in future:
            cache_key = (body["venue_id"], body["date"])
            if cache_key not in slots_cache:
                slots_cache[cache_key] = self.api(
                    "GET", f"/venues/{body['venue_id']}/slots", params={"date": body["date"]}
                )
            occupied = {item["hour"] for item in slots_cache[cache_key] if item["taken"]}
            if not occupied.intersection(
                range(body["start_hour"], body["start_hour"] + body["hours"])
            ):
                available.append(body)
            if len(available) >= 650:
                break
        future = available
        if len(future) < 643:
            raise RuntimeError("insufficient_disjoint_future_blocks")
        free_past = []
        for body in allocate_blocks(details, (today - timedelta(days=90)).isoformat(), 90):
            cache_key = (body["venue_id"], body["date"])
            if cache_key not in slots_cache:
                slots_cache[cache_key] = self.api(
                    "GET", f"/venues/{body['venue_id']}/slots", params={"date": body["date"]}
                )
            occupied = {item["hour"] for item in slots_cache[cache_key] if item["taken"]}
            if not occupied.intersection(
                range(body["start_hour"], body["start_hour"] + body["hours"])
            ):
                free_past.append(body)
            if len(free_past) >= 315:
                break
        past = iter(free_past)
        prefix = "synthetic." + uuid4().hex[:14]
        self.fixture = {
            "venues": details,
            "prices": {str(v["venue_id"]): v["price_per_hour"] for v in details},
            "categories_by_id": {str(v["venue_id"]): v["category"]["code"] for v in details},
            "email_prefix": prefix,
            "tomorrow": tomorrow,
            "accounts": [],
        }
        cursor = 0
        for index in range(50):
            email = f"{prefix}.{index}@load.invalid"
            signup = self.api(
                "POST",
                "/auth/signup",
                status=201,
                json={
                    "email": email,
                    "password": self.password,
                    "name": "합성시험회원",
                    "phone": "01000000000",
                    "birth": "000101",
                    "gender_digit": "3",
                    "marketing_agreed": False,
                    "terms_agreed": True,
                    "privacy_agreed": True,
                },
            )
            token = self.api(
                "POST", "/auth/login", json={"email": email, "password": self.password}
            )
            self.tokens[index] = token["access_token"]
            account = {"user_id": signup["user_id"], "review_fixtures": []}
            count = 40 if index < 15 else 1
            account["booking_blocks"] = future[cursor : cursor + count]
            cursor += count
            if len(account["booking_blocks"]) != count:
                raise RuntimeError("future_fixture_budget")
            # 첫 completed 예약은 인증 조회용. 후기 CRUD용은 별도 자원이다.
            needed = 46 if index >= 45 else 9 if index < 5 else 1
            for number in range(needed):
                for _attempt in range(200):
                    body = next(past)
                    try:
                        receipt = self.api(
                            "POST", "/reservations", account=index, status=201, json=body
                        )
                        break
                    except RuntimeError as error:
                        if "409_SLOT_TAKEN" not in str(error):
                            raise
                else:
                    raise RuntimeError("past_fixture_exhausted")
                check_reservation(
                    body, receipt, self.fixture["prices"][str(body["venue_id"])], "completed"
                )
                ident = receipt["reservation_id"]
                self.created.append(ident)
                if number == 0:
                    account["private_reservation"] = ident
                    review = self.api(
                        "POST",
                        f"/reservations/{ident}/review",
                        account=index,
                        status=201,
                        json={"rating": 5, "content": "합성 읽기 fixture 후기"},
                    )
                    account["private_review"] = review["review_id"]
                else:
                    account["review_fixtures"].append(ident)
            self.fixture["accounts"].append(account)
            if (index + 1) % 10 == 0:
                print(
                    f"FIXTURE accounts={index + 1}/50 reservations={len(self.created)}", flush=True
                )
        self.fixture["collision_blocks"] = future[cursor : cursor + 8]
        save(self.report / "fixtures.json", self.fixture)
        save(
            self.report / "fixture_summary.json",
            {
                "accounts": 50,
                "completed_reservations": len(self.created),
                "private_reviews": 50,
                "venue_count": len(details),
                "credentials": "process_memory_only",
            },
        )
        self.stage_remote_sampler()
        self.sampler = threading.Thread(target=self.sample_loop, daemon=True)
        self.sampler.start()
        self.contract_smoke()

    def contract_smoke(self):
        self.phase_name = "contract_smoke"
        venue = self.fixture["venues"][0]["venue_id"]
        routes = [
            "/categories",
            "/regions",
            "/facilities",
            "/venues?size=10",
            "/venues/new",
            f"/venues/{venue}",
            f"/venues/{venue}/available-dates?days=14",
            f"/venues/{venue}/slots?date={self.fixture['tomorrow']}",
            f"/venues/{venue}/reviews",
            "/reviews",
            "/users/me",
            "/reservations/me",
            "/users/me/reviews",
            f"/reservations/{self.fixture['accounts'][0]['private_reservation']}",
        ]
        for route in routes:
            self.api(
                "GET", route, account=0 if route.startswith(("/users/", "/reservations/")) else None
            )
        save(self.report / "contract-smoke.json", {"get_routes_passed": len(routes)})

    def sample_loop(self):
        with (self.report / "resources.jsonl").open("w", encoding="utf-8", buffering=1) as output:
            iteration = 0
            while not self.end_sampling.is_set():
                record = {"time": time.time(), "phase": self.phase_name, "metrics": {}}
                try:
                    for name, query in QUERIES.items():
                        response = requests.get(
                            "http://192.168.219.217:9090/api/v1/query",
                            params={"query": query},
                            timeout=5,
                        )
                        response.raise_for_status()
                        record["metrics"][name] = response.json()["data"]["result"]
                    if iteration % 2 == 0:
                        record["direct_7node_sample"] = json.loads(
                            remote(
                                "exec(open('"
                                + REMOTE_ROOT
                                + "/codex-loadsuite/sample_remote.py').read())",
                                timeout=25,
                            )
                        )
                    validate_observation(record)
                    self.monitor_errors = 0
                except (
                    requests.RequestException,
                    RuntimeError,
                    ValueError,
                    KeyError,
                    subprocess.TimeoutExpired,
                ):
                    record["monitor_error"] = True
                    self.monitor_errors += 1
                output.write(json.dumps(record) + "\n")
                iteration += 1
                self.end_sampling.wait(15)

    def run_phase(self, mode, users, measure, warmup, label=None):
        label = label or f"{mode}-{users}"
        self.phase_name = label
        folder = self.report / label
        folder.mkdir()
        self.api("GET", "/health")
        if self.monitor_errors >= 2:
            raise RuntimeError("monitoring_unavailable")
        env = {
            **os.environ,
            "SPACE_MODE": mode,
            "SPACE_FIXTURE": str(self.report / "fixtures.json"),
            "SPACE_RUN_DIR": str(folder),
            "SPACE_ACCOUNT_PASSWORD": self.password,
            "SPACE_SYNTHETIC_KEY": self.key,
            "SPACE_WARMUP": str(warmup),
            "SPACE_MEASURE": str(measure),
        }
        spawn = min(5, users)
        classes = ["Browser", "Booker", "Reviewer"] if mode == "mixed" else ["Scenario"]
        command = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(HERE / "locustfile.py"),
            *classes,
            "--host",
            self.gateway,
            "--headless",
            "--users",
            str(users),
            "--spawn-rate",
            str(spawn),
            "--run-time",
            str(warmup + measure + math.ceil(users / spawn) + 90) + "s",
            "--stop-timeout",
            "45",
            "--only-summary",
            "--csv",
            str(folder / "locust"),
            "--csv-full-history",
            "--html",
            str(folder / "locust.html"),
        ]
        print(f"START {label} users={users} warmup={warmup}s measure={measure}s", flush=True)
        with (folder / "console.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(  # noqa: S603 고정 Python/Locust·승인한 사설 정문이며 비밀값은 환경으로만 전달
                command,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=warmup + measure + math.ceil(users / spawn) + 180,
            )
        if (folder / "abort.json").exists():
            save(
                folder / "summary.json",
                {
                    "phase": label,
                    "users": users,
                    "exit_code": process.returncode,
                    "aborted": True,
                    "first_failure": json.loads(
                        (folder / "abort.json").read_text(encoding="utf-8")
                    ),
                },
            )
            raise RuntimeError("phase_aborted_on_first_error_" + label)
        result = self.summarize(folder, mode, users)
        result["exit_code"] = process.returncode
        save(folder / "summary.json", result)
        self.results.append(result)
        self.write_summary()
        print("RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
        if (
            result["availability_error_rate"] >= 0.01
            or result["contract_errors"]
            or result["fixture_exhausted"]
            or process.returncode
        ):
            raise RuntimeError("phase_failed_" + label)
        self.api("GET", "/health")
        return result

    def summarize(self, folder, mode, users):
        phase = json.loads((folder / "phase.json").read_text())
        raw = [json.loads(line) for line in (folder / "requests.jsonl").read_text().splitlines()]
        samples = [r for r in raw if r["phase"] == "measure"]
        if not samples:
            raise RuntimeError("no_measured_requests_" + folder.name)
        transactions = [
            json.loads(line) for line in (folder / "transactions.jsonl").read_text().splitlines()
        ]
        availability = sum(r["verdict"] == "availability" for r in samples)
        grouped = defaultdict(list)
        for row in samples:
            grouped[(row["method"], row["name"])].append(row)
        endpoint = []
        for (method, name), rows in grouped.items():
            normal = [r["ms"] for r in rows if not r["failed"] and 200 <= r["status"] < 300]
            endpoint.append(
                {
                    "method": method,
                    "name": name,
                    "count": len(rows),
                    "failures": sum(r["failed"] for r in rows),
                    "p95_ms": percentile(normal, 95),
                    "p99_ms": percentile(normal, 99),
                }
            )
        save(folder / "endpoints.json", endpoint)
        return {
            "phase": folder.name,
            "mode": mode,
            "users": users,
            "spawned": phase["spawned"],
            "start": phase["measurement_start"],
            "end": phase["measurement_end"],
            "requests": len(samples),
            "rps": len(samples) / (phase["measurement_end"] - phase["measurement_start"]),
            "availability_errors": availability,
            "availability_error_rate": availability / len(samples),
            "contract_errors": sum(r["verdict"] == "contract" for r in samples),
            "fixture_exhausted": sum(r["kind"] == "fixture_exhausted" for r in transactions),
            "statuses": dict(Counter(str(r["status"]) for r in samples)),
            "get_p95_ms": percentile(
                [r["ms"] for r in samples if r["method"] == "GET" and not r["failed"]], 95
            ),
            "reservation_p95_ms": percentile(
                [
                    r["ms"]
                    for r in samples
                    if r["method"] == "POST"
                    and r["name"] == "/reservations"
                    and r["status"] == 201
                    and not r["failed"]
                ],
                95,
            ),
            "all_phase_failed_requests": sum(r["failed"] for r in raw),
        }

    def recover(self, seconds):
        self.phase_name = "cooldown"
        print(f"COOLDOWN {seconds}s", flush=True)
        # 짧게 검사하며 사용자의 새 입력을 반영할 수 있게 실행 로그를 계속 제공한다.
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            time.sleep(min(5, max(0, until - time.monotonic())))
        self.api("GET", "/health")

    def auth_smoke(self):
        self.phase_name = "auth-smoke"

        def exercise(index):
            email = "synthetic.auth." + uuid4().hex + "@load.invalid"
            secret = secrets.token_urlsafe(24)
            replacement = secrets.token_urlsafe(24)
            response = self.api(
                "POST",
                "/auth/signup",
                status=201,
                json={
                    "email": email,
                    "password": secret,
                    "name": "합성인증시험",
                    "phone": "01000000000",
                    "birth": "000101",
                    "gender_digit": "3",
                    "marketing_agreed": False,
                    "terms_agreed": True,
                    "privacy_agreed": True,
                },
            )
            token = self.api("POST", "/auth/login", json={"email": email, "password": secret})[
                "access_token"
            ]
            temp_index = 100 + index
            self.tokens[temp_index] = token
            self.api(
                "PATCH",
                "/users/me/password",
                account=temp_index,
                status=204,
                json={"current_password": secret, "new_password": replacement},
            )
            token = self.api("POST", "/auth/login", json={"email": email, "password": replacement})[
                "access_token"
            ]
            self.tokens[temp_index] = token
            self.api("POST", "/auth/logout", account=temp_index, status=204)
            self.api("DELETE", "/users/me", account=temp_index, status=204)
            self.api(
                "POST", "/auth/login", status=401, json={"email": email, "password": replacement}
            )
            return {"user_id": response["user_id"], "steps": 8, "completed": True}

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            result = list(pool.map(exercise, range(5)))
        save(self.report / "auth-smoke.json", result)
        print("AUTH_SMOKE 5 disposable users passed", flush=True)

    def write_summary(self, error=None):
        save(
            self.report / "suite.json",
            {
                "run_id": self.run_id,
                "gateway": self.gateway,
                "results": self.results,
                "error": error,
                "db_limits_changed": False,
                "credentials_saved": False,
            },
        )
        lines = [
            "# 7대 VM Locust 실행 결과",
            "",
            f"run_id: {self.run_id}",
            "",
            "|단계|VU|요청 수|RPS|GET p95 ms|예약 201 p95 ms|가용성 오류|",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in self.results:
            lines.append(
                f"|{r['phase']}|{r['users']}|{r['requests']}|{r['rps']:.2f}|{r['get_p95_ms']}|{r['reservation_p95_ms']}|{r['availability_errors']}|"
            )
        lines += [
            "",
            "측정은 목표 VU 도달 뒤 워밍업을 제외하고 시작·종료가 모두 구간 안에 든 요청만 계산했다. 짧은 탐색과 50명 혼합 A7을 구분한다. latency는 request 원본의 nearest-rank 백분위다.",
            "",
            "CPU/메모리/DB 연결·Sleep/Query·행 잠금 대기: resources.jsonl. 개별 API: 각 단계 endpoints.json. 원본·CSV·HTML은 각 단계 폴더. DB 전역·앱 연결 제한을 바꾸지 않았다.",
        ]
        if error:
            lines += ["", "중단 사유: " + error]
        (self.report / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def collision_checks(self):
        """서로 다른 50명/같은 회원 재시도를 독립된 칸에서 동기화한다."""
        self.phase_name = "collision"
        results = []
        for kind, shared in [("C01-distinct-50", False), ("C02-same-user-50", True)]:
            body = self.fixture["collision_blocks"][int(shared)]
            barrier = threading.Barrier(50)

            def attempt(index, same_user=shared, start_barrier=barrier, request_body=body):
                account = 0 if same_user else index
                headers = {
                    "X-Synthetic": "1",
                    "X-Synthetic-Key": self.key,
                    "Authorization": "Bearer " + self.tokens[account],
                    "X-Session-Id": str(uuid4()),
                }
                start_barrier.wait(timeout=15)
                started = time.time()
                response = requests.post(
                    self.gateway + "/api/reservations",
                    headers=headers,
                    json=request_body,
                    timeout=25,
                )
                try:
                    data = response.json()
                except ValueError:
                    data = {}
                return {
                    "account_index": account,
                    "status": response.status_code,
                    "id": data.get("reservation_id"),
                    "code": data.get("code"),
                    "started": started,
                    "finished": time.time(),
                }

            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
                records = list(pool.map(attempt, range(50)))
            counts = Counter(r["status"] for r in records)
            wanted = {201: 1, 200 if shared else 409: 49}
            valid = dict(counts) == wanted
            if shared:
                valid = valid and len({r["id"] for r in records}) == 1
            else:
                valid = valid and all(
                    r["code"] == "SLOT_TAKEN" for r in records if r["status"] == 409
                )
            result = {
                "case": kind,
                "counts": dict(counts),
                "pass": valid,
                "start_spread_ms": 1000
                * (max(r["started"] for r in records) - min(r["started"] for r in records)),
                "requests": records,
            }
            results.append(result)
            save(self.report / "collision.json", results)
            for winner in [r for r in records if r["status"] == 201]:
                self.api(
                    "POST", f"/reservations/{winner['id']}/cancel", account=winner["account_index"]
                )
            if not valid:
                raise RuntimeError("collision_failed_" + kind)
        print("COLLISION distinct50=201x1/409x49; same-user=201x1/200x49", flush=True)

    def finish(self, error):
        self.end_sampling.set()
        if hasattr(self, "sampler"):
            self.sampler.join(timeout=50)
        try:
            self.write_summary(error)
        except OSError as exception:
            print("REPORT_WRITE_FAILED " + type(exception).__name__, flush=True)
        # 전용 key/password/token은 프로세스 메모리에서만 사용했다.
        self.key = ""
        self.password = ""
        self.tokens.clear()
        if self.claimed:
            script = (
                "run_id="
                + repr(self.run_id)
                + "\nstate="
                + repr("실패·후속 확인" if error else "완료")
                + "\n"
                + r"""
from pathlib import Path
import fcntl
root=Path('/home/playdata/spacecube109');op=root/'.server-operation.lock'
if (op/'runner').read_text()!=run_id:raise SystemExit('run_owner_changed')
with (root/'.server-work-board.edit.lock').open('a') as edit:
 fcntl.flock(edit,fcntl.LOCK_EX);p=root/'SERVER_WORK_BOARD.md';text=p.read_text();lines=[]
 for line in text.splitlines():
  if line.startswith('| CODEX-LOAD-20261107 |'):
   line='| CODEX-LOAD-20261107 | Codex | '+state+' | '+run_id+' | 결과·원본은 해당 run_id reports/loadsuite, 설정/DB 한도 유지 |'
  lines.append(line)
 try:
  p.write_text('\n'.join(lines)+'\n')
 finally:
  (op/'runner').unlink();(op/'owner').unlink();op.rmdir();print('own_operation_lock_released')
"""
            )
            remote(script)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default="http://192.168.219.218")
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    if SSH is None:
        raise SystemExit("ssh_not_found")
    stamp = datetime.fromtimestamp(time.time(), ZoneInfo("Asia/Seoul")).strftime("%Y%m%d-%H%M%S")
    report = ROOT / "logs" / ("loadsuite-" + stamp)
    suite = Suite(args.gateway, report)
    print("REPORT " + str(report), flush=True)
    error = None
    try:
        suite.claim()
        suite.prepare()
        for mode in ["public", "private", "book", "review", "profile", "events"]:
            suite.run_phase(mode, 1, 15, 5, "smoke-" + mode)
            suite.recover(15)
        suite.auth_smoke()
        suite.collision_checks()
        suite.recover(30)
        if not args.smoke_only:
            for mode in ["public", "book"]:
                for users in [5, 20, 50]:
                    suite.run_phase(mode, users, 60, 10)
                    suite.recover(30)
            for mode in ["private", "review", "profile", "events"]:
                suite.run_phase(mode, 5, 30, 5)
                suite.recover(30)
            suite.run_phase("mixed", 50, 540, 60, "A7-mixed-50")
            suite.recover(30)
    except Exception as exception:
        error = str(exception)
        print("STOP " + error, flush=True)
    finally:
        suite.finish(error)
    print("FINISHED " + str(report / "RESULTS.md"), flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
