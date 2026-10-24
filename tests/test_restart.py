"""Real process restart with persistent local SQLite; not a cloud rebuild test."""
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from backend.domain import iso

class RestartTests(unittest.TestCase):
    def test_server_restart_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            base=f'http://127.0.0.1:{port}';secret=secrets.token_urlsafe(32);password=secrets.token_urlsafe(32)
            env={**os.environ,'APP_ENV':'development','APP_ORIGIN':base,'PRODUCT_HOST':'127.0.0.1','PRODUCT_PORT':str(port),'PRODUCT_DB_PATH':str(Path(tmp)/'persistent.sqlite'),'DEMO_PASSWORD':password,'SESSION_SECRET':secret,'TICK_SECRET':secret}
            env.pop('FUYAO_VERIFIED_MAPPING',None)
            cookie=''
            def call(path,method='GET',body=None,headers=None):
                nonlocal cookie
                req=urllib.request.Request(base+path,method=method,data=None if body is None else json.dumps(body).encode(),headers={'Origin':base,'Content-Type':'application/json','Cookie':cookie,**(headers or {})})
                with urllib.request.urlopen(req,timeout=5) as r:
                    if r.headers.get('Set-Cookie'):cookie=r.headers['Set-Cookie'].split(';')[0]
                    return json.load(r)
            def start():
                p=subprocess.Popen([sys.executable,'-m','backend.server'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    for _ in range(100):
                        try:call('/api/health');return p
                        except (OSError,urllib.error.URLError):time.sleep(.03)
                    raise AssertionError('local process failed to start')
                except BaseException:p.terminate();p.wait(timeout=5);raise
            process=start()
            try:
                call('/api/v1/auth/login','POST',{'password':password})
                due=time.time()+.3
                spec={'name':'RESTART TEST ONLY','instrument_id':None,'rule':{'kind':'calendar_once','scheduled_at':iso(due)},'schedule':{'mode':'once','timezone':'Asia/Shanghai'},'notification_policy':{'mode':'on_episode','cooldown_seconds':0}}
                task=call('/api/v1/tasks','POST',spec);id=task['id'];call(f'/api/v1/tasks/{id}/activate','POST',{'expected_version':1})
                time.sleep(max(0,due-time.time())+.02)
                call('/internal/monitor/tick','POST',{}, {'Authorization':'Bearer '+secret,'Idempotency-Key':'restart-test-01'})
                before={key:call(path) for key,path in {'task':f'/api/v1/tasks/{id}','versions':f'/api/v1/tasks/{id}/versions','runs':f'/api/v1/tasks/{id}/runs','notifications':'/api/v1/notifications'}.items()}
                process.terminate();process.wait(timeout=5);process=start()
                after={key:call(path) for key,path in {'task':f'/api/v1/tasks/{id}','versions':f'/api/v1/tasks/{id}/versions','runs':f'/api/v1/tasks/{id}/runs','notifications':'/api/v1/notifications'}.items()}
                self.assertEqual(before,after);self.assertEqual(len(after['notifications']),1);self.assertEqual(len(after['runs']),1)
            finally:process.terminate();process.wait(timeout=5)
