"""HTTP transport and deploy contract tests; temporary databases only."""
import io
import http.client
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
from backend.server import Application
from backend.serve import preflight, server_options
from backend.store import Store
from backend.wsgi import WebApplication

class WsgiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.now=100
        self.app=Application(Store(root/'test.sqlite'),password='p'*24,session_secret='s'*32,tick_secret='t'*32,origin='https://example.test')
        (root/'index.html').write_text('<html>product</html>');(root/'.secret').write_text('must-not-serve')
        self.web=WebApplication(self.app,root,clock=lambda:self.now)
    def tearDown(self):self.tmp.cleanup()
    def call(self,path,method='GET',body=b'',**overrides):
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'','HTTP_HOST':'example.test','HTTP_ORIGIN':'https://example.test','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),**overrides}
        response={}
        def start(status,headers):response.update(status=int(status.split()[0]),headers=dict(headers))
        response['body']=b''.join(self.web(env,start));return response
    def test_auth_cookie_and_security_headers(self):
        self.assertEqual(self.call('/api/v1/tasks')['status'],401)
        r=self.call('/api/v1/auth/login','POST',json.dumps({'password':'p'*24}).encode());self.assertEqual(r['status'],200)
        self.assertIn('HttpOnly',r['headers']['Set-Cookie']);self.assertIn('Secure',r['headers']['Set-Cookie']);self.assertIn('Strict-Transport-Security',r['headers'])
        self.assertEqual(self.call('/api/v1/tasks',HTTP_COOKIE=r['headers']['Set-Cookie'])['status'],200)
    def test_body_and_method_limits(self):
        for body,status in [(b'x'*32769,413),(b'[]',400),(b'{"x":NaN}',400),(b'\xff',400)]:
            self.assertEqual(self.call('/api/v1/auth/login','POST',body)['status'],status)
        self.assertEqual(self.call('/api/v1/auth/login','POST',b'{}',CONTENT_TYPE='text/plain')['status'],415)
        self.assertEqual(self.call('/api/v1/auth/login','POST',b'{}',CONTENT_LENGTH='5')['status'],400)
        self.assertEqual(self.call('/api/health','TRACE')['status'],405)
    def test_host_origin_and_forwarded_spoofing(self):
        self.assertEqual(self.call('/api/health',HTTP_HOST='evil.test',HTTP_X_FORWARDED_HOST='example.test')['status'],400)
        self.assertEqual(self.call('/api/v1/auth/login','POST',b'{}',HTTP_ORIGIN='https://evil.test')['status'],403)
        self.assertEqual(self.call('/api/v1/tasks',HTTP_X_FORWARDED_FOR='127.0.0.1')['status'],401)
    def test_static_head_and_traversal(self):
        self.assertEqual(self.call('/')['body'],b'<html>product</html>')
        r=self.call('/','HEAD');self.assertEqual(r['body'],b'');self.assertEqual(int(r['headers']['Content-Length']),20)
        for path in ['/../.secret','/.secret','/missing.js']:
            self.assertEqual(self.call(path)['status'],404)
        self.assertEqual(self.call('/tasks/route')['status'],200)
    def test_login_rate_limit(self):
        for _ in range(10):self.assertEqual(self.call('/api/v1/auth/login','POST',b'{}')['status'],401)
        r=self.call('/api/v1/auth/login','POST',b'{}');self.assertEqual(r['status'],429);self.assertEqual(r['headers']['Retry-After'],'60')
        self.now+=61;self.assertEqual(self.call('/api/v1/auth/login','POST',b'{}')['status'],401)
    def test_busy_tick_and_authorization(self):
        self.assertEqual(self.call('/internal/monitor/tick','POST',b'{}')['status'],401)
        self.web.tick_slots.acquire()
        try:self.assertEqual(self.call('/internal/monitor/tick','POST',b'{}')['status'],503)
        finally:self.web.tick_slots.release()
        r=self.call('/internal/monitor/tick','POST',b'{}',HTTP_AUTHORIZATION='Bearer '+'t'*32,HTTP_IDEMPOTENCY_KEY='wsgi-test-key')
        self.assertEqual(r['status'],200)
    def test_unexpected_errors_do_not_leak(self):
        def fail(*args):raise RuntimeError('SECRET_SENTINEL')
        self.app.dispatch=fail;r=self.call('/api/health');self.assertEqual(r['status'],500);self.assertNotIn(b'SECRET_SENTINEL',r['body']);self.assertIn('X-Request-ID',r['headers'])
    def test_production_guard_and_platform_port(self):
        with self.assertRaises(RuntimeError):preflight({'APP_ENV':'production','APP_ORIGIN':'http://insecure.test'})
        with self.assertRaisesRegex(RuntimeError,'production_storage_not_ready'):preflight({'APP_ENV':'production','APP_ORIGIN':'https://example.test'})
        options=server_options({'PRODUCT_HOST':'0.0.0.0','PORT':'9000'});self.assertEqual(options['port'],9000);self.assertEqual(options['host'],'0.0.0.0');self.assertEqual(options['threads'],8);self.assertEqual(options['max_request_body_size'],32768)

class WaitressProcessTests(unittest.TestCase):
    def test_root_entry_real_http_and_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            origin=f'http://127.0.0.1:{port}';secret=secrets.token_urlsafe(32)
            env={**os.environ,'APP_ENV':'development','APP_ORIGIN':origin,'PRODUCT_HOST':'127.0.0.1','PORT':str(port),'PRODUCT_DB_PATH':str(Path(tmp)/'waitress.sqlite'),'DEMO_PASSWORD':secret,'SESSION_SECRET':secret,'TICK_SECRET':secret}
            env.pop('FUYAO_VERIFIED_MAPPING',None)
            p=subprocess.Popen(['sh','scripts/start.sh'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(origin+'/api/health',timeout=2) as r:
                            self.assertIn('watchlist',r.headers['Server']);self.assertEqual(json.load(r)['status'],'ok');break
                    except OSError:
                        if p.poll() is not None:self.fail('Waitress root process failed to start')
                        time.sleep(.03)
                else:self.fail('Waitress did not listen')
                def request(path,data,headers=None):
                    q=urllib.request.Request(origin+path,data=data,headers={'Origin':origin,'Content-Type':'application/json',**(headers or {})})
                    try:
                        with urllib.request.urlopen(q,timeout=3) as r:return r.status,dict(r.headers),r.read()
                    except urllib.error.HTTPError as e:
                        try:return e.code,dict(e.headers),e.read()
                        finally:e.close()
                status,headers,body=request('/api/v1/auth/login',json.dumps({'password':secret}).encode());self.assertEqual(status,200);self.assertIn('HttpOnly',headers['Set-Cookie'])
                self.assertEqual(request('/internal/monitor/tick',b'{}')[0],401)
                self.assertEqual(request('/internal/monitor/tick',b'{}',{'Authorization':'Bearer '+secret,'Idempotency-Key':'real-wsgi-tick'})[0],200)
                connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
                try:
                    connection.request('POST','/api/v1/auth/login',headers={'Content-Length':'32769','Content-Type':'application/json'})
                    response=connection.getresponse();self.assertEqual(response.status,413);response.read()
                finally:connection.close()
                # Transport rejects oversized headers before application dispatch.
                self.assertEqual(request('/api/v1/auth/login',b'{}',{'X-Large':'x'*9000})[0],431)
            finally:p.terminate();p.wait(timeout=5)
