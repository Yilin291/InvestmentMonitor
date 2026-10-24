"""Actual product preview integration. No activation, no invented units/times."""
import json,os,shlex,tempfile,time
from pathlib import Path
from backend.store import Store
from backend.manage import import_instruments
from backend.providers import FuyaoProvider
from backend.engine import Engine

for line in Path('.env.local').read_text().splitlines():
    if '=' not in line or line.lstrip().startswith('#'):continue
    name,value=line.split('=',1);name=name.strip().removeprefix('export ')
    if name=='FUYAO_API_KEY':
        tokens=shlex.split(value)
        if len(tokens)==1:os.environ[name]=tokens[0]
with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp)/'product-quote.sqlite')
    import_instruments(store,{'validation_evidence':'validation/evidence/ifind_live.json + validation/evidence/fuyao_live_rerun.json','instruments':[{'id':'CN.SH.600519','market':'SH','code':'600519','name':'贵州茅台','asset_class':'stock','currency':'CNY'}]})
    spec=json.loads(Path('artifacts/product-model-live.json').read_text())['cases'][0]['result']['drafts'][0]
    outcome=Engine(store,FuyaoProvider(store)).preview(spec)
    evidence={'scope':'real Fuyao product preview with real product DeepSeek draft; temporary database; no activation','checked_at':time.time(),'preview':outcome,'formal_tasks_created':len(store.listing('demo',time.time())),'notification_count':len(store.notifications('demo'))}
    Path('artifacts/product-quote-live.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    print(json.dumps({'result':outcome['result'],'warnings':outcome['warnings'],'evidence_count':len(outcome['evidence']),'formal_tasks_created':evidence['formal_tasks_created']},ensure_ascii=False))
