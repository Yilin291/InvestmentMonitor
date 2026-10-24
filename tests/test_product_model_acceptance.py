import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from backend.manage import import_instruments
from backend.providers import Parser
from backend.store import Store
from scripts.product_model_assertions import case_errors, evidence_errors

ROOT = Path(__file__).resolve().parents[1]

class ProductModelAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.good = json.loads((ROOT/'artifacts/product-model-live.json').read_text())

    def test_historical_real_positive(self):
        self.assertEqual(evidence_errors(self.good), [])

    def test_lead_three_negative_results(self):
        bad = json.loads((ROOT/'docs/lead/TWO_SESSIONS_PRODUCT_MODEL_NEGATIVE.json').read_text())['evidence']
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'test.sqlite')
            import_instruments(store,json.loads((ROOT/'deploy/instruments_verified.json').read_text()))
            for case in bad['cases']:
                payload = {k:case['result'][k] for k in ('drafts','questions','unsupported')}
                def transport(*args, **kwargs):
                    return {'choices':[{'message':{'content':json.dumps(payload)}}]}
                result = Parser(store, transport=transport, key='TEST ONLY').parse('TEST ONLY replay',time.time())
                with self.subTest(case=case['name']):
                    self.assertTrue(case_errors(case['name'],result))
            self.assertEqual(store.query('SELECT count(*) AS n FROM parser_audit')[0]['n'],3)
            self.assertEqual(store.query('SELECT count(*) AS n FROM tasks')[0]['n'],0)

    def test_semantic_mutations(self):
        mutations = [('instrument_id','WRONG'),('rule.combinator','any'),
                     ('rule.conditions.0.operator','lt'),('rule.conditions.0.value','1'),
                     ('rule.conditions.0.currency','USD'),('rule.conditions.0.field','change_pct'),
                     ('notification_policy.cooldown_seconds',3600)]
        for path,value in mutations:
            r = copy.deepcopy(self.good['cases'][0]['result']); target=r['drafts'][0]
            parts=path.split('.')
            for part in parts[:-1]:target=target[int(part)] if isinstance(target,list) else target[part]
            target[parts[-1]]=value
            with self.subTest(path=path): self.assertTrue(case_errors('normal',r))

    def test_side_effect_and_audit_assertions(self):
        for key,value in [('audit_count',2),('tasks_created',1)]:
            evidence=copy.deepcopy(self.good);evidence[key]=value
            self.assertIn(key,evidence_errors(evidence))

    def test_clarification_draft_and_irrelevant_extra_question(self):
        for case in self.good['cases'][1:]:
            r=copy.deepcopy(case['result']);r['questions'].append('你今天吃饭了吗？')
            self.assertIn('irrelevant_question',case_errors(case['name'],r))
            r=copy.deepcopy(case['result']);r['drafts']=self.good['cases'][0]['result']['drafts']
            self.assertIn('clarification_must_not_draft',case_errors(case['name'],r))
