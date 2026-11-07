"""설정 고정 실패 지점 탐색. 첫 오류/신뢰성 실패에서 전체 증량을 멈춘다."""

import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from capacity_logic import audit_count, latency_failed, validate_host_sample
from logic import require_clean_stage
from read_high import ReadSuite
from runner import HERE, ROOT, save
from write_high import WriteSuite


def collect(name, report, *args):
    subprocess.run(  # noqa: S603 고정 수집기 이름과 보고서 경로만 전달
        [sys.executable, str(HERE / name), str(report), *args], check=True
    )


class CapacitySuite(WriteSuite):
    def refresh_tokens(self):
        for index in range(len(self.fixture.get("accounts", []))):
            response = self.api(
                "POST",
                "/auth/login",
                json={
                    "email": f"{self.fixture['email_prefix']}.{index}@load.invalid",
                    "password": self.password,
                },
            )
            self.tokens[index] = response["access_token"]

    def clean_own_confirmed(self):
        self.refresh_tokens()
        super().clean_own_confirmed()


def audit_stage(suite, label):
    until = time.monotonic() + 60
    while True:
        collect("collect_write_audit.py", suite.report)
        data = json.loads((suite.report / "write-data-audit.json").read_text(encoding="utf-8"))
        save(suite.report / (label + "-audit.json"), data)
        try:
            total = audit_count(data)
            print(f"AUDIT_OK {label} reservations={total} events={total * 2}", flush=True)
            return
        except ValueError:
            if time.monotonic() >= until:
                raise
            time.sleep(5)


def safety_loop(suite, stop, observer):
    last = None
    while not stop.wait(2):
        try:
            path = suite.report / "resources.jsonl"
            if not path.exists():
                continue
            rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
            if not rows:
                continue
            row = rows[-1]
            reason = None
            if row.get("monitor_error") or time.time() - row["time"] > 75:
                reason = "monitoring_unavailable"
            metrics = row.get("metrics", {})
            if any(float(v["value"][1]) >= 5 for v in metrics.get("db_replica_lag", [])):
                reason = "replication_lag"
            if any(float(v["value"][1]) > 60 for v in metrics.get("db_connections", [])):
                reason = "db_connections_safety_limit"
            for node in row.get("direct_7node_sample", {}).get("nodes", []):
                if node.get("error"):
                    reason = "vm_observation_failed"
                if node["server"] == "mongo" and node.get("disk_free", 2**60) < 1024**3:
                    reason = "mongo_disk_low"
            cpu_rows = [r for r in rows if row["time"] - 65 <= r["time"] <= row["time"]]
            if len(cpu_rows) >= 3 and cpu_rows[-1]["time"] - cpu_rows[0]["time"] >= 60:
                for server in ["api1", "api2", "gw", "mon", "db-primary", "db-replica"]:
                    vals = [
                        [
                            float(v["value"][1])
                            for v in r.get("metrics", {}).get("cpu", [])
                            if v["metric"].get("server") == server
                        ]
                        for r in cpu_rows
                    ]
                    if all(v and v[0] >= 85 for v in vals):
                        reason = "sustained_cpu_" + server
            host = suite.report / "generator-host-resources.jsonl"
            if observer.poll() is not None:
                reason = "host_observer_exited"
            if not host.exists():
                reason = "host_observation_missing"
            else:
                h = json.loads(host.read_text(encoding="utf-8").splitlines()[-1])
                try:
                    validate_host_sample(h, time.time())
                except ValueError as exception:
                    reason = str(exception)
            if reason and last != reason:
                marker = suite.report / "safety-stop.json"
                if not marker.exists():
                    tmp = suite.report / "safety-stop.tmp"
                    save(tmp, {"time": time.time(), "reason": reason})
                    tmp.replace(marker)
                last = reason
        except (OSError, ValueError, KeyError):
            # JSONL은 다른 스레드가 추가 중이다. 다음 표본에서 다시 읽는다.
            continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["book", "public"], default="book")
    parser.add_argument("--steps", default="400,400,500,600,800,1000")
    args = parser.parse_args()
    steps = [int(x) for x in args.steps.split(",")]
    if any(x < 1 or x > 1000 for x in steps):
        raise ValueError("steps_outside_approved_range")
    stamp = datetime.fromtimestamp(time.time(), ZoneInfo("Asia/Seoul")).strftime("%Y%m%d-%H%M%S")
    cls = CapacitySuite if args.mode == "book" else ReadSuite
    suite = cls("http://192.168.219.218", ROOT / "logs" / ("capacity-" + args.mode + "-" + stamp))
    suite.max_users = max(steps)
    error = None
    stop = threading.Event()
    print("REPORT " + str(suite.report), flush=True)
    try:
        suite.claim()
        suite.prepare()
        collect("observe_vms.py", suite.report, "start")
        observer = subprocess.Popen(  # noqa: S603 고정 자원 관측 도구만 실행
            [sys.executable, str(HERE / "observe_generator_host.py"), str(suite.report)],
            stdout=(suite.report / "host-observer.log").open("w"),
            stderr=subprocess.STDOUT,
        )
        save(suite.report / "host-observer.json", {"pid": observer.pid})
        deadline = time.monotonic() + 45
        host = suite.report / "generator-host-resources.jsonl"
        while not host.exists() or not host.stat().st_size:
            if observer.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("host_observer_start_failed")
            time.sleep(1)
        validate_host_sample(
            json.loads(host.read_text(encoding="utf-8").splitlines()[-1]), time.time()
        )
        threading.Thread(target=safety_loop, args=(suite, stop, observer), daemon=True).start()
        if args.mode == "book":
            suite.provision_accounts(steps[0])
            suite.smoke()
        time.sleep(15)
        collect("collect_server_evidence.py", suite.report, "--label", "before")
        for index, users in enumerate(steps, 1):
            if (suite.report / "safety-stop.json").exists():
                raise RuntimeError("safety_stop")
            if args.mode == "book":
                suite.provision_accounts(users)
            label = f"{args.mode}-{users}-r{index}"
            result = suite.run_phase(args.mode, users, 180, 60, label)
            require_clean_stage(result)
            suite.recover(120)
            if (suite.report / "safety-stop.json").exists():
                raise RuntimeError("safety_stop_after_cooldown")
            rows = [
                json.loads(x)
                for x in (suite.report / label / "requests.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            if args.mode == "book":
                audit_stage(suite, label)
            if latency_failed(rows, result["start"], args.mode):
                raise RuntimeError("latency_slo_" + label)
    except Exception as exception:
        error = str(exception)
        print("STOP " + error, flush=True)
    finally:
        if (suite.report / "safety-stop.json").exists():
            error = error or "safety_stop"
        if args.mode == "book" and suite.tokens:
            try:
                suite.clean_own_confirmed()
                audit_stage(suite, "final")
            except Exception as exception:
                error = error or "cleanup_or_audit_failed"
                save(suite.report / "cleanup-error.json", {"error": type(exception).__name__})
        stop.set()
        if (suite.report / "safety-stop.json").exists():
            error = error or "safety_stop"
        suite.finish(error)
        if (suite.report / "vm-observers-start.json").exists():
            try:
                collect("observe_vms.py", suite.report, "stop")
            except Exception:
                error = error or "vm_observation_collection_failed"
        if (suite.report / "resources.jsonl").exists():
            for name in [
                "collect_evidence.py",
                "collect_server_evidence.py",
                "collect_app_logs.py",
            ]:
                try:
                    collect(name, suite.report)
                except Exception as exception:
                    save(suite.report / (name + ".error.json"), {"error": type(exception).__name__})
                    error = error or "evidence_collection_failed"
    suite.write_summary(error)
    print("FINISHED " + str(suite.report), flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
