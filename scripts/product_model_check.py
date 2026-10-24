"""Live PRODUCT protocol integration, distinct from V0 vendor connection probes.

Loads only two locally configured provider keys, never echoes them. Uses a
separate temporary database and verified instrument metadata, not market fixtures.
"""
import argparse
import json
import os
import shlex
import tempfile
import time
from pathlib import Path
from backend.manage import import_instruments
from backend.providers import Parser
from backend.store import Store
from backend.domain import Problem
from scripts.product_model_assertions import case_errors, evidence_errors


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--output", default="artifacts/product-model-live-pr01.json")
    output = Path(args.parse_args().output)
    if output.exists():
        raise SystemExit("Evidence already exists; choose a new --output path")
    for line in Path('.env.local').read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        name,value=line.split('=',1)
        name=name.strip().removeprefix('export ')
        if name in ('DEEPSEEK_API_KEY','FUYAO_API_KEY'):
            tokens=shlex.split(value)
            if len(tokens)==1:os.environ[name]=tokens[0]
    evidence={'scope':'real DeepSeek calls through product Parser / RuleVersion contract; temporary DB, no activation','checked_at':time.time(),'cases':[]}
    with tempfile.TemporaryDirectory() as tmp:
        store=Store(Path(tmp)/'product-live.sqlite')
        import_instruments(store,{'validation_evidence':'validation/evidence/ifind_live.json (600519.SH 贵州茅台); A-share CNY instrument metadata, not a quote-unit claim','instruments':[{'id':'CN.SH.600519','market':'SH','code':'600519','name':'贵州茅台','asset_class':'stock','currency':'CNY'}]})
        parser=Parser(store)
        cases=[('normal','贵州茅台最新价高于1500元时提醒我，滚动24小时冷却','ready'),('ambiguous','它涨了就提醒我','needs_clarification'),('unsupported','账户余额高于一万元时提醒我','needs_clarification')]
        for name,text,expected in cases:
            start=time.monotonic()
            try:
                result=parser.parse(text,time.time());errors=case_errors(name,result);item={'name':name,'status':result['status'],'passed':not errors,'semantic_errors':errors,'result':result}
            except Problem as error:item={'name':name,'status':'error','passed':False,'reason_code':error.code}
            item['observed_seconds']=round(time.monotonic()-start,3);evidence['cases'].append(item)
        evidence['audit_count']=store.query('SELECT count(*) AS count FROM parser_audit')[0]['count']
        evidence['tasks_created']=store.query('SELECT count(*) AS count FROM tasks')[0]['count']
    evidence['acceptance_errors']=evidence_errors(evidence)
    evidence['passed']=not evidence['acceptance_errors']
    output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    print(json.dumps({'cases':[{'name':c['name'],'status':c['status'],'passed':c['passed']} for c in evidence['cases']],'tasks_created':evidence['tasks_created']},ensure_ascii=False))
    raise SystemExit(0 if evidence['passed'] else 1)

if __name__=='__main__':main()
