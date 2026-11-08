"""시험 VM에서 1초 간격으로 읽기 전용 자원 표본을 남긴다. 4시간 뒤 자동 종료."""

import json
import os
import shutil
import signal
import time

running = True


def finish(_number, _frame):
    global running
    running = False


def snapshot():
    with open("/proc/stat") as stream:
        cpu = list(map(int, stream.readline().split()[1:9]))
    with open("/proc/meminfo") as stream:
        memory = {s.split(":")[0]: int(s.split()[1]) * 1024 for s in stream}
    with open("/proc/net/dev") as stream:
        interfaces = [
            s.split(":", 1) for s in stream if ":" in s and s.split(":", 1)[0].strip() != "lo"
        ]
        network = {name.strip(): [int(x) for x in values.split()] for name, values in interfaces}
    disk = shutil.disk_usage("/")
    return {
        "time": time.time(),
        "cpu": cpu,
        "memory": memory,
        "network": network,
        "disk_free": disk.free,
        "disk_total": disk.total,
        "load1": os.getloadavg()[0],
        "vcpus": os.cpu_count(),
    }


def main():
    signal.signal(signal.SIGTERM, finish)
    signal.signal(signal.SIGINT, finish)
    before = snapshot()
    deadline = time.monotonic() + 14400
    while running and time.monotonic() < deadline:
        time.sleep(1)
        after = snapshot()
        deltas = [b - a for a, b in zip(before["cpu"], after["cpu"], strict=True)]
        total = max(1, sum(deltas))
        row = {
            "time": after["time"],
            "vcpus": after["vcpus"],
            "cpu_percent": 100 * (total - deltas[3] - deltas[4]) / total,
            "iowait_percent": 100 * deltas[4] / total,
            "steal_percent": 100 * deltas[7] / total,
            "memory_percent": 100
            * (1 - after["memory"]["MemAvailable"] / after["memory"]["MemTotal"]),
            "memory_total": after["memory"]["MemTotal"],
            "memory_available": after["memory"]["MemAvailable"],
            "swap_total": after["memory"]["SwapTotal"],
            "swap_free": after["memory"]["SwapFree"],
            "disk_free": after["disk_free"],
            "disk_total": after["disk_total"],
            "load1": after["load1"],
        }
        dt = max(0.001, after["time"] - before["time"])
        row["network"] = {
            name: {
                "rx_bytes_s": (v[0] - before["network"][name][0]) / dt,
                "tx_bytes_s": (v[8] - before["network"][name][8]) / dt,
            }
            for name, v in after["network"].items()
            if name in before["network"]
        }
        print(json.dumps(row), flush=True)
        before = after


if __name__ == "__main__":
    main()
