"""Bounded synchronous tick. Network work occurs outside database transactions."""
import json
import time
from .domain import evaluate, transition, timestamp
from .store import uid, packed


class Engine:
    def __init__(self, store, provider, clock=time.time, lease_seconds=90):
        self.store, self.provider, self.clock, self.lease_seconds = store, provider, clock, lease_seconds

    def claim(self):
        now = self.clock()
        with self.store.tx() as db:
            row = db.execute("""SELECT t.*,r.state,r.next_run,r.lease_token,r.lease_until,r.last_checked,r.health
                FROM tasks t JOIN runtime r ON t.id=r.task_id
                WHERE t.lifecycle='enabled' AND r.next_run<=? AND (r.lease_until IS NULL OR r.lease_until<=?)
                ORDER BY r.next_run LIMIT 1""", (now, now)).fetchone()
            if not row:
                return None
            task = dict(row)
            token, run_id = uid(), uid()
            spec = json.loads(db.execute('SELECT spec FROM rule_versions WHERE task_id=? AND version=?', (task['id'], task['version'])).fetchone()[0])
            if task['lease_token']:
                db.execute("UPDATE runs SET status='superseded',decision='superseded',finished_at=? WHERE task_id=? AND status='running'", (now, task['id']))
                self.store.audit(db, task['id'], now, 'lease_expired', {'previous_lease_until': task['lease_until']})
            detail = {'evaluated_at': None, 'gap': None}
            interval = spec['schedule'].get('interval_seconds', 0)
            if interval and now - task['next_run'] > interval:
                detail['gap'] = {'from': task['next_run'], 'to': now, 'missed_intervals': int((now - task['next_run']) // interval), 'historical_prices_replayed': False}
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,NULL,?,NULL,NULL,?)', (run_id, task['id'], task['version'], task['generation'], token, task['next_run'], now, 'running', packed(detail)))
            db.execute('UPDATE runtime SET lease_token=?,lease_until=? WHERE task_id=?', (token, now + self.lease_seconds, task['id']))
            return {**task, 'spec': spec, 'state': json.loads(task['state']), 'token': token, 'run_id': run_id, 'detail': detail}

    def inspect(self, spec, now):
        if spec['rule']['kind'] == 'calendar_once':
            due = timestamp(spec['rule']['scheduled_at'])
            return {'result': now >= due, 'evidence': [], 'warnings': [], 'calendar': {'scheduled_at': due, 'actual_at': now, 'late_seconds': max(0, now - due)}}
        try:
            market = self.provider.market(now)
        except Exception:
            market = {'status': 'unknown', 'reason_code': 'calendar_provider_error'}
        if market.get('status') == 'closed':
            next_open = market.get('next_open')
            if not isinstance(next_open, (int, float)) or next_open <= now or not market.get('source_ref'):
                market = {'status': 'unknown', 'reason_code': 'invalid_calendar_evidence'}
            else:
                return {'result': None, 'decision': 'skipped_closed', 'evidence': [], 'warnings': [], 'market': market}
        if market.get('status') != 'open':
            return {'result': None, 'evidence': [], 'warnings': [market.get('reason_code', 'calendar_unavailable')], 'market': market}
        try:
            observations = self.provider.quote(spec['instrument_id'], now)
        except Exception:
            observations = {'last_price': {'quality': 'error', 'reason_code': 'quote_provider_error'}}
        result = evaluate(spec['rule'], observations, spec['instrument_id'], now, self.provider.freshness_seconds)
        result['market'] = market
        return result

    def preview(self, spec):
        now = self.clock()
        with self.store.tx() as db:
            self.store.check(db, spec, now)
        outcome = self.inspect(spec, now)
        if spec['rule']['kind'] == 'price_group' and not outcome.get('evidence') and outcome.get('market', {}).get('status') == 'unknown':
            # An explicitly labelled recent snapshot is useful in preview even
            # when the calendar blocks formal evaluation. It never changes state.
            try:
                observed = evaluate(spec['rule'], self.provider.quote(spec['instrument_id'], now), spec['instrument_id'], now, self.provider.freshness_seconds)
                outcome['evidence'] = observed['evidence']
                outcome['warnings'] += observed['warnings']
            except Exception:
                outcome['warnings'].append('quote_preview_unavailable')
        return {**outcome, 'evaluated_at': now, 'preview': True, 'state_mutated': False}

    def finish(self, claim, outcome):
        now = self.clock()
        with self.store.tx() as db:
            prior = db.execute('SELECT status,decision,detail FROM runs WHERE id=?', (claim['run_id'],)).fetchone()
            if json.loads(prior['detail']).get('evaluated_at') is not None:
                return {'run_id': claim['run_id'], 'status': prior['status'], 'decision': prior['decision']}
            task = dict(db.execute('SELECT * FROM tasks WHERE id=?', (claim['id'],)).fetchone())
            runtime = dict(db.execute('SELECT * FROM runtime WHERE task_id=?', (claim['id'],)).fetchone())
            valid = task['lifecycle'] == 'enabled' and task['version'] == claim['version'] and task['generation'] == claim['generation'] and runtime['lease_token'] == claim['token'] and runtime['lease_until'] > now
            detail = {**claim['detail'], **outcome, 'evaluated_at': now}
            spec, state = claim['spec'], json.loads(runtime['state'])
            decision, status = 'superseded', 'superseded'
            next_run = now + spec['schedule'].get('interval_seconds', 300)
            notification_key = None
            if valid:
                if spec['rule']['kind'] == 'calendar_once':
                    due = timestamp(spec['rule']['scheduled_at'])
                    notification_key = f"{claim['id']}:calendar:{due}"
                    if now < due:
                        decision, status, next_run = 'skipped_not_due', 'skipped', due
                    elif now - due > 86400:
                        decision, status, next_run = 'missed', 'succeeded', None
                        state['calendar_done'] = due
                    else:
                        decision, status, next_run = 'notify', 'succeeded', None
                        state['calendar_done'] = due
                elif outcome.get('decision') == 'skipped_closed':
                    decision, status = 'skipped_closed', 'skipped'
                    next_run = outcome['market']['next_open']
                else:
                    state, decision = transition(state, outcome['result'], now, spec['notification_policy']['cooldown_seconds'])
                    status = 'failed' if outcome['result'] is None else 'succeeded'
                    notification_key = f"{claim['id']}:v{claim['version']}:episode:{state['episode']}"
                if decision == 'notify':
                    inserted = db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,?,NULL,?)', (uid(), claim['id'], claim['run_id'], notification_key, now, packed({'name': task['name'], 'version': claim['version'], 'evidence': {**outcome, 'evaluated_at': now, 'decision': 'notify'}, 'channel': 'in_app'}))).rowcount
                    if not inserted:
                        decision = 'already_notified'
                health = 'degraded' if outcome.get('warnings') else 'healthy'
                if status == 'failed':
                    health = 'failed'
                if runtime['health'] in ('failed', 'degraded') and health == 'healthy':
                    self.store.audit(db, claim['id'], now, 'recovered', {'previous_health': runtime['health']})
                db.execute('UPDATE runtime SET state=?,next_run=?,lease_token=NULL,lease_until=NULL,last_checked=?,last_success=?,health=?,decision=? WHERE task_id=?', (packed(state), next_run, now, now if status in ('succeeded', 'skipped') else runtime['last_success'], health, decision, claim['id']))
            detail.update(decision=decision, status=status)
            db.execute('UPDATE runs SET finished_at=?,status=?,result=?,decision=?,detail=? WHERE id=?', (now, status, packed(outcome['result']), decision, packed(detail), claim['run_id']))
            for evidence in outcome.get('evidence', []):
                o, observation_id = evidence.get('observation', {}), uid()
                # Evidence attaches to the claimed entity, never to an untrusted provider ID.
                db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?)', (observation_id, claim['instrument_id'], o.get('field'), o.get('value'), o.get('unit'), o.get('source_time'), o.get('fetched_at'), o.get('provider'), o.get('source_ref'), evidence['quality'], evidence.get('reason_code')))
                db.execute('INSERT INTO evidence(run_id,observation_id,detail) VALUES(?,?,?)', (claim['run_id'], observation_id, packed(evidence)))
            return {'run_id': claim['run_id'], 'status': status, 'decision': decision}

    def tick(self, request_id, batch=5, budget_seconds=45):
        start = self.clock()
        with self.store.tx() as db:
            if not db.execute('INSERT OR IGNORE INTO ticks(id,started_at) VALUES(?,?)', (request_id, start)).rowcount:
                row = dict(db.execute('SELECT * FROM ticks WHERE id=?', (request_id,)).fetchone())
                return {'duplicate': True, 'tick': row}
        runs = []
        for _ in range(min(max(batch, 1), 10)):
            if self.clock() - start >= budget_seconds:
                break
            claim = self.claim()
            if not claim:
                break
            outcome = self.inspect(claim['spec'], self.clock())
            runs.append(self.finish(claim, outcome))
        with self.store.tx() as db:
            db.execute('UPDATE ticks SET finished_at=?,outcome=? WHERE id=?', (self.clock(), packed(runs), request_id))
        return {'duplicate': False, 'runs': runs}
