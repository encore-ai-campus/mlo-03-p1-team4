"""mon에서 현재 대시보드를 파일 원본으로 보존하고 UI 저장을 허용한다."""

import base64
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import yaml


def main():
    credentials = json.load(sys.stdin)
    header = base64.b64encode(
        (credentials["user"] + ":" + credentials["password"]).encode()
    ).decode()

    def api(path, payload=None):
        request = urllib.request.Request(
            "http://127.0.0.1:3000/api/" + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Authorization": "Basic " + header, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 고정 localhost HTTP API만 호출
            return json.load(response)

    provider = Path("/etc/grafana/provisioning/dashboards/spacecube.yml")
    backup = Path("/var/backups/spacecube-monitoring") / (
        "saved-dashboards-" + str(int(time.time()))
    )
    backup.mkdir(parents=True)
    shutil.copy2(provider, backup / "spacecube.yml")
    config = yaml.safe_load(provider.read_text())
    for row in config["providers"]:
        if row.get("name") == "Spacecube":
            row.update(allowUiUpdates=True, disableDeletion=True, updateIntervalSeconds=30)
    saved = []
    pending = []
    # 파일 하나를 쓰는 중 공급기가 다른 옛 파일을 재반영하지 않도록 먼저 모두 조회한다.
    for path in Path("/var/lib/grafana/dashboards").glob("dashboard-*.json"):
        disk = json.loads(path.read_text())
        current = api("dashboards/uid/" + disk["uid"])["dashboard"]
        pending.append((path, current))
    for path, current in pending:
        shutil.copy2(path, backup / path.name)
        current.pop("id", None)
        current["timezone"] = "Asia/Seoul"
        current["refresh"] = "15s"
        current["time"] = {"from": "now-30m", "to": "now"}
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
        saved.append(current["uid"])
    provider.write_text(yaml.safe_dump(config, sort_keys=False))
    api("admin/provisioning/dashboards/reload", {})
    print(
        json.dumps(
            {"persisted": saved, "ui_save_allowed": True, "backup": str(backup), "restarted": False}
        )
    )


if __name__ == "__main__":
    main()
