"""Deterministic rule contract. No provider or model is trusted to validate itself."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

class Problem(Exception):
    def __init__(self, code, message, status=400, fields=None):
        super().__init__(message)
        self.code, self.message, self.status, self.fields = code, message, status, fields


def timestamp(value):
    try:
        if not isinstance(value, str):
            raise ValueError()
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None:
            raise ValueError()
        return d.timestamp()
    except (ValueError, TypeError, OverflowError):
        raise Problem('invalid_time', '时间必须包含明确时区。')


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def exact_keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise Problem('invalid_structure', '字段缺失或包含未支持字段。')


def positive_decimal(value):
    try:
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError()
        d = Decimal(value)
        if not d.is_finite() or d <= 0 or d > Decimal('1000000000000'):
            raise ValueError()
        return d
    except (InvalidOperation, ValueError):
        raise Problem('invalid_price', '价格须为正数十进制字符串，且不超过 1 万亿元。')


def validate_spec(spec, now, instrument_exists, future=True):
    exact_keys(spec, ['name', 'instrument_id', 'rule', 'schedule', 'notification_policy'])
    if not isinstance(spec['name'], str) or not 1 <= len(spec['name'].strip()) <= 100:
        raise Problem('invalid_name', '任务名称须为 1–100 个字符。')
    rule, schedule, policy = spec['rule'], spec['schedule'], spec['notification_policy']
    exact_keys(policy, ['mode', 'cooldown_seconds'])
    if policy['mode'] != 'on_episode' or type(policy['cooldown_seconds']) is not int or not 0 <= policy['cooldown_seconds'] <= 31536000:
        raise Problem('invalid_policy', '冷却须为 0–31536000 秒；首次满足提醒、同事件段仅一次。')
    if not isinstance(rule, dict):
        raise Problem('invalid_rule', '规则格式错误。')
    if rule.get('kind') == 'price_group':
        exact_keys(rule, ['kind', 'combinator', 'conditions'])
        if not isinstance(spec['instrument_id'], str) or not instrument_exists(spec['instrument_id']):
            raise Problem('instrument_unverified', '请选择经过核验的 A 股标的。')
        if rule['combinator'] not in ('all', 'any') or not isinstance(rule['conditions'], list) or not 1 <= len(rule['conditions']) <= 4:
            raise Problem('invalid_group', '仅支持 1–4 个价格条件的单层 AND/OR。')
        ids = set()
        for c in rule['conditions']:
            exact_keys(c, ['id', 'field', 'operator', 'value', 'currency'])
            if not isinstance(c['id'], str) or not 1 <= len(c['id']) <= 40 or c['id'] in ids or c['field'] != 'last_price' or c['operator'] not in ('gt', 'lt') or c['currency'] != 'CNY':
                raise Problem('invalid_condition', '仅支持人民币最新价、严格高于/低于，条件 ID 不得重复。')
            positive_decimal(c['value'])
            ids.add(c['id'])
        exact_keys(schedule, ['mode', 'timezone', 'interval_seconds'])
        if schedule['mode'] != 'market_interval' or schedule['timezone'] != 'Asia/Shanghai' or type(schedule['interval_seconds']) is not int or not 300 <= schedule['interval_seconds'] <= 86400:
            raise Problem('invalid_schedule', '检查间隔须为 300–86400 秒，时区 Asia/Shanghai；上线频率仍待验证。')
    elif rule.get('kind') == 'calendar_once':
        exact_keys(rule, ['kind', 'scheduled_at'])
        if spec['instrument_id'] is not None:
            raise Problem('mixed_rule', '日历提醒是独立任务，不组合股票价格。')
        at = timestamp(rule['scheduled_at'])
        if future and at <= now:
            raise Problem('past_time', '指定时间已过去，请修改后再确认。')
        exact_keys(schedule, ['mode', 'timezone'])
        if schedule != {'mode': 'once', 'timezone': 'Asia/Shanghai'}:
            raise Problem('invalid_schedule', '日历提醒使用一次性安排和 Asia/Shanghai 时区。')
    else:
        raise Problem('unsupported_rule', '当前仅支持价格条件与独立日历提醒。')
    return spec


def combine(values, combinator):
    if combinator == 'all':
        return False if False in values else True if all(v is True for v in values) else None
    return True if True in values else False if all(v is False for v in values) else None


def evaluate(rule, observations, instrument_id, now, freshness):
    evidence = []
    for condition in rule['conditions']:
        o = observations.get(condition['id'], observations.get('last_price', {}))
        reason, result = o.get('reason_code'), None
        quality = o.get('quality', 'missing')
        if quality == 'valid':
            try:
                if o.get('instrument_id') != instrument_id or o.get('unit') != 'CNY' or o.get('field') != 'last_price':
                    quality, reason = 'conflict', 'identity_or_unit_mismatch'
                elif not o.get('provider') or not o.get('source_ref'):
                    quality, reason = 'missing', 'provenance_missing'
                elif not isinstance(freshness, (int, float)) or freshness <= 0:
                    quality, reason = 'error', 'freshness_policy_unverified'
                elif now - timestamp(o.get('source_time')) > freshness:
                    quality, reason = 'stale', 'source_time_stale'
                elif timestamp(o.get('source_time')) > now + 5 or timestamp(o.get('fetched_at')) > now + 5 or timestamp(o.get('fetched_at')) < timestamp(o.get('source_time')):
                    quality, reason = 'conflict', 'invalid_time_order'
                else:
                    actual, threshold = positive_decimal(o.get('value')), positive_decimal(condition['value'])
                    result = actual < threshold if condition['operator'] == 'lt' else actual > threshold
            except Problem:
                quality, reason = 'missing', 'invalid_value_or_time'
        evidence.append({'condition': condition, 'observation': o, 'result': result, 'quality': quality, 'reason_code': reason})
    return {'result': combine([e['result'] for e in evidence], rule['combinator']), 'evidence': evidence,
            'warnings': [e['reason_code'] or e['quality'] for e in evidence if e['quality'] != 'valid']}


def transition(state, result, now, cooldown):
    """Return a new runtime state and decision; unknown never rearms an episode."""
    s = dict(state)
    if result is None:
        return s, 'insufficient_data'
    if result is False:
        s.update(last_result=False, episode_notified=False)
        return s, 'no_match'
    if s.get('last_result') is not True:
        s['episode'] = s.get('episode', 0) + 1
        s['episode_notified'] = False
    s['last_result'] = True
    if s.get('episode_notified'):
        return s, 'already_notified'
    if now < s.get('cooldown_until', 0):
        return s, 'cooldown_suppressed'
    s.update(episode_notified=True, cooldown_until=now + cooldown)
    return s, 'notify'
