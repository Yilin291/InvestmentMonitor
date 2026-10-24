"""Synthetic mapping fixtures based on V0 shape; never live success evidence."""
import tempfile
import unittest
from pathlib import Path
from backend.providers import FuyaoProvider
from backend.store import Store
from backend.manage import import_instruments

class FuyaoMappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'fixture.sqlite')
        import_instruments(self.store,{'validation_evidence':'TEST ONLY','instruments':[{'id':'test','code':'999999','market':'SH','name':'TEST ONLY','asset_class':'stock','currency':'CNY'}]})
    def tearDown(self):self.tmp.cleanup()
    def test_actual_shape_never_fabricates_unit_or_exchange_time(self):
        provider=FuyaoProvider(self.store,key='test',transport=lambda *a,**k:{'code':0,'data':{'timestamp':12345,'item':[{'thscode':'999999.SH','last_price':'10.00000000000000000001'}]}})
        o=provider.quote('test',1800000000)['last_price'];self.assertEqual(o['value'],'10.00000000000000000001');self.assertIsNone(o['unit']);self.assertIsNone(o['source_time']);self.assertEqual(o['quality'],'missing')
    def test_http_200_business_failure_and_empty_data(self):
        for response,expected in [({'code':2003},'fuyao_business_error'),({'code':0,'data':{'item':[]}},'fuyao_empty_data')]:
            p=FuyaoProvider(self.store,key='test',transport=lambda *a,**k:response);self.assertEqual(p.quote('test',1800000000)['last_price']['reason_code'],expected)
    def test_calendar_truncated_range_not_closed(self):
        p=FuyaoProvider(self.store,key='test',transport=lambda *a,**k:{'code':0,'data':{'item':[{'date':'20261023'}]}})
        r=p.market(1792775628);self.assertEqual(r['status'],'unknown');self.assertEqual(r['reason_code'],'calendar_coverage_incomplete')
    def test_wrong_symbol_and_invalid_price(self):
        p=FuyaoProvider(self.store,key='test',transport=lambda *a,**k:{'code':0,'data':{'item':[{'thscode':'other','last_price':10}]}})
        self.assertEqual(p.quote('test',1800000000)['last_price']['reason_code'],'fuyao_symbol_conflict')
