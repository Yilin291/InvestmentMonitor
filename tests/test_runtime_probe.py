import unittest
from backend.runtime_probe import failure, probe

class RuntimeProbeTests(unittest.TestCase):
    def test_errors_are_actionable_without_connection_identity(self):
        cases = [('missing "=" after "private-value"', 'database_connection_string_invalid'),
                 ('could not translate host name "private-host"', 'database_dns_failed'),
                 ('server does not support SSL', 'database_tls_unsupported'),
                 ('password authentication failed for user private-user', 'database_authentication_failed')]
        for message, expected in cases:
            with self.subTest(expected=expected):
                result = failure(RuntimeError(message))
                self.assertEqual(result['reason'], expected)
                self.assertNotIn('private', str(result))
    def test_probe_rejects_sqlite_before_writing(self):
        class LocalStore: backend = 'sqlite'
        with self.assertRaisesRegex(RuntimeError, 'requires PostgreSQL'):
            probe(LocalStore())
