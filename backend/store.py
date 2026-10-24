import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from .domain import Problem, validate_spec, timestamp


def uid():
    return uuid.uuid4().hex


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


class Store:
    backend = 'sqlite'
    """One connection per transaction, enabling separate HTTP threads/processes."""
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        db = self.connect()
        try:
            # Older SQLite WAL versions have a documented reset race.
            # Retain SQLite safely with rollback journal until a patched runtime is used.
            v = sqlite3.sqlite_version_info
            patched = v >= (3, 51, 3) or (3, 50, 7) <= v < (3, 51, 0) or (3, 44, 6) <= v < (3, 45, 0)
            db.execute('PRAGMA journal_mode=' + ('WAL' if patched else 'DELETE'))
            db.executescript(Path(__file__).with_name('schema.sql').read_text())
        finally:
            db.close()

    def backup(self, destination):
        """Consistent online backup; never overwrite an existing artifact."""
        import os
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        source, backup = self.connect(), sqlite3.connect(target)
        try:
            source.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise Problem('backup_integrity_failed', '备份完整性检查失败。', 500)
        finally:
            source.close()
            backup.close()
        return {'integrity_check': 'ok'}

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA busy_timeout=10000')
        return db

    @contextmanager
    def tx(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def query(self, sql, args=()):
        db = self.connect()
        try:
            return [dict(r) for r in db.execute(sql, args)]
        finally:
            db.close()

    def owned(self, db, owner, task_id):
        row = db.execute('SELECT * FROM tasks WHERE id=? AND owner=? AND lifecycle!=?', (task_id, owner, 'deleted')).fetchone()
        if not row:
            raise Problem('not_found', '任务不存在。', 404)
        return dict(row)

    def check(self, db, spec, now, future=True):
        return validate_spec(spec, now, lambda key: db.execute('SELECT 1 FROM instruments WHERE id=?', (key,)).fetchone() is not None, future)

    def audit(self, db, task_id, now, action, detail):
        db.execute('INSERT INTO audit(task_id,at,action,detail) VALUES(?,?,?,?)', (task_id, now, action, packed(detail)))

    def create(self, owner, spec, now):
        with self.tx() as db:
            self.check(db, spec, now)
            if db.execute("SELECT count(*) FROM tasks WHERE owner=? AND lifecycle!='deleted'", (owner,)).fetchone()[0] >= 10:
                raise Problem('task_limit', '每账户最多 10 个未删除任务。', 409)
            task_id = uid()
            db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,0,?,?,?)', (task_id, owner, spec['name'], spec['instrument_id'], 1, 'draft', now, now))
            self.version(db, task_id, 1, spec, now, '创建草稿')
            db.execute('INSERT INTO runtime(task_id,state) VALUES(?,?)', (task_id, packed({'last_result': None, 'episode': 0, 'episode_notified': False, 'cooldown_until': 0})))
            self.audit(db, task_id, now, 'created', {})
        return self.get(owner, task_id, now)

    def version(self, db, task_id, version, spec, now, summary):
        db.execute('INSERT INTO rule_versions VALUES(?,?,?,?,?)', (task_id, version, packed(spec), now, summary))
        if spec['rule']['kind'] == 'calendar_once':
            db.execute('INSERT INTO calendar_entries VALUES(?,?,?)', (task_id, version, timestamp(spec['rule']['scheduled_at'])))

    def edit(self, owner, task_id, spec, expected, now):
        with self.tx() as db:
            task = self.owned(db, owner, task_id)
            self.expected(task, expected)
            self.check(db, spec, now)
            state = json.loads(db.execute('SELECT state FROM runtime WHERE task_id=?', (task_id,)).fetchone()[0])
            state.update(last_result=None, episode_notified=False)
            version = task['version'] + 1
            self.version(db, task_id, version, spec, now, '规则已修改；重置事件段，保留任务冷却。')
            db.execute('UPDATE tasks SET name=?,instrument_id=?,version=?,generation=generation+1,updated_at=? WHERE id=?', (spec['name'], spec['instrument_id'], version, now, task_id))
            due = self.initial_due(spec, now) if task['lifecycle'] == 'enabled' else None
            db.execute("UPDATE runtime SET state=?,next_run=?,lease_token=NULL,lease_until=NULL,health='pending',decision=NULL WHERE task_id=?", (packed(state), due, task_id))
            self.audit(db, task_id, now, 'edited', {'from': task['version'], 'to': version})
        return self.get(owner, task_id, now)

    @staticmethod
    def expected(task, expected):
        if type(expected) is not int or task['version'] != expected:
            raise Problem('version_conflict', '任务已变更，请刷新后重试。', 409)

    @staticmethod
    def initial_due(spec, now):
        return timestamp(spec['rule']['scheduled_at']) if spec['rule']['kind'] == 'calendar_once' else now

    def lifecycle(self, owner, task_id, action, expected, now):
        with self.tx() as db:
            task = self.owned(db, owner, task_id)
            if action in ('activate', 'resume'):
                self.expected(task, expected)
            spec = json.loads(db.execute('SELECT spec FROM rule_versions WHERE task_id=? AND version=?', (task_id, task['version'])).fetchone()[0])
            runtime = dict(db.execute('SELECT * FROM runtime WHERE task_id=?', (task_id,)).fetchone())
            if action == 'activate':
                if task['lifecycle'] != 'draft':
                    raise Problem('invalid_lifecycle', '只有草稿可启用。', 409)
                self.check(db, spec, now)
                status = 'enabled'
            elif action == 'resume':
                if task['lifecycle'] != 'paused':
                    raise Problem('invalid_lifecycle', '只有暂停任务可恢复。', 409)
                status = 'enabled'
            elif action == 'pause':
                if task['lifecycle'] not in ('enabled', 'paused'):
                    raise Problem('invalid_lifecycle', '只有启用任务可暂停。', 409)
                status = 'paused'
            elif action == 'delete':
                status = 'deleted'
            else:
                raise Problem('invalid_action', '不支持的操作。')
            due = self.initial_due(spec, now) if status == 'enabled' else None
            state = json.loads(runtime['state'])
            # Keep an already delivered/missed calendar occurrence terminal across pause/resume.
            if spec['rule']['kind'] == 'calendar_once' and state.get('calendar_done') == timestamp(spec['rule']['scheduled_at']):
                due = None
            db.execute('UPDATE tasks SET lifecycle=?,generation=generation+1,updated_at=? WHERE id=?', (status, now, task_id))
            db.execute('UPDATE runtime SET next_run=?,lease_token=NULL,lease_until=NULL,pause_at=? WHERE task_id=?', (due, now if status == 'paused' else None, task_id))
            self.audit(db, task_id, now, action, {'gap_from': runtime['pause_at'] if action == 'resume' else None, 'gap_to': now if action == 'resume' else None, 'historical_prices_replayed': False})
        return {'id': task_id, 'lifecycle': status}

    def get(self, owner, task_id, now):
        db = self.connect()
        try:
            task = self.owned(db, owner, task_id)
            runtime = dict(db.execute('SELECT * FROM runtime WHERE task_id=?', (task_id,)).fetchone())
            runtime['state'] = json.loads(runtime['state'])
            runtime.pop('lease_token', None)
            spec = json.loads(db.execute('SELECT spec FROM rule_versions WHERE task_id=? AND version=?', (task_id, task['version'])).fetchone()[0])
            interval = spec['schedule'].get('interval_seconds', 60)
            runtime['overdue'] = task['lifecycle'] == 'enabled' and runtime['next_run'] is not None and now > runtime['next_run'] + max(interval, 60)
            if runtime['overdue']:
                runtime['health'] = 'degraded'
            instrument = db.execute('SELECT * FROM instruments WHERE id=?', (task['instrument_id'],)).fetchone()
            unread = db.execute('SELECT count(*) FROM notifications WHERE task_id=? AND read_at IS NULL', (task_id,)).fetchone()[0]
            return {**task, 'spec': spec, 'runtime': runtime, 'instrument': dict(instrument) if instrument else None, 'unread': unread}
        finally:
            db.close()

    def listing(self, owner, now):
        ids = self.query("SELECT id FROM tasks WHERE owner=? AND lifecycle!='deleted' ORDER BY created_at DESC", (owner,))
        return [self.get(owner, r['id'], now) for r in ids]

    def history(self, owner, task_id, kind, limit=50, offset=0):
        with self.tx() as db:
            self.owned(db, owner, task_id)
        sqls = {'runs': 'SELECT * FROM runs WHERE task_id=? ORDER BY started_at DESC LIMIT ? OFFSET ?',
                'versions': 'SELECT * FROM rule_versions WHERE task_id=? ORDER BY version DESC LIMIT ? OFFSET ?',
                'audit': 'SELECT * FROM audit WHERE task_id=? ORDER BY at DESC LIMIT ? OFFSET ?'}
        if kind not in sqls:
            raise Problem('not_found', '路径不存在。', 404)
        rows = self.query(sqls[kind], (task_id, min(max(limit, 1), 100), max(offset, 0)))
        for row in rows:
            for key in ('spec', 'detail', 'result'):
                if key in row and row[key] is not None:
                    row[key] = json.loads(row[key])
            row.pop('lease_token', None)
            if kind == 'runs':
                row['evidence'] = [json.loads(e['detail']) for e in self.query('SELECT detail FROM evidence WHERE run_id=?', (row['id'],))]
        return rows

    def notifications(self, owner):
        rows = self.query('SELECT n.* FROM notifications n JOIN tasks t ON n.task_id=t.id WHERE t.owner=? ORDER BY n.created_at DESC LIMIT 100', (owner,))
        for row in rows:
            row['detail'] = json.loads(row['detail'])
        return rows

    def mark_read(self, owner, notification_id, now):
        with self.tx() as db:
            row = db.execute('SELECT n.id FROM notifications n JOIN tasks t ON n.task_id=t.id WHERE n.id=? AND t.owner=?', (notification_id, owner)).fetchone()
            if not row:
                raise Problem('not_found', '提醒不存在。', 404)
            db.execute('UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=?', (now, notification_id))
        return {'id': notification_id, 'read': True}
