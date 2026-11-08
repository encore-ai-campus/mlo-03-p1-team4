"""읽기 실행 동안 발생기 PC와 VMware 물리 호스트의 집계 자원만 기록한다."""

import base64
import contextlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

report = Path(sys.argv[1])
parents = [
    p
    for p in psutil.process_iter(["cmdline", "name"])
    if (p.info["name"] or "").lower().startswith("python")
    and any(
        Path(str(v)).name in {"read_high.py", "write_high.py", "capacity.py"}
        for v in p.info["cmdline"] or []
    )
]
if len(parents) != 1:
    raise SystemExit("read_runner_not_unique")
parent = parents[0]
script = "$o=Get-CimInstance Win32_OperatingSystem;$c=Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter \"Name='_Total'\";$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\";[pscustomobject]@{cpu_percent=$c.PercentProcessorTime;ram_total_kib=$o.TotalVisibleMemorySize;ram_free_kib=$o.FreePhysicalMemory;c_disk_total=$d.Size;c_disk_free=$d.FreeSpace}|ConvertTo-Json -Compress"
encoded = base64.b64encode(script.encode("utf-16-le")).decode()
command = (
    "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -NonInteractive -EncodedCommand "
    + encoded
)
psutil.cpu_percent()
cpu_cache = {}
with (report / "generator-host-resources.jsonl").open("a", encoding="utf-8", buffering=1) as output:
    while parent.is_running():
        processes = []
        for p in parent.children(recursive=True):
            with contextlib.suppress(psutil.Error):
                processes.append(
                    {
                        "pid": p.pid,
                        "cpu_percent_one_core": cpu_cache.setdefault(p.pid, p).cpu_percent(),
                        "rss_bytes": p.memory_info().rss,
                    }
                )
        record = {
            "time": time.time(),
            "generator_cpu_percent": psutil.cpu_percent(),
            "generator_memory_percent": psutil.virtual_memory().percent,
            "processes": processes,
        }
        try:
            r = subprocess.run(  # noqa: S603 고정 SSH·고정 집계 PowerShell만 실행
                [shutil.which("ssh"), "-o", "BatchMode=yes", "playdata", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            if r.returncode:
                raise ValueError("host_sample_failed")
            record["vmware_windows_host"] = json.loads(r.stdout)
        except (subprocess.TimeoutExpired, ValueError):
            record["host_sample_error"] = True
        output.write(json.dumps(record) + "\n")
        print("HOST_SAMPLE " + str(record["time"]), flush=True)
        for _ in range(30):
            if not parent.is_running():
                break
            time.sleep(1)
