"""새 Grafana의 초기 .env와 관리자 계정을 한 번만 일치시킨다."""

import base64
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

values = dict(
    line.split("=", 1) for line in Path("/etc/grafana/.env").read_text().splitlines() if "=" in line
)
password = values["GF_SECURITY_ADMIN_PASSWORD"]
marker = Path("/var/lib/spacecube/grafana-admin-configured")


def authenticated():
    encoded = base64.b64encode(("admin:" + password).encode()).decode()
    request = Request(
        "http://127.0.0.1:3000/api/user", headers={"Authorization": "Basic " + encoded}
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 같은 VM의 Grafana만 조회
            return response.status == 200
    except HTTPError as error:
        if error.code == 401:
            return False
        raise


changed = False
if not authenticated():
    if marker.exists():
        raise RuntimeError(
            "기존 초기화 뒤 인증이 달라졌습니다. 비밀번호를 자동 재설정하지 않습니다."
        )
    # 다른 관리자나 사용자가 있는 인스턴스는 자동 초기화하지 않는다.
    with sqlite3.connect("file:/var/lib/grafana/grafana.db?mode=ro", uri=True) as database:
        users = database.execute('SELECT id, login, is_admin FROM "user"').fetchall()
    if users != [(1, "admin", 1)]:
        raise RuntimeError("초기 관리자 한 명만 있는 새 Grafana가 아닙니다.")
    environment = dict(
        os.environ,
        GF_PATHS_DATA="/var/lib/grafana",
        GF_PATHS_LOGS="/var/log/grafana",
        GF_PATHS_PLUGINS="/var/lib/grafana/plugins",
    )
    result = subprocess.run(
        [
            "/usr/share/grafana/bin/grafana",
            "cli",
            "--homepath=/usr/share/grafana",
            "--config=/etc/grafana/grafana.ini",
            "admin",
            "reset-admin-password",
            "--password-from-stdin",
        ],
        input=password + "\n",
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    if result.returncode or not authenticated():
        raise RuntimeError("Grafana 초기 관리자 설정에 실패했습니다. 비밀값은 출력하지 않습니다.")
    changed = True
if not marker.exists():
    marker.parent.mkdir(exist_ok=True)
    marker.write_text("configured\n")
    changed = True
print(json.dumps({"changed": changed, "authenticated": True}))
