"""Real loopback HTTP tests with temporary SQLite, not cloud acceptance."""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from backend.server import Application, handler
from backend.store import Store
from backend.domain import iso

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'http.sqlite')
        self.app=Application(self.store,password='p'*24,session_secret='s'*32,tick_secret='t'*32)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.app));self.base='http://127.0.0.1:'+str(self.server.server_address[1]);self.app.origin=self.base
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.cookie=''
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def call(self,path,method='GET',body=None,headers=None):
        request=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json','Origin':self.base,'Cookie':self.cookie,**(headers or {})})
        try:
            with urllib.request.urlopen(request,timeout=10) as response:
                if response.headers.get('Set-Cookie'):self.cookie=response.headers['Set-Cookie'].split(';')[0]
                return response.status,json.load(response)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_auth_and_real_calendar_roundtrip(self):
        self.assertEqual(self.call('/api/v1/tasks')[0],401)
        self.assertEqual(self.call('/api/v1/auth/login','POST',{'password':'p'*24})[0],200)
        now=time.time();spec={'name':'HTTP TEST ONLY calendar','instrument_id':None,'rule':{'kind':'calendar_once','scheduled_at':iso(now+0.4)},'schedule':{'mode':'once','timezone':'Asia/Shanghai'},'notification_policy':{'mode':'on_episode','cooldown_seconds':0}}
        status,task=self.call('/api/v1/tasks','POST',spec);self.assertEqual(status,201);id=task['id']
        self.assertEqual(self.call(f'/api/v1/tasks/{id}/activate','POST',{'expected_version':1})[0],200)
        time.sleep(0.45)
        auth={'Authorization':'Bearer '+'t'*32,'Idempotency-Key':'http-real-tick'}
        status,tick=self.call('/internal/monitor/tick','POST',{},auth);self.assertEqual(status,200);self.assertEqual(tick['runs'][0]['decision'],'notify')
        self.assertTrue(self.call('/internal/monitor/tick','POST',{},auth)[1]['duplicate'])
        notes=self.call('/api/v1/notifications')[1];self.assertEqual(len(notes),1)
        self.assertEqual(self.call('/api/v1/notifications/'+notes[0]['id']+'/read','POST',{})[0],200)
        reopened=Store(self.store.path);self.assertEqual(len(reopened.notifications('demo')),1);self.assertEqual(len(reopened.history('demo',id,'runs')),1)
    def test_errors_and_capabilities(self):
        self.call('/api/v1/auth/login','POST',{'password':'p'*24})
        status,value=self.call('/api/v1/tasks','POST',{'tool':'exec'});self.assertEqual(status,400);self.assertTrue(value['request_id']);self.assertIn('code',value)
        self.assertFalse(self.call('/api/v1/capabilities')[1]['market_data']['available'])
        self.assertEqual(self.call('/api/v1/instruments')[1],[])
        self.assertEqual(self.call('/api/v1/auth/logout','POST',{}, {'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.call('/internal/monitor/tick','POST',{})[0],401)
        self.assertEqual(self.call('/api/v1/auth/logout','POST',{})[0],200)
        self.assertEqual(self.call('/api/v1/tasks')[0],401)
