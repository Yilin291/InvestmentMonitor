"""Synthetic fixtures only. These tests do not constitute live provider validation."""
import copy
import itertools
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.domain import Problem, combine, evaluate, iso, transition, validate_spec
from backend.engine import Engine
from backend.providers import Parser, FuyaoProvider
from backend.server import Application
from backend.store import Store

NOW = 1800000000.0

def price():
    return {'name': 'TEST ONLY 股票条件', 'instrument_id': 'fixture-stock', 'rule': {'kind': 'price_group', 'combinator': 'all', 'conditions': [{'id': 'p1', 'field': 'last_price', 'operator': 'gt', 'value': '10.00', 'currency': 'CNY'}]}, 'schedule': {'mode': 'market_interval', 'timezone': 'Asia/Shanghai', 'interval_seconds': 300}, 'notification_policy': {'mode': 'on_episode', 'cooldown_seconds': 1000}}

def calendar(at=NOW+100):
    s = price()
    s.update(instrument_id=None, rule={'kind': 'calendar_once', 'scheduled_at': iso(at)}, schedule={'mode': 'once', 'timezone': 'Asia/Shanghai'})
    return s

class Clock:
    def __init__(self): self.now = NOW
    def __call__(self): return self.now

class FixtureProvider:
    freshness_seconds = 60
    def __init__(self): self.value, self.quality, self.market_status = '11', 'valid', 'open'
    def availability(self): return {'available': True, 'test_fixture': True}
    def market(self, now): return {'status': self.market_status, 'source_ref': 'TEST ONLY calendar', 'next_open': now+1000}
    def quote(self, instrument_id, now):
        return {'last_price': {'instrument_id': instrument_id, 'field': 'last_price', 'value': self.value, 'unit': 'CNY', 'source_time': iso(now), 'fetched_at': iso(now), 'provider': 'TEST ONLY', 'source_ref': 'fixture', 'quality': self.quality, 'reason_code': None if self.quality=='valid' else 'fixture_failure'}}

class DomainTests(unittest.TestCase):
    def test_all_three_value_combinations(self):
        for values in itertools.product([True, False, None], repeat=4):
            self.assertEqual(combine(values,'all'), False if False in values else None if None in values else True)
            self.assertEqual(combine(values,'any'), True if True in values else None if None in values else False)

    def test_strict_decimal_boundaries(self):
        p = FixtureProvider(); p.value = '0.300000000000000000000001'
        s = price(); s['rule']['conditions'][0]['value'] = '0.300000000000000000000000'
        self.assertTrue(evaluate(s['rule'],p.quote('fixture-stock',NOW),'fixture-stock',NOW,60)['result'])
        s['rule']['conditions'][0]['value'] = p.value
        for op in ['gt','lt']:
            s['rule']['conditions'][0]['operator']=op
            self.assertFalse(evaluate(s['rule'],p.quote('fixture-stock',NOW),'fixture-stock',NOW,60)['result'])

    def test_unknown_and_cooldown(self):
        s = {'last_result':None,'episode':0,'episode_notified':False,'cooldown_until':0}
        s,d = transition(s,True,0,100); self.assertEqual(d,'notify')
        s,d = transition(s,None,20,100); self.assertEqual(d,'insufficient_data')
        s,d = transition(s,True,30,100); self.assertEqual(d,'already_notified')
        s,d = transition(s,False,40,100); self.assertEqual(d,'no_match')
        s,d = transition(s,True,50,100); self.assertEqual(d,'cooldown_suppressed')
        s,d = transition(s,None,100,100); self.assertEqual(d,'insufficient_data')
        s,d = transition(s,True,101,100); self.assertEqual(d,'notify')
        self.assertEqual(s['episode'],2)

    def test_false_cancels_pending(self):
        s={'last_result':False,'episode':1,'episode_notified':False,'cooldown_until':100}
        s,d=transition(s,True,50,100); self.assertEqual(d,'cooldown_suppressed')
        s,d=transition(s,False,80,100)
        s,d=transition(s,False,120,100); self.assertEqual(d,'no_match')
        s,d=transition(s,True,130,100); self.assertEqual(d,'notify'); self.assertEqual(s['episode'],3)

    def test_bad_observations(self):
        s=price(); p=FixtureProvider()
        cases=[('unit','USD'),('source_time',iso(NOW-61)),('source_time',iso(NOW+100)),('fetched_at',iso(NOW-10)),('instrument_id','other'),('value','NaN'),('value',-1),('source_ref',''),('quality','conflict'),('quality','error')]
        for key,value in cases:
            obs=p.quote('fixture-stock',NOW);obs['last_price'][key]=value
            with self.subTest(key=key,value=value):
                r=evaluate(s['rule'],obs,'fixture-stock',NOW,60);self.assertIsNone(r['result']);self.assertTrue(r['warnings'])

    def test_or_retains_unknown_evidence(self):
        s=price();s['rule']['combinator']='any';s['rule']['conditions'].append({**s['rule']['conditions'][0],'id':'p2'})
        obs=FixtureProvider().quote('fixture-stock',NOW);obs['p2']={'quality':'error','reason_code':'timeout'}
        r=evaluate(s['rule'],obs,'fixture-stock',NOW,60)
        self.assertTrue(r['result']);self.assertEqual(r['warnings'],['timeout'])

    def test_fail_closed_contract(self):
        for mutation in [lambda s:s.update(tool='exec'),lambda s:s['rule']['conditions'][0].update(operator='gte'),lambda s:s['rule']['conditions'][0].update(value=10),lambda s:s['rule'].update(combinator='nested'),lambda s:s.update(instrument_id='unverified'),lambda s:s['schedule'].update(interval_seconds=1)]:
            s=price();mutation(s)
            with self.assertRaises(Problem):validate_spec(s,NOW,lambda i:i=='fixture-stock')
        with self.assertRaises(Problem):validate_spec(calendar(NOW),NOW,lambda i:True)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dbpath=Path(self.tmp.name)/'test.sqlite';self.store=Store(self.dbpath)
        with self.store.tx() as db:db.execute('INSERT INTO instruments VALUES(?,?,?,?,?,?,?)',('fixture-stock','SH','999999','TEST ONLY','stock','CNY','synthetic test fixture'))
        self.clock=Clock();self.provider=FixtureProvider();self.engine=Engine(self.store,self.provider,self.clock)
    def tearDown(self):self.tmp.cleanup()
    def create(self,spec=None):
        t=self.store.create('a',spec or price(),self.clock());self.store.lifecycle('a',t['id'],'activate',1,self.clock());return t['id']
    def run_tick(self,key=None):return self.engine.tick(key or 'tick-'+str(self.clock()))
    def notes(self):return self.store.notifications('a')
    def test_consistent_backup_and_restore(self):
        id=self.create();self.run_tick();target=Path(self.tmp.name)/'backup.sqlite'
        self.assertEqual(self.store.backup(target)['integrity_check'],'ok')
        restored=Store(target);self.assertEqual(len(restored.notifications('a')),1)
        self.assertEqual(len(restored.history('a',id,'versions')),1)
        self.assertEqual(len(restored.history('a',id,'runs')),1)
        self.assertEqual(len(restored.query('SELECT * FROM evidence')),1)
        with self.assertRaises(FileExistsError):self.store.backup(target)

    def test_finish_replay_preserves_audit(self):
        self.create();claim=self.engine.claim();outcome=self.engine.inspect(claim['spec'],self.clock())
        first=self.engine.finish(claim,outcome);before=self.store.query('SELECT * FROM evidence')
        self.assertEqual(self.engine.finish(claim,outcome),first);self.assertEqual(self.store.query('SELECT * FROM evidence'),before)
        self.assertEqual(len(self.notes()),1)

    def test_price_episode_persistence(self):
        id=self.create();self.run_tick();self.assertEqual(len(self.notes()),1)
        self.clock.now+=300;self.run_tick();self.assertEqual(len(self.notes()),1)
        self.provider.value='9';self.clock.now+=300;self.run_tick()
        self.provider.value='11';self.clock.now+=300;r=self.run_tick();self.assertEqual(r['runs'][0]['decision'],'cooldown_suppressed')
        self.clock.now+=300;self.run_tick();self.assertEqual(len(self.notes()),2)
        reopened=Store(self.dbpath);self.assertEqual(len(reopened.notifications('a')),2);self.assertEqual(len(reopened.history('a',id,'runs')),5)
    def test_preview_has_no_database_side_effects(self):
        id=self.create();self.run_tick();before=self.store.query('SELECT * FROM runtime');notes=self.notes();runs=self.store.query('SELECT * FROM runs')
        self.engine.preview(price());self.assertEqual(before,self.store.query('SELECT * FROM runtime'));self.assertEqual(notes,self.notes());self.assertEqual(runs,self.store.query('SELECT * FROM runs'))
    def test_edit_invalidates_inflight(self):
        id=self.create();claim=self.engine.claim();out=self.engine.inspect(claim['spec'],self.clock())
        self.store.edit('a',id,price(),1,self.clock());result=self.engine.finish(claim,out)
        self.assertEqual(result['decision'],'superseded');self.assertFalse(self.notes());self.assertEqual(self.store.get('a',id,self.clock())['version'],2)
        self.run_tick();self.assertEqual(len(self.notes()),1)
    def test_pause_resume_invalidates_inflight(self):
        id=self.create();claim=self.engine.claim();self.store.lifecycle('a',id,'pause',None,self.clock());self.store.lifecycle('a',id,'resume',1,self.clock())
        self.assertEqual(self.engine.finish(claim,self.engine.inspect(claim['spec'],self.clock()))['decision'],'superseded');self.assertFalse(self.notes())
    def test_delete_invalidates_inflight(self):
        id=self.create();claim=self.engine.claim();self.store.lifecycle('a',id,'delete',None,self.clock())
        self.assertEqual(self.engine.finish(claim,self.engine.inspect(claim['spec'],self.clock()))['decision'],'superseded')
        self.assertIsNone(self.engine.claim())
    def test_edit_retains_cooldown_and_immutable_versions(self):
        id=self.create();self.run_tick();old=self.store.get('a',id,self.clock())['runtime']['state']['cooldown_until']
        self.store.edit('a',id,price(),1,self.clock());self.assertEqual(self.store.get('a',id,self.clock())['runtime']['state']['cooldown_until'],old)
        self.assertEqual(self.run_tick('edited-tick')['runs'][0]['decision'],'cooldown_suppressed')
        with self.assertRaises(Problem):self.store.edit('a',id,price(),1,self.clock())
        with self.assertRaises(Exception):
            with self.store.tx() as db:db.execute('UPDATE rule_versions SET spec=?',('{}',))
    def test_concurrent_tick_and_replay(self):
        self.create()
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda i:Engine(Store(self.dbpath),self.provider,self.clock).tick('same-request'),range(8)))
        self.assertEqual(len(self.notes()),1);self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.clock.now+=300
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda i:Engine(Store(self.dbpath),self.provider,self.clock).tick('new-request-'+str(i)),range(8)))
        self.assertEqual(len(self.notes()),1);self.assertEqual(len(self.store.query('SELECT * FROM runs')),2)
    def test_lease_expiry(self):
        self.create();a=self.engine.claim();self.clock.now+=91;b=self.engine.claim()
        self.assertEqual(self.engine.finish(a,self.engine.inspect(a['spec'],self.clock()))['decision'],'superseded')
        self.assertEqual(self.engine.finish(b,self.engine.inspect(b['spec'],self.clock()))['decision'],'notify');self.assertEqual(len(self.notes()),1)
    def test_gap_and_overdue(self):
        id=self.create();self.clock.now+=1800
        self.assertTrue(self.store.get('a',id,self.clock())['runtime']['overdue'])
        self.run_tick();runs=self.store.history('a',id,'runs');self.assertEqual(len(runs),1);self.assertEqual(runs[0]['detail']['gap']['missed_intervals'],6)
    def test_failure_recovery(self):
        id=self.create();self.provider.quality='error';self.run_tick();t=self.store.get('a',id,self.clock());self.assertEqual(t['runtime']['health'],'failed');self.assertFalse(self.notes())
        self.clock.now+=300;self.provider.quality='valid';self.run_tick();self.assertEqual(len(self.notes()),1)
        self.assertTrue(any(a['action']=='recovered' for a in self.store.history('a',id,'audit')))
    def test_calendar_failure_not_closed(self):
        id=self.create();self.provider.market_status='unknown';self.run_tick();self.assertEqual(self.store.get('a',id,self.clock())['runtime']['decision'],'insufficient_data')
    def test_closed_market_next_open(self):
        id=self.create();self.provider.market_status='closed';self.run_tick();t=self.store.get('a',id,self.clock());self.assertEqual(t['runtime']['decision'],'skipped_closed');self.assertEqual(t['runtime']['next_run'],NOW+1000);self.assertFalse(self.notes())
    def test_calendar_late_and_read_idempotent(self):
        id=self.create(calendar());self.clock.now+=150;self.run_tick();self.assertEqual(len(self.notes()),1)
        self.assertEqual(self.notes()[0]['detail']['evidence']['calendar']['late_seconds'],50)
        state=self.store.query('SELECT * FROM runtime');nid=self.notes()[0]['id'];self.store.mark_read('a',nid,self.clock());self.clock.now+=1;self.store.mark_read('a',nid,self.clock())
        self.assertEqual(self.store.query('SELECT * FROM runtime'),state);self.assertEqual(self.notes()[0]['read_at'],NOW+150)
        self.store.lifecycle('a',id,'pause',None,self.clock());self.store.lifecycle('a',id,'resume',1,self.clock());self.run_tick();self.assertEqual(len(self.notes()),1)
    def test_calendar_missed(self):
        id=self.create(calendar());self.clock.now+=86600;self.run_tick();self.assertFalse(self.notes());self.assertEqual(self.store.get('a',id,self.clock())['runtime']['decision'],'missed')
    def test_calendar_new_date(self):
        id=self.create(calendar());self.clock.now+=100;self.run_tick();self.store.edit('a',id,calendar(self.clock()+100),1,self.clock());self.clock.now+=100;self.run_tick();self.assertEqual(len(self.notes()),2)
    def test_ownership_and_limit(self):
        id=self.create()
        for fn in [lambda:self.store.get('b',id,NOW),lambda:self.store.edit('b',id,price(),1,NOW),lambda:self.store.lifecycle('b',id,'delete',None,NOW),lambda:self.store.history('b',id,'runs')]:
            with self.assertRaises(Problem) as c:fn()
            self.assertEqual(c.exception.status,404)
        for _ in range(9):self.store.create('a',price(),NOW)
        with self.assertRaises(Problem):self.store.create('a',price(),NOW)
    def test_auth_csrf_tick(self):
        app=Application(self.store,self.provider,password='p'*24,session_secret='s'*32,tick_secret='t'*32)
        with self.assertRaises(Problem):app.dispatch('GET','/api/v1/tasks',{}, {},{})
        with self.assertRaises(Problem):app.dispatch('POST','/api/v1/auth/login',{}, {'password':'p'*24},{'Origin':'https://evil.example'})
        _,_,headers=app.dispatch('POST','/api/v1/auth/login',{}, {'password':'p'*24},{'Origin':'http://127.0.0.1:8080'})
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.assertEqual(app.dispatch('GET','/api/v1/tasks',{}, {},{'Cookie':headers['Set-Cookie']})[0],200)
        with self.assertRaises(Problem):app.dispatch('POST','/internal/monitor/tick',{}, {},{})
    def test_parser_invalid_tool_rejected(self):
        def transport(*args,**kwargs):return {'choices':[{'message':{'content':json.dumps({'drafts':[dict(price(),tool='exec')],'questions':[],'unsupported':[]})}}]}
        with self.assertRaises(Problem):Parser(self.store,transport,'test-key').parse('test',NOW)
        self.assertEqual(self.store.query('SELECT outcome FROM parser_audit')[0]['outcome'],'rejected');self.assertFalse(self.store.listing('a',NOW))
    def test_parser_valid_and_ambiguity(self):
        response={'drafts':[price()],'questions':[],'unsupported':[]}
        def transport(*args,**kwargs):return {'choices':[{'message':{'content':json.dumps(response)}}]}
        parser=Parser(self.store,transport,'test-key');self.assertEqual(parser.parse('test',NOW)['status'],'ready')
        response['questions']=['自然日还是滚动24小时？'];self.assertEqual(parser.parse('test',NOW)['drafts'],[])
    def test_missing_credentials_no_fixture_fallback(self):
        old=os.environ.pop('FUYAO_VERIFIED_MAPPING',None)
        try:self.assertEqual(FuyaoProvider(self.store).market(NOW)['status'],'unknown')
        finally:
            if old:os.environ['FUYAO_VERIFIED_MAPPING']=old
        self.assertEqual(Parser(self.store,key='').parse('提醒',NOW)['status'],'unavailable')

if __name__=='__main__':unittest.main()
