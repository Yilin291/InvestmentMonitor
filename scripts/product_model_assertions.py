"""Acceptance oracle for the three fixed PRODUCT prompts, not a general NLP judge."""
from decimal import Decimal, InvalidOperation
import re


def case_errors(name, result):
    errors = []
    def check(condition, code):
        if not condition: errors.append(code)
    drafts = result.get('drafts', [])
    questions = result.get('questions', [])
    unsupported = result.get('unsupported', [])
    if name == 'normal':
        check(result.get('status') == 'ready', 'normal_status')
        check(not questions and not unsupported, 'unexpected_clarification')
        check(len(drafts) == 1, 'exactly_one_draft')
        if len(drafts) != 1: return errors
        draft = drafts[0]
        check(draft.get('instrument_id') == 'CN.SH.600519', 'instrument')
        rule = draft.get('rule', {})
        check(rule.get('kind') == 'price_group' and rule.get('combinator') == 'all', 'condition_structure')
        conditions = rule.get('conditions', [])
        check(len(conditions) == 1, 'exactly_one_condition')
        if len(conditions) == 1:
            c = conditions[0]
            check(c.get('field') == 'last_price', 'field')
            check(c.get('operator') == 'gt', 'direction')
            try: correct = Decimal(str(c.get('value'))) == Decimal('1500')
            except (InvalidOperation, ValueError): correct = False
            check(correct, 'threshold')
            check(c.get('currency') == 'CNY', 'currency')
        check(draft.get('notification_policy') == {'mode':'on_episode','cooldown_seconds':86400}, 'rolling_cooldown')
        schedule = draft.get('schedule', {})
        check(schedule.get('mode') == 'market_interval' and schedule.get('timezone') == 'Asia/Shanghai', 'schedule')
    elif name in ('ambiguous', 'unsupported'):
        check(result.get('status') == 'needs_clarification', 'clarification_status')
        check(not drafts, 'clarification_must_not_draft')
        if name == 'ambiguous':
            stock = r'标的|股票|哪[只个家]|它.*指|贵州茅台'
            threshold = r'阈值|价格|涨幅|涨跌幅|涨了|多少|百分比'
            check(bool(questions), 'missing_questions')
            check(any(re.search(stock, q) for q in questions), 'missing_instrument_question')
            check(any(re.search(threshold, q) for q in questions), 'missing_threshold_question')
            check(all(re.search(stock+'|'+threshold, q) for q in questions), 'irrelevant_question')
            check(all(re.search(threshold, u) for u in unsupported), 'irrelevant_unsupported')
        else:
            account = r'账户|余额|资金'
            check(bool(unsupported) and all(re.search(account, u) for u in unsupported), 'missing_account_rejection')
            check(all(re.search(account, q) for q in questions), 'irrelevant_question')
    else: errors.append('unknown_case')
    return errors


def evidence_errors(evidence):
    errors = []
    cases = evidence.get('cases', [])
    if [c.get('name') for c in cases] != ['normal', 'ambiguous', 'unsupported']:
        errors.append('case_set')
    for case in cases:
        errors.extend(case.get('name', '?')+':'+e for e in case_errors(case.get('name'), case.get('result', {})))
    if evidence.get('audit_count') != 3: errors.append('audit_count')
    if evidence.get('tasks_created') != 0: errors.append('tasks_created')
    return errors
