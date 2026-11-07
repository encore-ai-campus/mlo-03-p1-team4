"""7개 VM의 임시 1초 관측기를 시작/종료하고 집계 표본만 회수한다."""

import argparse
import json

from runner import HERE, remote, save


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("action", choices=["start", "stop"])
    args = parser.parse_args()
    code = r"""
from pathlib import Path
import subprocess,concurrent.futures,json,re
assert re.fullmatch(r'capacity-(book|public)-[0-9-]+',RUN)
cfg=Path.home()/'.config/spacecube109'
opts=['ssh','-i',str(cfg/'id_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(cfg/'known_hosts')]
roles={'gw':(218,'ubuntu'),'api1':(214,'ubuntu'),'api2':(215,'ubuntu'),'mon':(217,'ubuntu'),'db1':(212,'ubuntu'),'db2':(213,'ubuntu'),'mongo':(216,'test')}
def work(item):
 name,(ip,user)=item
 try:
  x=subprocess.run(opts+[f'{user}@192.168.219.{ip}','python3 -'],input='RUN='+repr(RUN)+'\nCODE='+repr(CODE)+'\nACTION='+repr(ACTION)+'\n'+GUEST,capture_output=True,text=True,timeout=30)
  if x.returncode:raise RuntimeError('guest_observer_failed')
  return {'server':name,**json.loads(x.stdout)}
 except Exception as error:return {'server':name,'error':type(error).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:result=list(pool.map(work,roles.items()))
print(json.dumps(result))
"""
    guest = r"""
from pathlib import Path
import subprocess,os,json,time,signal,gzip,base64
root=Path('/tmp/spacecube-capacity')/RUN
if ACTION=='start':
 root.mkdir(parents=True,mode=0o700,exist_ok=False)
 script=root/'observer.py';script.write_text(CODE)
 with (root/'samples.jsonl').open('w') as out,(root/'observer.err').open('w') as err:
  p=subprocess.Popen(['python3',str(script)],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
 (root/'pid').write_text(str(p.pid))
 print(json.dumps({'pid':p.pid,'path':str(root)}))
else:
 pid=int((root/'pid').read_text())
 proc=Path('/proc')/str(pid)/'cmdline'
 if proc.exists():
  assert str(root/'observer.py').encode() in proc.read_bytes()
  os.kill(pid,signal.SIGTERM)
  for i in range(30):
   if not proc.exists() or not proc.read_bytes():break
   time.sleep(.1)
 data=(root/'samples.jsonl').read_bytes()
 print(json.dumps({'samples':len(data.splitlines()),'gzip':base64.b64encode(gzip.compress(data)).decode(),'stderr':(root/'observer.err').read_text()[-100:]}))
"""
    script = (
        "RUN="
        + repr(args.report.name)
        + "\nACTION="
        + repr(args.action)
        + "\nCODE="
        + repr((HERE / "guest_observer.py").read_text(encoding="utf-8"))
        + "\nGUEST="
        + repr(guest)
        + "\n"
        + code
    )
    result = json.loads(remote(script, timeout=60))
    if args.action == "stop":
        import base64

        for row in result:
            if "gzip" in row:
                (args.report / ("vm-1s-" + row["server"] + ".jsonl.gz")).write_bytes(
                    base64.b64decode(row.pop("gzip"))
                )
    save(args.report / ("vm-observers-" + args.action + ".json"), result)
    print(
        json.dumps(
            result
            if args.action == "start"
            else [{k: v for k, v in x.items() if k != "stderr"} for x in result]
        )
    )
    if len(result) != 7 or any(
        x.get("error") or (args.action == "stop" and not x.get("samples")) for x in result
    ):
        raise RuntimeError("vm_observation_failed")


if __name__ == "__main__":
    main()
