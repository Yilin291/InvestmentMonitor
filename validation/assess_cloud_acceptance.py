#!/usr/bin/env python3
"""Assess saved real scheduler/DB evidence; never calls an endpoint."""
import json,sys,datetime
from pathlib import Path
cloud=json.loads(Path(sys.argv[1]).read_text())
db=json.loads(Path(sys.argv[2]).read_text())
out=Path(sys.argv[3])
logs=cloud['logs']; ticks=[r for r in logs if r.get('phase')=='tick' and r.get('scheduler_mode')=='active']
bykey={}
for r in ticks: bykey.setdefault(r['request_key'],[]).append(r)
keys=sorted(bykey); minutes=sorted(int(k.rsplit(':',1)[1]) for k in keys)
rows={r['request_key']:r for r in db['rows']}
checks={
 'at_least_three_slots':len(keys)>=3,
 'at_least_30_minutes':bool(minutes) and (minutes[-1]-minutes[0])>=30,
 'no_missing_minute':bool(minutes) and len(minutes)==minutes[-1]-minutes[0]+1,
 'all_slots_have_accepted_response':all(any(r.get('http_status')==200 and r.get('status')=='accepted_requires_business_readback' for r in rs) for rs in bykey.values()),
 'all_slots_persisted':all(k in rows and rows[k]['finished_at'] is not None for k in keys),
 'key_matches_planned_minute':all(int(r['request_key'].rsplit(':',1)[1])==r['scheduled_time_ms']//60000 for r in ticks),
}
expected={'48bf9e848e5a4b29ba47241a4636ab3e':('notify',1), '67c22ac8c03742a9939a6f4fa98c278b':('notify',1),'546597e801114893915b4fa98c978d0a':('no_match',0),'57a30a61beea43ee85e48e748c12f314':('notify',1)}
tasks=[]
for task_id,(decision,count) in expected.items():
 rr=[r for r in rows.values() if r.get('run') and r['run']['task_id']==task_id]
 notes=[n for r in rr for n in r['notifications']]
 valid=len(rr)==1 and rr[0]['outcome']['decision']==decision and len(notes)==count and len(rr[0]['evidence'])==1
 checks['task_'+task_id]=valid
 tasks.append({'task_id':task_id,'runs':len(rr),'notification_ids':[n['id'] for n in notes],'run_ids':[r['run']['id'] for r in rr],'passed':valid})
# Cross-check the persisted real bar and rule semantics, not only decisions.
price_cases={
 '67c22ac8c03742a9939a6f4fa98c278b':('CN.SH.600519','1335.0','1336.0',True),
 '546597e801114893915b4fa98c978d0a':('CN.SH.601318','51.76','50.76',False),
 '57a30a61beea43ee85e48e748c12f314':('CN.SH.600036','41.77','42.77',True),
}
from decimal import Decimal
for task_id,(instrument,price,threshold,truth) in price_cases.items():
 rr=[r for r in rows.values() if r.get('run') and r['run']['task_id']==task_id]
 valid=False
 if len(rr)==1 and len(rr[0]['evidence'])==1:
  detail=json.loads(rr[0]['evidence'][0]['detail']);ob=detail.get('observation',{});cond=detail.get('condition',{})
  valid=(ob.get('instrument_id')==instrument and ob.get('value')==price and ob.get('unit')=='CNY' and ob.get('adjust')=='none' and ob.get('trade_date')=='2026-10-23' and bool(ob.get('request_id')) and cond.get('field')=='close_price' and cond.get('operator')=='lt' and cond.get('value')==threshold and detail.get('result') is truth and (Decimal(price)<Decimal(threshold)) is truth)
 checks['real_close_semantics_'+task_id]=valid
replay=[r for r in logs if r.get('phase')=='validation_replay']
checks['cloud_same_key_replay']=any(r.get('http_status')==200 and r.get('business',{}).get('duplicate') is True for r in replay)
health=[r for r in logs if r.get('phase')=='health' and r.get('scheduler_mode')=='active']
releases=sorted(set(r.get('product_release') for r in health if r.get('product_release')))
checks['observed_product_redeploy']='deno-close-v10' in releases and 'deno-close-v11' in releases
checks['no_recorded_primary_failure']=all(r.get('status')!='failed' for r in logs if r.get('scheduler_mode')=='active' and r.get('phase')!='validation_replay')
result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'evidence':[sys.argv[1],sys.argv[2]],'checks':checks,'passed':all(checks.values()),'slot_count':len(keys),'observed_minutes':minutes[-1]-minutes[0] if minutes else 0,'product_releases':releases,'max_lateness_ms':max((r['lateness_ms'] for r in ticks),default=None),'tasks':tasks,'limits':['Only this observed window is assessed; no promise of indefinite availability.','Scheduled one-off duplicate replay is explicitly TEST; primary slots are real cron execution.','Cached real completed daily bars were reused; this is not live intraday validation.','Database readback is read-only, not a disaster-recovery restore.']}
with out.open('x') as f: json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'file':str(out),'passed':result['passed'],'slot_count':len(keys),'observed_minutes':result['observed_minutes'],'failed_checks':[k for k,v in checks.items() if not v]}))
sys.exit(0 if result['passed'] else 1)
