"""109 WSL에서 7대 VM 자원을 읽는다. 설치·설정 변경·비밀값 출력 없음."""

import concurrent.futures
import json
import subprocess
import time
from pathlib import Path

KEY = Path.home() / ".config/spacecube109/id_ed25519"
KNOWN = Path.home() / ".config/spacecube109/known_hosts"
ROLES = {
    "gw": (218, "ubuntu"),
    "api1": (214, "ubuntu"),
    "api2": (215, "ubuntu"),
    "mon": (217, "ubuntu"),
    "db1": (212, "ubuntu"),
    "db2": (213, "ubuntu"),
    "mongo": (216, "test"),
}
CODE = """
import json,time,os,shutil,re

def cpu():
 x=list(map(int,open('/proc/stat').readline().split()[1:9]));return sum(x),x[3]+x[4]
def disks():
 out={}
 for line in open('/proc/diskstats'):
  f=line.split()
  if re.fullmatch(r'(sd[a-z]|vd[a-z]|nvme[0-9]+n[0-9]+)',f[2]):out[f[2]]=list(map(int,f[3:]))
 return out
a=cpu();da=disks();ta=time.monotonic();time.sleep(1);b=cpu();db=disks();elapsed=time.monotonic()-ta
m={l.split(':')[0]:int(l.split()[1])*1024 for l in open('/proc/meminfo')};d=shutil.disk_usage('/');io={}
for device,y in db.items():
 if device not in da:continue
 x=da[device];reads=y[0]-x[0];writes=y[4]-x[4]
 io[device]=dict(read_iops=reads/elapsed,write_iops=writes/elapsed,read_bytes_s=(y[2]-x[2])*512/elapsed,write_bytes_s=(y[6]-x[6])*512/elapsed,busy_percent=(y[9]-x[9])/elapsed/10,read_latency_ms=(y[3]-x[3])/reads if reads else None,write_latency_ms=(y[7]-x[7])/writes if writes else None)
print(json.dumps(dict(cpu_percent=100*(1-(b[1]-a[1])/max(1,b[0]-a[0])),memory_percent=100*(1-m['MemAvailable']/m['MemTotal']),memory_total=m['MemTotal'],disk_total=d.total,disk_free=d.free,swap_total=m['SwapTotal'],swap_free=m['SwapFree'],disk_io=io,load1=os.getloadavg()[0])))
"""


def sample(item):
    role, (end, user) = item
    args = [
        "/usr/bin/ssh",
        "-i",
        str(KEY),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "UserKnownHostsFile=" + str(KNOWN),
        f"{user}@192.168.219.{end}",
        "python3 -",
    ]
    try:
        result = subprocess.run(args, input=CODE, capture_output=True, text=True, timeout=12)  # noqa: S603 고정 VM 목록·고정 읽기 전용 스크립트
        if result.returncode:
            return {"server": role, "error": "ssh_exit_" + str(result.returncode)}
        return {"server": role, **json.loads(result.stdout)}
    except (subprocess.TimeoutExpired, ValueError):
        return {"server": role, "error": "sample_failed"}


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        print(json.dumps({"time": time.time(), "nodes": list(pool.map(sample, ROLES.items()))}))
