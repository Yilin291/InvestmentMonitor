"""Operator-only metadata import. No unverified/sample instruments ship by default."""
import argparse
import json
import os
import re
from .domain import Problem, exact_keys
from .store import Store


def import_instruments(store, payload):
    exact_keys(payload, ['validation_evidence', 'instruments'])
    if not isinstance(payload['validation_evidence'], str) or not payload['validation_evidence'].strip() or not isinstance(payload['instruments'], list) or not 1 <= len(payload['instruments']) <= 10000:
        raise Problem('invalid_instrument_import', '需要核验来源与 1–10000 个标的。')
    with store.tx() as db:
        for item in payload['instruments']:
            exact_keys(item, ['id','market','code','name','asset_class','currency'])
            if not isinstance(item['id'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',item['id']) or item['market'] not in ('SH','SZ','BJ') or not isinstance(item['code'],str) or not re.fullmatch(r'\d{6}',item['code']) or not isinstance(item['name'],str) or not 1 <= len(item['name']) <= 100 or item['asset_class']!='stock' or item['currency']!='CNY':
                raise Problem('invalid_instrument_import', '标的字段不符合 A 股白名单。')
            existing=db.execute('SELECT market,code FROM instruments WHERE id=?',(item['id'],)).fetchone()
            if existing and (existing['market'],existing['code'])!=(item['market'],item['code']):
                raise Problem('instrument_identity_immutable', '既有标的 ID 的市场和代码不能变更。')
            db.execute('INSERT INTO instruments VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,provenance=excluded.provenance',(item['id'],item['market'],item['code'],item['name'],item['asset_class'],item['currency'],payload['validation_evidence']))
    return {'imported':len(payload['instruments']),'validation_evidence':payload['validation_evidence']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['import-instruments']);parser.add_argument('file');args=parser.parse_args()
    store=Store(os.environ.get('PRODUCT_DB_PATH','.product-data/monitor.sqlite'))
    with open(args.file) as f:payload=json.load(f)
    print(json.dumps(import_instruments(store,payload),ensure_ascii=False))
