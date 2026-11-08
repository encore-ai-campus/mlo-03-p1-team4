"""앱 원본 IP별 연결·대기 집계만 node exporter textfile로 게시한다."""

import os
import subprocess
import time
from pathlib import Path

TARGET = Path("/var/lib/spacecube-monitoring/textfile/app_connections.prom")
IPS = {"192.168.219.214": "api1", "192.168.219.215": "api2"}
SQL = """
SELECT SUBSTRING_INDEX(HOST,':',1),COMMAND,COUNT(*),MAX(TIME)
FROM information_schema.PROCESSLIST
WHERE SUBSTRING_INDEX(HOST,':',1) IN ('192.168.219.214','192.168.219.215')
AND DB='spacecube' AND COMMAND IN ('Sleep','Query')
GROUP BY SUBSTRING_INDEX(HOST,':',1),COMMAND;
SELECT SUBSTRING_INDEX(p.HOST,':',1),COUNT(*),
COALESCE(MAX(TIMESTAMPDIFF(SECOND,t.trx_wait_started,NOW())),0)
FROM information_schema.INNODB_TRX t JOIN information_schema.PROCESSLIST p
ON p.ID=t.trx_mysql_thread_id
WHERE t.trx_state='LOCK WAIT'
AND SUBSTRING_INDEX(p.HOST,':',1) IN ('192.168.219.214','192.168.219.215')
GROUP BY SUBSTRING_INDEX(p.HOST,':',1);
"""


def collect():
    result = subprocess.run(
        [
            "/usr/bin/mariadb",
            "--defaults-extra-file=/etc/spacecube-monitoring/my.cnf",
            "--batch",
            "--skip-column-names",
        ],
        input=SQL,
        capture_output=True,
        text=True,
        timeout=8,
    )
    lines = [f"spacecube_db_app_observed_timestamp_seconds {time.time()}"]
    if result.returncode:
        return [*lines, "spacecube_db_app_metrics_error 1"]
    counts = {(ip, command): (0, 0) for ip in IPS for command in ["Sleep", "Query"]}
    waits = dict.fromkeys(IPS, (0, 0))
    for row in result.stdout.splitlines():
        fields = row.split("\t")
        if len(fields) == 4:
            counts[(fields[0], fields[1])] = (int(fields[2]), int(fields[3]))
        elif len(fields) == 3:
            waits[fields[0]] = (int(fields[1]), int(fields[2]))
    for (ip, command), (count, age) in counts.items():
        labels = f'app="{IPS[ip]}",source_ip="{ip}",command="{command}"'
        lines += [
            f"spacecube_db_app_connections{{{labels}}} {count}",
            f"spacecube_db_app_state_age_seconds_max{{{labels}}} {age}",
        ]
    for ip, (count, seconds) in waits.items():
        labels = f'app="{IPS[ip]}",source_ip="{ip}"'
        lines += [
            f"spacecube_db_app_lock_waits{{{labels}}} {count}",
            f"spacecube_db_app_lock_wait_seconds_max{{{labels}}} {seconds}",
        ]
    return [*lines, "spacecube_db_app_metrics_error 0"]


if __name__ == "__main__":
    temp = TARGET.with_suffix(".tmp")
    temp.write_text("\n".join(collect()) + "\n", encoding="utf-8")
    os.replace(temp, TARGET)
