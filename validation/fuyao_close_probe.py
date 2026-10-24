#!/usr/bin/env python3
"""Eight bounded sequential live requests. Prices parsed as Decimal, never float.

No production mutation. Evidence files are exclusive-create and contain only
allowlisted business fields; credential values and headers are never persisted.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Shanghai')
SYMBOLS = [('贵州茅台', '600519.SH'), ('中国平安', '601318.SH'), ('招商银行', '600036.SH')]
BASE = 'https://fuyao.aicubes.cn'
SAFE_FIELDS = {'thscode', 'ticker', 'name', 'exchange', 'asset_type', 'currency',
               'date_ms', 'date', 'close_price', 'open_price', 'high_price',
               'low_price', 'volume', 'turnover', 'list_date'}


def credential():
    key = os.environ.get('FUYAO_API_KEY', '')
    if key:
        return key
    path = ROOT / '.env.local'
    if not path.exists():
        return ''
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError('unsafe_env_file_permissions')
    for line in path.read_text().splitlines():
        parts = shlex.split(line, comments=True)
        for part in parts:
            if part.startswith('FUYAO_API_KEY='):
                return part.split('=', 1)[1]
    return ''


def serializable(value, key):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return value.replace(key, '[REDACTED]') if key else value
    if isinstance(value, list):
        return [serializable(v, key) for v in value]
    if isinstance(value, dict):
        return {k: serializable(v, key) for k, v in value.items()}
    return value


def request(path, params, key, label):
    started = datetime.now(TZ).isoformat()
    result = {'label': label, 'path': path, 'params': params, 'started_at': started,
              'http_status': None, 'passed': False}
    req = urllib.request.Request(BASE + path + '?' + urllib.parse.urlencode(params),
                                 headers={'X-api-key': key, 'Accept': 'application/json'})
    try:
        try:
            response = urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(1_000_001)
            result['http_status'] = response.status
        if len(body) > 1_000_000:
            raise ValueError('response_too_large')
        result['response_sha256'] = hashlib.sha256(body).hexdigest()
        envelope = json.loads(body, parse_float=Decimal,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
        result['business_code'] = envelope.get('code')
        rid = envelope.get('request_id')
        result['request_id'] = rid if isinstance(rid, str) and re.fullmatch(r'[A-Za-z0-9:_-]{1,160}', rid) else None
        result['provider_message'] = str(envelope.get('message', ''))[:160].replace(key, '[REDACTED]')
        data = envelope.get('data')
        if isinstance(data, dict):
            result['data_fields'] = sorted(data)
            result['data_timestamp_ms'] = data.get('timestamp')
            result['symbol_echo'] = data.get('thscode')
            result['adjust_echo'] = data.get('adjust')
            rows = data.get('item')
            if isinstance(rows, list):
                result['rows'] = [{k: v for k, v in row.items() if k in SAFE_FIELDS}
                                  if isinstance(row, dict) else None for row in rows]
        result['transport_business_ok'] = response.status == 200 and envelope.get('code') == 0
    except Exception as error:
        result['error_type'] = type(error).__name__
        result['failure_reason'] = 'network_http_json_or_size_failure'
    result['finished_at'] = datetime.now(TZ).isoformat()
    return result


def date_of_ms(value):
    if type(value) is not int:
        raise ValueError('date_ms_not_integer')
    value = datetime.fromtimestamp(value // 1000, TZ)
    if value.hour or value.minute or value.second:
        raise ValueError('date_ms_not_shanghai_midnight')
    return value.date().isoformat()


def main():
    now = datetime.now(TZ)
    out = Path(os.environ.get('EVIDENCE_OUT', str(ROOT / 'validation/evidence' /
               ('fuyao_close_three_' + now.strftime('%Y%m%dT%H%M%S%f%z') + '.json'))))
    if out.exists():
        raise ValueError('refuse_existing_evidence_path')
    key = credential()
    evidence = {'checked_at': now.isoformat(), 'mode': 'live_read_only_sequential',
                'decimal_parsing': 'json.parse_float=Decimal; persisted decimal strings',
                'credentials_configured': bool(key), 'checks': [], 'samples': [],
                'overall_passed': False, 'production_rules_or_notifications_created': False}
    if key:
        calendar = request('/api/a-share/calendar/trading-days', {}, key, 'calendar')
        rows = calendar.get('rows', [])
        days = []
        try:
            for row in rows:
                day = date_of_ms(row['date_ms'])
                if row['date'] != day.replace('-', '') or day > now.date().isoformat():
                    raise ValueError('calendar_date_mismatch')
                days.append(day)
            calendar['passed'] = bool(calendar.get('transport_business_ok') and days and days == sorted(set(days)))
        except Exception:
            calendar['failure_reason'] = 'calendar_date_or_order_invalid'
        calendar['completeness_verified'] = False
        calendar['future_coverage'] = False
        evidence['checks'].append(calendar)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=14)
        for name, symbol in SYMBOLS:
            time.sleep(0.5)
            meta = request('/api/meta/tickers/search', {'q': name, 'asset_type': 'a-share', 'limit': 10}, key, 'meta:' + symbol)
            matches = [r for r in meta.get('rows', []) if isinstance(r, dict) and r.get('thscode') == symbol]
            meta['passed'] = bool(meta.get('transport_business_ok') and len(matches) == 1 and
                                  all(matches[0].get(k) == v for k, v in {'name': name, 'ticker': symbol[:6],
                                       'currency': 'CNY', 'exchange': 'SH', 'asset_type': 'a-share'}.items()))
            evidence['checks'].append(meta)
            time.sleep(0.5)
            bar = request('/api/a-share/prices/historical', {'thscode': symbol, 'interval': '1d',
                          'adjust': 'none', 'start': int(start.timestamp()) * 1000,
                          'end': int(end.timestamp()) * 1000}, key, 'daily:' + symbol)
            try:
                dates = []
                for row in bar.get('rows', []):
                    day = date_of_ms(row['date_ms'])
                    if not start.date().isoformat() <= day <= end.date().isoformat():
                        raise ValueError('date_outside_request_window')
                    close = row['close_price']
                    if isinstance(close, bool) or not isinstance(close, (Decimal, int)) or not Decimal(close).is_finite() or close <= 0:
                        raise ValueError('invalid_close')
                    if row.get('thscode', symbol) != symbol:
                        raise ValueError('wrong_symbol')
                    dates.append(day)
                if bar.get('symbol_echo') not in (None, symbol):
                    raise ValueError('wrong_symbol_echo')
                if bar.get('adjust_echo') not in (None, 'none'):
                    raise ValueError('wrong_adjust_echo')
                bar['passed'] = bool(bar.get('transport_business_ok') and dates and dates == sorted(set(dates)))
                # Never infer calendar completeness. This sample supports only the observed date.
                completed = [(day, row) for day, row in zip(dates, bar['rows'])
                             if day < now.date().isoformat() or now.hour >= 15]
                if not completed:
                    raise ValueError('no_completed_bar_candidate')
                day, last = completed[-1]
                close = Decimal(last['close_price'])
                evidence['samples'].append({'name': name, 'thscode': symbol, 'currency': 'CNY',
                    'trade_date': day, 'close_price': str(close), 'adjust': 'none',
                    'date_ms_semantics': 'daily_bar_date_not_exact_trade_time',
                    'request_symbol_binding': 'request_context; echo validated if supplied',
                    'calendar_contains_bar_date': day in days,
                    'latest_observed_calendar_date': days[-1] if days else None,
                    'expected_latest_completed_date': '2026-10-23' if now.date().isoformat() == '2026-10-24' else None,
                    'expected_date_basis': '2026-10-24 Saturday under SSE weekday rule plus observed 2026-10-23 trading date',
                    'request_id': bar.get('request_id'), 'meta_request_id': meta.get('request_id'),
                    'threshold_candidates': {'gt_true': str(close - Decimal('1')), 'gt_false': str(close + Decimal('1')),
                                             'equal_boundary': str(close)},
                    'thresholds_are_candidates_not_online_product_evidence': True})
            except Exception as error:
                bar['passed'] = False
                bar['failure_reason'] = str(error) if isinstance(error, ValueError) else type(error).__name__
            evidence['checks'].append(bar)
        time.sleep(0.5)
        error = request('/api/meta/tickers/search', {'asset_type': 'a-share', 'limit': 1}, key, 'live_invalid_parameter_missing_q')
        error['expected_business_code'] = 1001
        error['passed'] = error.get('http_status') in (200, 400) and error.get('business_code') == 1001
        evidence['checks'].append(error)
        evidence['overall_passed'] = len(evidence['samples']) == 3 and all(c['passed'] for c in evidence['checks'])
    else:
        evidence['mode'] = 'not_run'
        evidence['reason'] = 'credential_missing'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as f:
        json.dump(serializable(evidence, key), f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({'file': str(out), 'overall_passed': evidence['overall_passed'],
                      'checks': [{'label': c['label'], 'http_status': c.get('http_status'),
                                  'business_code': c.get('business_code'), 'passed': c['passed']} for c in evidence['checks']]}, ensure_ascii=False))
    return 0 if evidence['overall_passed'] else (1 if key else 2)


if __name__ == '__main__':
    sys.exit(main())
