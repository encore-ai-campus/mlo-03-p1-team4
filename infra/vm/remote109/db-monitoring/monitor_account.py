"""DB 내부에서만 전용 계정과 보호 인증 파일을 만든다. 비밀값 출력 없음."""

import grp
import os
import secrets
import subprocess
from pathlib import Path

TARGET = Path("/etc/spacecube-monitoring/my.cnf")
TARGET.parent.mkdir(mode=0o750, exist_ok=True)
group = grp.getgrnam("spacecube-exporter").gr_gid
os.chown(TARGET.parent, 0, group)
os.chmod(TARGET.parent, 0o750)  # noqa: S103 전용 exporter 그룹만 탐색하며 other 접근은 없음
if TARGET.exists():
    raise SystemExit("existing_client_file_preserved")

password = secrets.token_hex(32)
sql = (
    "SET SESSION sql_log_bin=0; "
    "CREATE USER IF NOT EXISTS 'spacecube_exporter'@'localhost' "
    f"IDENTIFIED BY '{password}' WITH MAX_USER_CONNECTIONS 3; "
    f"ALTER USER 'spacecube_exporter'@'localhost' IDENTIFIED BY '{password}' "
    "WITH MAX_USER_CONNECTIONS 3; "
    "GRANT PROCESS, REPLICA MONITOR ON *.* TO 'spacecube_exporter'@'localhost'; "
    "GRANT SELECT ON spacecube.* TO 'spacecube_exporter'@'localhost';"
)
result = subprocess.run(
    ["/usr/bin/mariadb", "--batch"], input=sql, text=True, capture_output=True, timeout=15
)
if result.returncode:
    raise SystemExit("monitor_account_setup_failed")
fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
with os.fdopen(fd, "w") as stream:
    stream.write(
        "[client]\nuser=spacecube_exporter\npassword="
        + password
        + "\nsocket=/run/mysqld/mysqld.sock\n"
    )
os.chown(TARGET, 0, group)
os.chmod(TARGET, 0o640)
print("monitor_account_and_protected_file_created")
