"""인증/SQL/사용자 글을 제외한 앱 요청·Uvicorn·health·타이머 기록."""

import argparse
import json
import time
from pathlib import Path

from runner import remote, save

CODE = r"""
from pathlib import Path
from datetime import datetime
import json,re,subprocess
rows=[]
for path in Path('/opt/spacecube/backend/logs').glob('app.log*'):
 if path.suffix=='.lock':continue
 try:
  with path.open() as stream:
   for line in stream:
    try:
     x=json.loads(line);stamp=datetime.fromisoformat(x['ts']).timestamp()
     if START<=stamp<=END:
      y={k:x[k] for k in ['ts','server','level','request_id','method','status','ms','completed','error_type','error_location'] if k in x}
      if 'path' in x:y['path']=re.sub(r'/[0-9]+(?=/|$)','/{id}',x['path'].split('?')[0])
      rows.append(y)
    except (ValueError,KeyError,TypeError):pass
 except (OSError,UnicodeError):pass
warnings=[]
r=subprocess.run(['journalctl','-u','spacecube','--since','@'+str(int(START)),'--until','@'+str(int(END)),'--no-pager','-o','json','--grep','Exceeded concurrency'],capture_output=True,text=True)
for line in r.stdout.splitlines():
 try:
  x=json.loads(line);warnings.append({'time_us':x.get('__REALTIME_TIMESTAMP'),'pid':x.get('_PID')})
 except ValueError:pass
timers={}
for unit in ['spacecube-event-daily.service','spacecube-complete.service','spacecube-crawler.service']:
 r=subprocess.run(['systemctl','show',unit,'-p','ExecMainStartTimestamp','-p','ExecMainExitTimestamp','-p','ExecMainStatus','-p','Result','-p','ActiveState'],capture_output=True,text=True)
 timers[unit]=dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
print(json.dumps({'requests':rows,'uvicorn_concurrency_warnings':warnings,'timers':timers}))
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    first = json.loads((args.report / "resources.jsonl").read_text().splitlines()[0])
    start = first["time"]
    end = time.time()
    script = (
        "CODE="
        + repr(CODE)
        + "\nSTART="
        + repr(start)
        + "\nEND="
        + repr(end)
        + "\n"
        + r'''
from pathlib import Path
import subprocess,json,concurrent.futures
c=Path.home()/'.config/spacecube109'
base=['ssh','-i',str(c/'id_ed25519'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(c/'known_hosts')]
def one(end):
 code='START='+repr(START)+'\nEND='+repr(END)+'\n'+CODE
 r=subprocess.run(base+[f'ubuntu@192.168.219.{end}','sudo python3 -'],input=code,capture_output=True,text=True,timeout=35)
 if r.returncode:raise RuntimeError('app_log_collection_failed')
 return {'ip':end,**json.loads(r.stdout)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:apps=list(pool.map(one,[214,215]))
code='START='+repr(START)+'\nEND='+repr(END)+'\n'+"""
import subprocess,json
r=subprocess.run(['journalctl','-u','haproxy','--since','@'+str(int(START)),'--until','@'+str(int(END)),'--no-pager','-o','json','--grep','DOWN|UP|no server|Layer7'],capture_output=True,text=True)
rows=[]
for line in r.stdout.splitlines():
 try:
  x=json.loads(line);message=x.get('MESSAGE','')
  if 'Server apps/' in message or 'backend apps' in message:rows.append({'time_us':x.get('__REALTIME_TIMESTAMP'),'message':message})
 except ValueError:pass
print(json.dumps(rows))
"""
r=subprocess.run(base+['ubuntu@192.168.219.218','sudo python3 -'],input=code,capture_output=True,text=True,timeout=20)
if r.returncode:raise RuntimeError('haproxy_log_collection_failed')
print(json.dumps({'apps':apps,'haproxy':json.loads(r.stdout)}))
'''
    )
    result = json.loads(remote(script, timeout=60))
    save(args.report / "application-logs.json", {"start": start, "end": end, **result})
    print(
        json.dumps(
            {
                "apps": [
                    {
                        "ip": v["ip"],
                        "requests": len(v["requests"]),
                        "warnings": len(v["uvicorn_concurrency_warnings"]),
                    }
                    for v in result["apps"]
                ],
                "haproxy_events": len(result["haproxy"]),
            }
        )
    )


if __name__ == "__main__":
    main()
