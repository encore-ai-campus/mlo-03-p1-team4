"""시험 뒤 서버 로그를 구간 필터링하고 인증정보 없이 보존한다."""

import argparse
import json
import time
from pathlib import Path

from runner import remote, save

CODE = r"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import json,subprocess,hashlib,re,os
result={'role':ROLE,'time':__import__('time').time(),'fingerprints':{}}
paths=[Path('/etc/haproxy/haproxy.cfg')]
paths+=list(Path('/etc/nginx').glob('*.conf'))+list(Path('/etc/nginx/sites-enabled').glob('*'))+list(Path('/etc/nginx/conf.d').glob('*.conf'))
paths+=[Path('/opt/spacecube/backend/app/core')/name for name in ['db.py','database.py','config.py','settings.py','middleware.py','errors.py']]
paths += [Path('/opt/spacecube/backend/app/main.py')]
for p in paths:
 try:
  if p.is_file():result['fingerprints'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 except PermissionError:pass
if ROLE in ['api1','api2']:
 value=subprocess.run(['systemctl','show','spacecube','-p','ExecStart','--value'],capture_output=True,text=True).stdout
 result['uvicorn']={name:(re.search(r'--'+name+r'\s+(\S+)',value).group(1) if re.search(r'--'+name+r'\s+(\S+)',value) else None) for name in ['workers','limit-concurrency','timeout-keep-alive']}
result['nginx_requests']=[]
p=Path('/var/log/nginx/spacecube-access.log')
if p.exists():
 try:
  with p.open() as stream:
   for line in stream:
    try:
     x=json.loads(line);stamp=datetime.fromisoformat(x['time']).timestamp()
     if START<=stamp<=END:
      path=re.sub(r'/[0-9]+(?=/|$)','/{id}',x.get('path','').split('?')[0])
      result['nginx_requests'].append({'time':stamp,'method':x.get('method'),'path':path,'status':x.get('status'),'duration':x.get('duration'),**{k:x[k] for k in ['request_id','upstream_status','upstream_time','upstream_response_time','upstream_connect_time','upstream_header_time','upstream_addr'] if k in x}})
    except (ValueError,KeyError,TypeError):pass
 except PermissionError:result['nginx_log_unavailable']=True
result['nginx_status_counts']=dict(Counter(str(r['status']) for r in result['nginx_requests']))
services={'gw':'haproxy','api1':'spacecube','api2':'spacecube','mon':'grafana-server','db1':'mariadb','db2':'mariadb','mongo':'mongod'}
patterns=['Exceeded concurrency','ERROR','Traceback','Timeout','QueuePool','OperationalError','deadlock','Too many connections']
r=subprocess.run(['journalctl','-u',services[ROLE],'--since','@'+str(int(START)),'--until','@'+str(int(END)),'--no-pager','-o','json','--grep','|'.join(patterns)],capture_output=True,text=True)
counts=Counter();minutes=Counter()
for line in r.stdout.splitlines():
 try:
  x=json.loads(line);message=x.get('MESSAGE','');stamp=int(x.get('__REALTIME_TIMESTAMP',0))/1e6
  for pattern in patterns:
   if pattern.lower() in message.lower():counts[pattern]+=1;minutes[(int(stamp//60)*60,pattern)]+=1
 except (ValueError,TypeError):pass
result['journal']={'exit_code':r.returncode,'counts':dict(counts),'by_minute':[{'time':t,'kind':k,'count':n} for (t,k),n in sorted(minutes.items())],'raw_messages_saved':False}
if ROLE in ['db1','db2']:
 sql="SELECT @@max_connections,@@max_user_connections,@@read_only; SELECT max_user_connections FROM mysql.user WHERE User='team4';"
 r=subprocess.run(['mariadb','--batch','--skip-column-names'],input=sql,capture_output=True,text=True)
 result['db_limits']=r.stdout.splitlines();result['db_query_exit']=r.returncode
print(json.dumps(result))
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--label", default="after")
    args = parser.parse_args()
    resources = [
        json.loads(line) for line in (args.report / "resources.jsonl").read_text().splitlines()
    ]
    start = resources[0]["time"]
    end = time.time()
    script = (
        "CODE="
        + repr(CODE)
        + "\nSTART="
        + repr(start)
        + "\nEND="
        + repr(end)
        + "\n"
        + r"""
from pathlib import Path
import concurrent.futures,subprocess,json
cfg=Path.home()/'.config/spacecube109'
roles={'gw':(218,'ubuntu'),'api1':(214,'ubuntu'),'api2':(215,'ubuntu'),'mon':(217,'ubuntu'),'db1':(212,'ubuntu'),'db2':(213,'ubuntu'),'mongo':(216,'test')}
def collect(item):
 role,(end,user)=item
 script='ROLE='+repr(role)+'\nSTART='+repr(START)+'\nEND='+repr(END)+'\n'+CODE
 command='python3 -' if role=='mongo' else 'sudo python3 -'
 r=subprocess.run(['ssh','-i',str(cfg/'id_ed25519'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(cfg/'known_hosts'),f'{user}@192.168.219.{end}',command],input=script,capture_output=True,text=True,timeout=45)
 if r.returncode:return {'role':role,'collection_failed':True}
 return json.loads(r.stdout)
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:print(json.dumps(list(pool.map(collect,roles.items()))))
"""
    )
    result = json.loads(remote(script, timeout=60))
    save(
        args.report / ("server-evidence-" + args.label + ".json"),
        {"start": start, "end": end, "nodes": result},
    )
    print(
        json.dumps(
            [
                {
                    "role": r["role"],
                    "requests": len(r.get("nginx_requests", [])),
                    "journal": r.get("journal", {}).get("counts"),
                    "failed": r.get("collection_failed", False),
                }
                for r in result
            ]
        )
    )


if __name__ == "__main__":
    main()
