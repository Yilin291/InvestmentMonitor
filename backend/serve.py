"""Waitress entry for root scripts/start.sh; dev http.server is never imported as a runner."""
import os
from urllib.parse import urlsplit
from .server import Application, ROOT
from .store import packed
from .postgres import from_environment
from .wsgi import WebApplication, MAX_BODY


def server_options(env):
    host = env.get('PRODUCT_HOST', '127.0.0.1')
    port = int(env.get('PORT', env.get('PRODUCT_PORT', '8080')))
    if not 1 <= port <= 65535:
        raise RuntimeError('invalid listen port')
    return dict(host=host, port=port, threads=8, connection_limit=64, backlog=64,
                channel_timeout=15, cleanup_interval=1, max_request_header_size=8192,
                max_request_body_size=MAX_BODY, expose_tracebacks=False,
                clear_untrusted_proxy_headers=True, log_untrusted_proxy_headers=False,
                log_socket_errors=False, ident='watchlist', channel_request_lookahead=0)


def preflight(env):
    mode = env.get('APP_ENV', 'development')
    if mode not in ('development', 'production'):
        raise RuntimeError('APP_ENV must be development or production')
    if mode == 'production':
        origin = urlsplit(env.get('APP_ORIGIN', ''))
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.path or origin.query or origin.fragment:
            raise RuntimeError('production APP_ORIGIN must be an HTTPS origin without path or credentials')
        if not (env.get('SUPABASE_DB_URL') or env.get('DATABASE_URL')):
            raise RuntimeError('production_storage_not_ready: PostgreSQL connection missing; no ephemeral SQLite fallback')


def main():
    os.umask(0o077)
    stage = 'preflight'
    try:
        preflight(os.environ)
        stage = 'listener_configuration'
        options = server_options(os.environ)
        stage = 'database_connect_and_schema'
        store = from_environment()
        if os.environ.get('PRODUCT_RUNTIME_PROBE') == '1':
            stage = 'database_transaction_probe'
            from .runtime_probe import probe
            print(packed(probe(store)), flush=True)
        stage = 'application_configuration'
        app = Application(store)
        web = WebApplication(app)
    except Exception as exc:
        from .runtime_probe import failure
        present = {key: bool(os.environ.get(key)) for key in
                   ('APP_ORIGIN', 'SUPABASE_DB_URL', 'DATABASE_URL', 'DEMO_PASSWORD',
                    'SESSION_SECRET', 'TICK_SECRET', 'PRODUCT_RUNTIME_PROBE')}
        print(packed({'event': 'startup_blocked', 'stage': stage, 'configuration_present': present,
                      **failure(exc), 'guide': 'deploy/HTTP_DEPLOYMENT.md'}), flush=True)
        raise SystemExit(2)
    from waitress import serve
    print(packed({'event': 'listening', 'transport': 'waitress', 'host': options['host'], 'port': options['port'], 'storage': store.backend, 'production_validated': False}), flush=True)
    serve(web, **options)

if __name__ == '__main__':
    main()
