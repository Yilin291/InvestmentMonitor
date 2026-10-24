"""Adapter contract only. These tests deliberately do not claim PostgreSQL execution."""
import unittest
from backend.postgres import Record, postgres_sql, from_environment
from backend.serve import preflight

class PostgresContractTests(unittest.TestCase):
    def test_parameterized_fixed_sql_translation(self):
        self.assertEqual(postgres_sql('SELECT * FROM instruments WHERE instr(name,?)>0'),'SELECT * FROM instruments WHERE strpos(name,%s)>0')
        self.assertEqual(postgres_sql('INSERT OR IGNORE INTO ticks(id,started_at) VALUES(?,?)'),'INSERT INTO ticks(id,started_at) VALUES(%s,%s) ON CONFLICT DO NOTHING')
    def test_record_compatibility(self):
        row=Record(version=2,spec='{}');self.assertEqual(row[0],2);self.assertEqual(row['version'],2)
    def test_production_never_falls_back_to_sqlite(self):
        with self.assertRaises(RuntimeError):from_environment({'APP_ENV':'production'})
        preflight({'APP_ENV':'production','APP_ORIGIN':'https://example.test','SUPABASE_DB_URL':'postgresql://placeholder.invalid/product'})
        # Acceptance above checks only configuration, not connection success.
