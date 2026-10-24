"""Production transport adapter. Business dispatch stays in Application.

Waitress bounds HTTP buffering/connections. A deployment TLS proxy must additionally
bound header/body receive time, connection rates, and isolate the origin listener.
"""
import json
import mimetypes
import threading
import time
from collections import deque
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .domain import Problem
from .server import ROOT
from .store import packed, uid

MAX_BODY = 32768
SECURITY_HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",
}


class WebApplication:
    def __init__(self, application, static_root=None, clock=time.monotonic):
        self.application = application
        self.static_root = Path(static_root or ROOT / 'dist').resolve()
        self.clock = clock
        self.login_attempts = deque()
        self.login_lock = threading.Lock()
        self.tick_slots = threading.BoundedSemaphore(1)
        self.model_slots = threading.BoundedSemaphore(2)

    def login_limit(self):
        # Single demo account: global bound cannot be bypassed with forged XFF.
        now = self.clock()
        with self.login_lock:
            while self.login_attempts and self.login_attempts[0] <= now - 60:
                self.login_attempts.popleft()
            if len(self.login_attempts) >= 10:
                raise Problem('login_rate_limited', '登录尝试过于频繁，请稍后重试。', 429)
            self.login_attempts.append(now)

    def route(self, environ):
        method = environ.get('REQUEST_METHOD', 'GET')
        if method not in ('GET', 'HEAD', 'POST', 'PATCH', 'DELETE'):
            raise Problem('method_not_allowed', '不支持的 HTTP 方法。', 405)
        headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                headers[key[5:].replace('_', '-')] = value
        # Never derive auth, cookies, redirects or owner from forwarded headers.
        expected_host = urlsplit(self.application.origin).netloc
        if headers.get('Host', '').lower() != expected_host.lower():
            raise Problem('host_rejected', '访问地址不匹配。', 400)
        path = environ.get('PATH_INFO', '/')
        if '\x00' in path or '\\' in path:
            raise Problem('invalid_path', '请求路径无效。')
        if not path.startswith(('/api/', '/internal/')):
            if method not in ('GET', 'HEAD'):
                raise Problem('method_not_allowed', '不支持的 HTTP 方法。', 405)
            candidate = (self.static_root / path.lstrip('/')).resolve()
            if not candidate.is_relative_to(self.static_root) or any(part.startswith('.') for part in Path(path).parts if part not in ('/', '.')):
                raise Problem('not_found', '页面不存在。', 404)
            if not candidate.is_file():
                if Path(path).suffix:
                    raise Problem('not_found', '文件不存在。', 404)
                candidate = self.static_root / 'index.html'
            if not candidate.is_file():
                raise Problem('frontend_not_built', '前端尚未构建。', 503)
            return 200, candidate.read_bytes(), {}, mimetypes.guess_type(candidate)[0] or 'application/octet-stream'
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
        except ValueError:
            raise Problem('invalid_content_length', '请求长度无效。')
        if length < 0 or length > MAX_BODY:
            raise Problem('payload_too_large', '请求体超过 32 KiB 限制。', 413)
        if length and environ.get('CONTENT_TYPE', '').split(';', 1)[0].strip().lower() != 'application/json':
            raise Problem('unsupported_media_type', '请求体须使用 application/json。', 415)
        raw = environ['wsgi.input'].read(length) if length else b''
        try:
            if len(raw) != length:
                raise ValueError()
            body = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError())) if raw else {}
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise Problem('invalid_json', '请求体必须为有效的 JSON 对象。')
        slot = None
        if path == '/api/v1/auth/login' and method == 'POST':
            self.login_limit()
        if path == '/internal/monitor/tick' and method == 'POST':
            slot = self.tick_slots
        elif path == '/api/v1/rules/parse' and method == 'POST':
            slot = self.model_slots
        if slot is not None and not slot.acquire(blocking=False):
            raise Problem('service_busy', '执行容量已满，请稍后重试。', 503)
        try:
            try:
                query = parse_qs(environ.get('QUERY_STRING', ''), max_num_fields=30)
            except ValueError:
                raise Problem('too_many_query_fields', '查询参数过多。')
            status, data, response_headers = self.application.dispatch('GET' if method == 'HEAD' else method, path, query, body, headers)
            return status, data, response_headers, 'application/json; charset=utf-8'
        finally:
            if slot is not None:
                slot.release()

    def __call__(self, environ, start_response):
        request_id = uid()
        headers = {}
        content_type = 'application/json; charset=utf-8'
        try:
            status, data, headers, content_type = self.route(environ)
        except Problem as error:
            status = error.status
            data = {'code': error.code, 'message': error.message, 'field_errors': error.fields, 'request_id': request_id}
            if status in (429, 503):
                headers['Retry-After'] = '60' if status == 429 else '5'
        except Exception:
            status, data = 500, {'code': 'internal_error', 'message': '服务内部错误，请使用请求编号联系维护者。', 'request_id': request_id}
        encoded = data if isinstance(data, bytes) else packed(data).encode()
        response_headers = {**SECURITY_HEADERS, 'Content-Type': content_type, 'Content-Length': str(len(encoded)), 'X-Request-ID': request_id, **headers}
        if self.application.secure:
            response_headers['Strict-Transport-Security'] = 'max-age=31536000'
        start_response(f'{status} {HTTPStatus(status).phrase}', list(response_headers.items()))
        return [] if environ.get('REQUEST_METHOD') == 'HEAD' else [encoded]
