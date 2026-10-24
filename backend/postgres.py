"""PostgreSQL adapter for the authorized Meoo project; SQLite stays local-only.

All mutations take one transaction-scoped advisory lock. This deliberately
serializes short commits for the small MVP while network work remains outside.
"""
import os
import re
from contextlib import contextmanager
from pathlib import Path
from .domain import Problem
from .store import Store

LOCK_ID = 724102401

class Record(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def record_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Record(zip(names, values))


def postgres_sql(sql):
    """Translate only the fixed SQL used by Store/Engine, never user SQL."""
    sql = sql.replace('?', '%s')
    sql = re.sub(r'\binstr\(', 'strpos(', sql, flags=re.I)
    if re.match(r'\s*INSERT OR IGNORE INTO ', sql, re.I):
        sql = re.sub(r'INSERT OR IGNORE INTO ', 'INSERT INTO ', sql, count=1, flags=re.I)
        sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    return sql


class Connection:
    def __init__(self, connection): self.connection = connection
    def execute(self, sql, parameters=()): return self.connection.execute(postgres_sql(sql), parameters)
    def close(self): self.connection.close()


class PostgresStore(Store):
    backend = 'postgresql'
    def __init__(self, dsn, migrate=False):
        if not dsn:
            raise RuntimeError('SUPABASE_DB_URL or DATABASE_URL is required')
        self._dsn = dsn
        if migrate:
            self.migrate()
        else:
            db = self.connect()
            try:
                row = db.execute('SELECT version FROM schema_version ORDER BY version DESC LIMIT 1').fetchone()
                if not row or row['version'] != 1:
                    raise RuntimeError('product_schema_migration_required')
            finally: db.close()

    def connect(self):
        import psycopg
        # No guessed TLS downgrade: honor server-provided DSN policy. Require
        # encrypted transport by default; production evidence must report ssl.
        sslmode = os.environ.get('PRODUCT_DB_SSLMODE', 'require')
        if sslmode not in ('require', 'verify-ca', 'verify-full'):
            raise RuntimeError('encrypted PostgreSQL transport required')
        db = psycopg.connect(self._dsn, autocommit=True, row_factory=record_factory,
            connect_timeout=8, sslmode=sslmode,
            options='-c search_path=watchlist -c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=15000')
        return Connection(db)

    @contextmanager
    def tx(self):
        db = self.connect()
        try:
            with db.connection.transaction():
                db.execute('SELECT pg_advisory_xact_lock(?)', (LOCK_ID,))
                yield db
        finally: db.close()

    def migrate(self):
        db = self.connect()
        try:
            with db.connection.transaction():
                db.execute('SELECT pg_advisory_xact_lock(?)', (LOCK_ID,))
                # Fixed trusted migration, no values interpolated from requests.
                db.connection.execute(Path(__file__).with_name('schema_postgres.sql').read_text(), prepare=False)
        finally: db.close()

    def backup(self, destination):
        raise Problem('postgres_backup_external', 'PostgreSQL 请使用平台备份或 pg_dump，并执行独立恢复验证；不使用 SQLite 文件备份。', 409)


def from_environment(env=None, migrate=False):
    env = os.environ if env is None else env
    dsn = env.get('SUPABASE_DB_URL') or env.get('DATABASE_URL')
    if dsn:
        return PostgresStore(dsn, migrate=migrate)
    if env.get('APP_ENV') == 'production':
        raise RuntimeError('production PostgreSQL connection is missing; no SQLite fallback')
    return Store(env.get('PRODUCT_DB_PATH', '.product-data/monitor.sqlite'))


def main():
    try:
        store = from_environment(migrate=True)
        if not isinstance(store, PostgresStore):
            raise RuntimeError('PostgreSQL connection required for migration')
        info = store.query("SELECT current_database() IS NOT NULL AS connected, EXISTS(SELECT 1 FROM pg_stat_ssl WHERE pid=pg_backend_pid() AND ssl) AS encrypted")
        print(__import__('json').dumps({'status':'migrated','schema':'watchlist','connection':info}))
    except Exception:
        # Driver messages may include connection identities; never echo them.
        print('{"status":"failed","reason":"postgres_migration_or_connection_failed"}')
        raise SystemExit(2)

if __name__ == '__main__': main()
