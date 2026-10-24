"""Real Store transaction probe. No migration, no market fixtures, no credentials output."""
import json
import uuid
from datetime import datetime, timezone


def failure(exc):
    # Classify internally; never return raw driver text (may contain DSN identities).
    message = str(exc).lower()
    reason = 'database_connection_or_schema_failed'
    for needle, code in [('missing "="', 'database_connection_string_invalid'),
                         ('production app_origin', 'production_https_origin_missing_or_invalid'),
                         ('production_storage_not_ready', 'production_database_configuration_missing'),
                         ('product_schema_migration_required', 'database_schema_version_missing'),
                         ('must each contain', 'business_secret_missing_or_short'),
                         ('could not translate host', 'database_dns_failed'),
                         ('name or service not known', 'database_dns_failed'),
                         ('timeout', 'database_connection_timeout'),
                         ('does not support ssl', 'database_tls_unsupported'),
                         ('certificate verify failed', 'database_certificate_failed'),
                         ('password authentication failed', 'database_authentication_failed'),
                         ('permission denied', 'database_permission_denied'),
                         ('does not exist', 'database_schema_or_object_missing'),
                         ('connection refused', 'database_connection_refused')]:
        if needle in message:
            reason = code
            break
    return {'reason': reason, 'exception_type': type(exc).__name__,
            'sqlstate': getattr(exc, 'sqlstate', None)}


def probe(store):
    import psycopg
    if store.backend != 'postgresql':
        raise RuntimeError('runtime probe requires PostgreSQL')
    identifier = 'runtime-probe-' + uuid.uuid4().hex
    rolled_back = identifier + '-rollback'
    tls = store.query('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')[0]['ssl']
    if not tls:
        raise RuntimeError('encrypted PostgreSQL transport required')
    try:
        with store.tx() as db:
            db.execute('INSERT INTO ticks(id,started_at,outcome) VALUES(?,?,?)',
                       (identifier, datetime.now(timezone.utc).timestamp(), 'runtime connectivity probe'))
        committed = store.query('SELECT id FROM ticks WHERE id=?', (identifier,))[0]['id'] == identifier
        try:
            with store.tx() as db:
                db.execute('INSERT INTO ticks(id,started_at) VALUES(?,?)', (rolled_back, 0))
                raise ValueError('intentional probe rollback')
        except ValueError:
            pass
        rollback = not store.query('SELECT id FROM ticks WHERE id=?', (rolled_back,))
        duplicate = False
        try:
            with store.tx() as db:
                db.execute('INSERT INTO ticks(id,started_at) VALUES(?,?)', (identifier, 0))
        except psycopg.errors.UniqueViolation:
            duplicate = True
        recovered = bool(store.query('SELECT id FROM ticks WHERE id=?', (identifier,)))
        if not all((committed, rollback, duplicate, recovered)):
            raise RuntimeError('runtime probe assertion failed')
        return {'event': 'postgres_runtime_probe', 'status': 'passed', 'tls': tls,
                'commit_readback': committed, 'rollback': rollback,
                'unique_violation_handled': duplicate, 'connection_after_error': recovered,
                'probe_id': identifier, 'at': datetime.now(timezone.utc).isoformat()}
    finally:
        with store.tx() as db:
            db.execute('DELETE FROM ticks WHERE id IN (?,?)', (identifier, rolled_back))


def main():
    from .postgres import from_environment
    try:
        result = probe(from_environment())
    except Exception as exc:
        print(json.dumps({'event': 'postgres_runtime_probe', 'status': 'failed', **failure(exc)}))
        raise SystemExit(2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
