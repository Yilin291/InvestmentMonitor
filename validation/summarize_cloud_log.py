#!/usr/bin/env python3
"""Read Wrangler concatenated JSON; save an immutable, compact evidence snapshot."""
import json,sys,datetime
from pathlib import Path
source=Path(sys.argv[1]); target=Path(sys.argv[2])
s=source.read_text(); decoder=json.JSONDecoder(); i=0; events=[]; rows=[]
while i<len(s):
 while i<len(s) and s[i].isspace(): i+=1
 if i==len(s): break
 try: event,end=decoder.raw_decode(s,i)
 except json.JSONDecodeError: break # tail may be writing the final event
 i=end
 events.append({'event':event.get('event'),'outcome':event.get('outcome'),'version':event.get('scriptVersion'),'cpu_ms':event.get('cpuTime'),'wall_ms':event.get('wallTime')})
 for log in event.get('logs',[]):
  for msg in log.get('message',[]):
   try: row=json.loads(msg)
   except (ValueError,TypeError): continue
   if row.get('source')=='cloudflare_cron': rows.append(row)
ticks=[r for r in rows if r.get('phase')=='tick']
keys=sorted(set(r['request_key'] for r in ticks))
result={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_file':str(source),'events':events,'logs':rows,'tick_slot_count':len(keys),'tick_keys':keys,'manual_tick_sent':False,'notes':['Cloud scheduler events, local tail is observation only.','A successful HTTP result still requires database business readback.']}
with target.open('x') as f: json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'file':str(target),'events':len(events),'tick_slots':len(keys)}))
