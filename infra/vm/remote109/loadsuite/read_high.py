"""읽기 100/200/400명만 실행한다. 합성 계정/예약 생성·쓰기 부하는 하지 않는다."""

import json
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from runner import HERE, ROOT, Suite, remote, save


def grafana_source(report):
    storage = json.loads(
        (HERE.parent.parent / "lab/dashboard-storage.json").read_text(encoding="utf-8")
    )
    code = r"""
from pathlib import Path
import json,shutil,time,base64,urllib.request,os,pwd
root=Path('/var/lib/grafana/dashboards');backup=Path('/var/backups/spacecube-monitoring')/('fixed-source-'+str(int(time.time())));backup.mkdir()
common='109 219망 VM 7대. MariaDB exporter 2대 정상, 전체 19 targets. MongoDB 온라인/exporter 미설치. FastAPI는 현재 수집 워커 기준이며 빈 구간은 0이 아닙니다.'
for path in root.glob('dashboard-*.json'):
 old=json.loads(path.read_text());shutil.copy2(path,backup/path.name)
 d=STORAGE if old['uid']=='spacecube-storage' else old
 d['description']=common
 if d['uid']=='spacecube-overview':
  for p in d['panels']:
   if p.get('type')=='text' and 'DB .212/.213' in p.get('options',{}).get('content',''):
    p['options']['content']='DB .212/.213 node/mysqld exporter 정상, Mongo .216 온라인. 앱별 연결/행 잠금은 DB 연결·대기 화면. 요청은 Nginx 합계이며 정적/health 포함. FastAPI 카운터는 수집 워커 기준.'
 d.pop('id',None);d['version']=int(d.get('version',0))+1;d['timezone']='Asia/Seoul';d['refresh']='15s';d['time']={'from':'now-30m','to':'now'}
 temp=path.with_suffix('.json.next');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.chmod(temp,0o644);u=pwd.getpwnam('grafana');os.chown(temp,u.pw_uid,u.pw_gid);temp.replace(path)
header=base64.b64encode(('admin:'+PASSWORD).encode()).decode()
def api(path,payload=None):
 req=urllib.request.Request('http://127.0.0.1:3000/api/'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':'Basic '+header,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
api('admin/provisioning/dashboards/reload',{})
print(json.dumps({'backup':str(backup),'files':{p.name:json.loads(p.read_text()) for p in root.glob('dashboard-*.json')}}))
""".replace("STORAGE", repr(storage))
    wrapper = (
        "code="
        + repr(code)
        + "\n"
        + r"""
from pathlib import Path
import subprocess
cfg=Path.home()/'.config/spacecube109';v=dict(l.split('=',1) for l in (cfg/'grafana/.env').read_text().splitlines() if '=' in l)
script='PASSWORD='+repr(v['GF_SECURITY_ADMIN_PASSWORD'])+'\n'+code
r=subprocess.run(['ssh','-i',str(cfg/'id_ed25519'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(cfg/'known_hosts'),'ubuntu@192.168.219.217','sudo python3 -'],input=script,capture_output=True,text=True,timeout=30)
if r.returncode:raise SystemExit('grafana_source_failed')
print(r.stdout)
"""
    )
    result = json.loads(remote(wrapper))
    save(report / "grafana-source.json", result)
    print("GRAFANA_FILE_SOURCE_SAVED", flush=True)
    # 공급 폴링 주기(30초)를 넘긴 뒤 다시 확인한다.
    time.sleep(35)
    check = (
        code[code.index("header=") : code.index("api('admin/")]
        + "\nprint(json.dumps({uid: {'title':api('dashboards/uid/'+uid)['dashboard']['title'],'panels':len(api('dashboards/uid/'+uid)['dashboard']['panels'])} for uid in ['spacecube-storage','spacecube-db-connections']}))"
    )
    check = "import base64,urllib.request,json\n" + check
    check_wrapper = wrapper.replace(repr(code), repr(check))
    observed = json.loads(remote(check_wrapper))
    if observed["spacecube-storage"]["panels"] != len(storage["panels"]):
        raise RuntimeError("grafana_panel_persistence_failed")
    if observed["spacecube-storage"]["title"] != storage["title"]:
        raise RuntimeError("grafana_title_persistence_failed")
    save(report / "grafana-after-refresh.json", observed)
    print("GRAFANA_AFTER_POLL_VERIFIED", flush=True)


class ReadSuite(Suite):
    def prepare(self):
        self.key = remote(
            "from pathlib import Path;v=dict(l.split('=',1) for l in (Path.home()/'.config/spacecube109/app/.env').read_text().splitlines() if '=' in l);print(v['SYNTHETIC_API_KEY'])"
        ).strip()
        self.api("GET", "/health")
        save(self.report / "openapi.json", self.api("GET", "/openapi.json"))
        venues = self.api("GET", "/venues", params={"size": 50})
        details = [self.api("GET", f"/venues/{v['venue_id']}") for v in venues["items"]]
        dates = self.api(
            "GET",
            f"/venues/{details[0]['venue_id']}/available-dates",
            params={"offset": 0, "days": 1},
        )
        today = date.fromisoformat(dates["dates"][0]["date"])
        self.fixture = {
            "venues": details,
            "tomorrow": (today + timedelta(days=1)).isoformat(),
            "accounts": [],
        }
        save(self.report / "fixtures.json", self.fixture)
        self.stage_remote_sampler()
        self.sampler = threading.Thread(target=self.sample_loop, daemon=True)
        self.sampler.start()
        time.sleep(6)


def main():
    stamp = datetime.fromtimestamp(time.time(), ZoneInfo("Asia/Seoul")).strftime("%Y%m%d-%H%M%S")
    suite = ReadSuite("http://192.168.219.218", ROOT / "logs" / ("read-high-" + stamp))
    print("REPORT " + str(suite.report), flush=True)
    error = None
    try:
        suite.claim()
        grafana_source(suite.report)
        suite.prepare()
        for users in [100, 200, 400]:
            suite.run_phase("public", users, 180, 60)
            suite.recover(120)
    except Exception as exception:
        error = str(exception)
        print("STOP " + error, flush=True)
    finally:
        suite.finish(error)
    print("READ_FINISHED_REVIEW_BEFORE_WRITE " + str(suite.report / "RESULTS.md"), flush=True)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
