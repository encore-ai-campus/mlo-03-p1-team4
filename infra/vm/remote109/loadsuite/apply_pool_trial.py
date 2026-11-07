"""승인된 109 API 두 대의 풀 용량만 백업 후 변경한다. VM/DB 한도는 유지한다."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from pool_trial import patch_pool
from runner import ROOT, remote, save


def main():
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d-%H%M%S")
    report = ROOT / "logs" / ("pool-trial-" + stamp)
    report.mkdir()
    code = r"""
from pathlib import Path
import subprocess,json,hashlib,time
root=Path('/home/playdata/spacecube109');op=root/'.server-operation.lock'
if op.exists():raise RuntimeError('operation_already_claimed')
board=root/'SERVER_WORK_BOARD.md'
for line in board.read_text().splitlines():
 if line.startswith('| ') and ' | Codex | ' not in line and '진행 중' in line:raise RuntimeError('other_agent_active')
op.mkdir();(op/'owner').write_text('CODEX-POOL-TRIAL');(op/'runner').write_text(STAMP)
with board.open('a') as f:f.write('\n## CODEX-POOL-TRIAL · '+STAMP+'\n사용자 승인: VM 사양/DB 한도 유지, API 풀3+2→5+5만 변경 후 읽기·쓰기100/200/400. 첫 오류 단계 중단. 백업 core/db.py.pool-before-'+STAMP+' 복원 후 spacecube 재시작으로 원복. 다른 배포·부하 금지.\n')
cfg=Path.home()/'.config/spacecube109'
opts=['ssh','-i',str(cfg/'id_ed25519'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(cfg/'known_hosts')]
results=[]
for ip in [214,215]:
 script='STAMP='+repr(STAMP)+'\n'+PATCH+'\n'+GUEST
 r=subprocess.run(opts+['ubuntu@192.168.219.'+str(ip),'sudo python3 -'],input=script,capture_output=True,text=True,timeout=45)
 if r.returncode:raise RuntimeError('pool_trial_failed_'+str(ip)+':'+r.stderr[-200:])
 results.append({'ip':ip,**json.loads(r.stdout)})
(root/'reports'/('pool-trial-'+STAMP+'.json')).write_text(json.dumps(results))
(op/'runner').unlink();(op/'owner').unlink();op.rmdir()
print(json.dumps(results))
"""
    guest = r"""
from pathlib import Path
import shutil,hashlib,subprocess,json,urllib.request,time
p=Path('/opt/spacecube/backend/app/core/db.py');old=p.read_text();new=patch_pool(old)
backup=p.with_name('db.py.pool-before-'+STAMP);shutil.copy2(p,backup)
p.write_text(new)
r=subprocess.run(['systemctl','restart','spacecube'],capture_output=True,text=True)
if r.returncode:p.write_text(old);raise RuntimeError('restart_failed')
healthy=False
for attempt in range(20):
 try:
  with urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3) as response:healthy=json.load(response).get('status')=='ok'
  if healthy:break
 except Exception:pass
 time.sleep(1)
if not healthy:
 p.write_text(old);subprocess.run(['systemctl','restart','spacecube']);raise RuntimeError('health_failed_rolled_back')
print(json.dumps({'backup':str(backup),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'health':healthy,'pool_size':5,'max_overflow':5,'pool_timeout':3}))
"""
    import inspect

    code = (
        "STAMP="
        + repr(stamp)
        + "\nPATCH="
        + repr(inspect.getsource(patch_pool))
        + "\nGUEST="
        + repr(guest)
        + "\n"
        + code
    )
    result = json.loads(remote(code, timeout=130))
    save(report / "deployment.json", result)
    print(str(report))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
