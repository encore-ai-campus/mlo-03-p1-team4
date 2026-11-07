"""자기 합성 계정의 예약/결제/슬롯 및 Mongo 적재 건수만 집계한다."""

import argparse
import json
from pathlib import Path

from runner import remote, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    fixture = json.loads((args.report / "fixtures.json").read_text())
    ids = [int(v["user_id"]) for v in fixture["accounts"]]
    if not ids or any(v <= 0 for v in ids):
        raise ValueError("invalid_account_ids")
    joined = ",".join(str(v) for v in ids)
    sql = (
        "SELECT 'users',COUNT(*) FROM spacecube.users WHERE user_id IN ("  # noqa: S608 API ID를 int로 변환·양수 검증한 숫자 목록만 사용
        + joined
        + "); SELECT r.status,p.status,COUNT(*) FROM spacecube.reservations r JOIN spacecube.payments p ON p.reservation_id=r.reservation_id WHERE r.user_id IN ("
        + joined
        + ") GROUP BY r.status,p.status; SELECT 'remaining_slots',COUNT(*) FROM spacecube.reservation_slots s JOIN spacecube.reservations r ON r.reservation_id=s.reservation_id WHERE r.user_id IN ("
        + joined
        + "); SELECT 'synthetic_reservations',SUM(is_synthetic=1),COUNT(*) FROM spacecube.reservations WHERE user_id IN ("
        + joined
        + "); SELECT @@max_connections,@@max_user_connections,@@read_only;"
    )
    db_code = (
        "SQL="
        + repr(sql)
        + "\n"
        + r"""
import json,subprocess
r=subprocess.run(['mariadb','--batch','--skip-column-names'],input=SQL,capture_output=True,text=True,check=True)
s=subprocess.run(['mariadb','--batch','-e','SHOW SLAVE STATUS'],capture_output=True,text=True,check=True).stdout.splitlines();replica={}
if len(s)>1:
 x=dict(zip(s[0].split('\t'),s[1].split('\t')));replica={k:x.get(k) for k in ['Slave_IO_Running','Slave_SQL_Running','Seconds_Behind_Master','Last_IO_Errno','Last_SQL_Errno']}
print(json.dumps({'rows':r.stdout.splitlines(),'replication':replica}))
"""
    )
    mongo_code = (
        "IDS="
        + repr(ids)
        + "\n"
        + r"""
import json
from pymongo import MongoClient
c=MongoClient(URL,serverSelectionTimeoutMS=5000,maxPoolSize=1)
coll=c['space_rental_analytics']['events']
query={'user.user_id':{'$in':list(map(str,IDS))}}
rows=list(coll.aggregate([{'$match':query},{'$group':{'_id':'$event_name','count':{'$sum':1}}}]))
print(json.dumps({'own_event_names':rows,'own_events':coll.count_documents(query),'own_synthetic_events':coll.count_documents({**query,'is_synthetic':True}),'event_daily_total':c['space_rental_analytics']['event_daily'].count_documents({}),'events_total':coll.estimated_document_count()}))
"""
    )
    script = (
        "DB_CODE="
        + repr(db_code)
        + "\nMONGO_CODE="
        + repr(mongo_code)
        + "\n"
        + r"""
from pathlib import Path
import subprocess,json,concurrent.futures
cfg=Path.home()/'.config/spacecube109';base=['ssh','-i',str(cfg/'id_ed25519'),'-o','BatchMode=yes','-o','UserKnownHostsFile='+str(cfg/'known_hosts')]
def db(end):
 r=subprocess.run(base+[f'ubuntu@192.168.219.{end}','sudo python3 -'],input=DB_CODE,capture_output=True,text=True,timeout=25)
 if r.returncode:raise RuntimeError('db_audit_failed')
 return {'ip':end,**json.loads(r.stdout)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:dbs=list(pool.map(db,[212,213]))
v=dict(line.split('=',1) for line in (cfg/'app/.env').read_text().splitlines() if '=' in line)
r=subprocess.run(base+['ubuntu@192.168.219.214','/opt/spacecube/venv/bin/python -'],input='URL='+repr(v['MONGO_URL'])+'\n'+MONGO_CODE,capture_output=True,text=True,timeout=25)
if r.returncode:raise RuntimeError('mongo_audit_failed')
print(json.dumps({'dbs':dbs,'mongo':json.loads(r.stdout)}))
"""
    )
    result = json.loads(remote(script, timeout=60))
    save(args.report / "write-data-audit.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
