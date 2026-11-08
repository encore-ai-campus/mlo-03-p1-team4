"""mon에서 기존 scrape 설정을 보존해 DB 4개 target만 추가한다."""

import shutil
import subprocess
import time
from pathlib import Path

import yaml

PATH = Path("/etc/prometheus/prometheus.yml")
previous = PATH.read_text()
config = yaml.safe_load(previous)
jobs = config["scrape_configs"]
nodes = next(job for job in jobs if job["job_name"] == "nodes")
for end, server in [(212, "db-primary"), (213, "db-replica")]:
    target = f"192.168.219.{end}:9100"
    if not any(target in row.get("targets", []) for row in nodes["static_configs"]):
        nodes["static_configs"].append({"targets": [target], "labels": {"server": server}})
mysql = next((job for job in jobs if job["job_name"] == "mariadb"), None)
if mysql is None:
    mysql = {"job_name": "mariadb", "static_configs": []}
    jobs.append(mysql)
for end, server in [(212, "db-primary"), (213, "db-replica")]:
    target = f"192.168.219.{end}:9104"
    if not any(target in row.get("targets", []) for row in mysql["static_configs"]):
        mysql["static_configs"].append({"targets": [target], "labels": {"server": server}})
next_text = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
temp = PATH.with_suffix(".codex-next.yml")
temp.write_text(next_text)
result = subprocess.run(  # noqa: S603 고정 promtool과 고정 설정 경로
    ["/usr/bin/promtool", "check", "config", str(temp)], capture_output=True, text=True, timeout=15
)
if result.returncode:
    temp.unlink()
    raise SystemExit("promtool_validation_failed")
if next_text != previous:
    shutil.copy2(PATH, PATH.with_name(f"prometheus.yml.before-db-exporters-{int(time.time())}"))
    shutil.copyfile(temp, PATH)
temp.unlink()
subprocess.run(["/usr/bin/systemctl", "reload", "prometheus"], check=True, timeout=15)
print("prometheus_db_targets_added_config_valid")
