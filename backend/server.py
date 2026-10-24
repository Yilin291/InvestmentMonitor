"""Same-origin HTTP application; credentials remain on server, sessions in signed cookies."""
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .domain import Problem
from .engine import Engine
from .providers import FuyaoProvider, Parser
from .store import Store, uid, packed

ROOT = Path(__file__).resolve().parent.parent


class Application:
    def __init__(self, store, provider=None, password=None, session_secret=None, tick_secret=None, origin=None):
        self.store = store
        self.provider = provider or FuyaoProvider(store)
        self.engine = Engine(store, self.provider)
        self.parser = Parser(store)
        self.password = password or os.environ.get('DEMO_PASSWORD', '')
        self.secret = session_secret or os.environ.get('SESSION_SECRET', '')
        self.tick_secret = tick_secret or os.environ.get('TICK_SECRET', '')
        self.origin = origin or os.environ.get('APP_ORIGIN', 'http://127.0.0.1:8080')
        if min(len(self.password), len(self.secret), len(self.tick_secret)) < 24:
            raise RuntimeError('DEMO_PASSWORD, SESSION_SECRET, TICK_SECRET must each contain at least 24 characters')
        self.secure = self.origin.startswith('https://')
        self.cookie_suffix = '; HttpOnly; SameSite=Strict; Path=/' + ('; Secure' if self.secure else '')

    def session(self):
        body = base64.urlsafe_b64encode(packed({'owner': 'demo', 'expires': time.time() + 43200}).encode()).decode()
        return body + '.' + hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    def owner(self, cookie):
        try:
            token = next(x.strip().split('=', 1)[1] for x in cookie.split(';') if x.strip().startswith('monitor_session='))
            body, signature = token.split('.')
            if not hmac.compare_digest(signature, hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).hexdigest()):
                raise ValueError()
            session = json.loads(base64.urlsafe_b64decode(body))
            if session['expires'] <= time.time() or session['owner'] != 'demo':
                raise ValueError()
            return session['owner']
        except (StopIteration, ValueError, KeyError, TypeError):
            raise Problem('unauthorized', '请登录演示账户。', 401)

    def dispatch(self, method, path, query, body, headers):
        now = time.time()
        if path == '/api/health' and method == 'GET':
            return 200, {'status': 'ok', 'storage': getattr(self.store, 'backend', 'sqlite'), 'production_validated': False}, {}
        if path == '/internal/monitor/tick' and method == 'POST':
            auth = headers.get('Authorization', '')
            if not hmac.compare_digest(auth, 'Bearer ' + self.tick_secret):
                raise Problem('unauthorized', '调度身份校验失败。', 401)
            key = headers.get('Idempotency-Key', '')
            if not re.fullmatch('[A-Za-z0-9:_-]{8,128}', key):
                raise Problem('invalid_idempotency_key', '调度请求需 8–128 字符 Idempotency-Key。')
            batch = body.get('batch', 5)
            if type(batch) is not int or not 1 <= batch <= 10:
                raise Problem('invalid_batch', '单次批次为 1–10。')
            return 200, self.engine.tick(key, batch), {}
        if method not in ('GET', 'HEAD') and headers.get('Origin') != self.origin:
            raise Problem('origin_rejected', '请求来源不匹配。', 403)
        if path == '/api/v1/auth/login' and method == 'POST':
            password = body.get('password', '')
            if not isinstance(password, str) or not hmac.compare_digest(password.encode(), self.password.encode()):
                raise Problem('invalid_credentials', '登录凭证错误。', 401)
            return 200, {'owner': 'demo'}, {'Set-Cookie': 'monitor_session=' + self.session() + '; Max-Age=43200' + self.cookie_suffix}
        owner = self.owner(headers.get('Cookie', ''))
        if path == '/api/v1/auth/logout' and method == 'POST':
            return 200, {'logged_out': True}, {'Set-Cookie': 'monitor_session=; Max-Age=0' + self.cookie_suffix}
        if path == '/api/v1/auth/me' and method == 'GET':
            return 200, {'owner': owner}, {}
        if path == '/api/v1/capabilities' and method == 'GET':
            return 200, {'rule_kinds': ['price_group', 'calendar_once'], 'fields': ['last_price'], 'operators': ['lt', 'gt'], 'max_conditions': 4, 'max_tasks': 10, 'interval_seconds_min': 300, 'frequency_verified': False, 'market_data': self.provider.availability(), 'natural_language': bool(self.parser.key), 'disabled': ['announcement', 'heat', 'trading', 'external_notifications'], 'deployment': 'local_sqlite_not_cloud_validated'}, {}
        if path == '/api/v1/instruments' and method == 'GET':
            q = query.get('q', [''])[0][:100]
            return 200, self.store.query('SELECT * FROM instruments WHERE instr(name,?)>0 OR instr(code,?)>0 ORDER BY code LIMIT 30', (q, q)), {}
        if path == '/api/v1/rules/parse' and method == 'POST':
            return 200, self.parser.parse(body.get('text'), now), {}
        if path == '/api/v1/rules/preview' and method == 'POST':
            return 200, self.engine.preview(body), {}
        if path == '/api/v1/tasks':
            if method == 'GET':
                return 200, self.store.listing(owner, now), {}
            if method == 'POST':
                return 201, self.store.create(owner, body, now), {}
        match = re.fullmatch('/api/v1/tasks/([a-f0-9]{32})(?:/(activate|pause|resume|runs|versions|audit))?', path)
        if match:
            task_id, action = match.groups()
            if method == 'GET':
                if action is None:
                    return 200, self.store.get(owner, task_id, now), {}
                try:
                    limit, offset = int(query.get('limit', ['50'])[0]), int(query.get('offset', ['0'])[0])
                except ValueError:
                    raise Problem('invalid_pagination', '分页参数须为整数。')
                return 200, self.store.history(owner, task_id, action, limit, offset), {}
            if method == 'PATCH' and action is None:
                return 200, self.store.edit(owner, task_id, body.get('spec'), body.get('expected_version'), now), {}
            if method == 'DELETE' and action is None:
                return 200, self.store.lifecycle(owner, task_id, 'delete', None, now), {}
            if method == 'POST' and action in ('activate', 'pause', 'resume'):
                return 200, self.store.lifecycle(owner, task_id, action, body.get('expected_version'), now), {}
        if path == '/api/v1/notifications' and method == 'GET':
            return 200, self.store.notifications(owner), {}
        match = re.fullmatch('/api/v1/notifications/([a-f0-9]{32})/read', path)
        if match and method == 'POST':
            return 200, self.store.mark_read(owner, match[1], now), {}
        raise Problem('not_found', '接口不存在。', 404)


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No URLs, bodies, cookies, headers or provider secrets in access logs.

        def respond(self, status, data, headers=None, content_type='application/json; charset=utf-8'):
            encoded = data if isinstance(data, bytes) else packed(data).encode()
            self.send_response(status)
            for k, v in {'Content-Type': content_type, 'Content-Length': str(len(encoded)), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'", **(headers or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(encoded)

        def handle_request(self):
            request_id = uid()
            try:
                url = urlsplit(self.path)
                if not url.path.startswith(('/api/', '/internal/')) and self.command == 'GET':
                    root = (ROOT / 'dist').resolve()
                    path = (root / url.path.lstrip('/')).resolve()
                    if not path.is_relative_to(root):
                        raise Problem('not_found', '页面不存在。', 404)
                    if not path.is_file():
                        path = root / 'index.html'
                    if not path.is_file():
                        raise Problem('frontend_not_built', '请先构建 frontend。', 503)
                    return self.respond(200, path.read_bytes(), content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 <= size <= 32768:
                        raise Problem('payload_too_large', '请求体超过限制。', 413)
                    self.connection.settimeout(10)
                    body = json.loads(self.rfile.read(size)) if size else {}
                    if not isinstance(body, dict):
                        raise ValueError()
                except (ValueError, TimeoutError):
                    raise Problem('invalid_json', '请求体必须为 JSON 对象。')
                status, data, headers = app.dispatch(self.command, url.path, parse_qs(url.query), body, self.headers)
                self.respond(status, data, {**headers, 'X-Request-ID': request_id})
            except Problem as e:
                self.respond(e.status, {'code': e.code, 'message': e.message, 'field_errors': e.fields, 'request_id': request_id})
            except Exception:
                self.respond(500, {'code': 'internal_error', 'message': '服务内部错误，请使用请求编号联系维护者。', 'request_id': request_id})

        do_GET = do_POST = do_PATCH = do_DELETE = handle_request
    return Handler


def main():
    os.umask(0o077)
    if os.environ.get('APP_ENV', 'development') != 'development':
        raise RuntimeError('Production blocked: durable storage and runtime handoff L-01/L-02 not validated; SQLite on an unverified filesystem cannot be deployed')
    store = Store(os.environ.get('PRODUCT_DB_PATH', str(ROOT / '.product-data' / 'monitor.sqlite')))
    app = Application(store)
    port = int(os.environ.get('PRODUCT_PORT', '8080'))
    server = ThreadingHTTPServer((os.environ.get('PRODUCT_HOST', '127.0.0.1'), port), handler(app))
    print(packed({'event': 'listening', 'port': port, 'storage': 'sqlite', 'market_data': app.provider.availability()}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
