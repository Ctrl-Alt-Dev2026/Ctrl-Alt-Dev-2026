import unittest
from unittest.mock import patch

from risk.inspect import ROOT, inspect_data, render


class InspectionTests(unittest.TestCase):
    def test_default_never_reads_synthetic_files(self):
        from risk.inspect import read
        with patch('risk.inspect.read', wraps=read) as reader:
            report = inspect_data(ROOT / 'context/output/observed/iasi')
        self.assertNotIn('synthetic', report)
        self.assertTrue(all('false_data' not in str(c.args[0]) for c in reader.call_args_list))
        self.assertNotIn('TOTAL DEMO', render(report))

    def test_current_snapshot_and_worked_example(self):
        report = inspect_data(ROOT / 'context/output/observed/iasi', ROOT / 'false_data')
        self.assertIsNone(report['observed']['score'])
        self.assertEqual(report['observed']['data_mode'], 'observed')
        demo = report['synthetic']
        self.assertEqual(demo['calculation']['result']['scor'], 12)
        self.assertEqual(demo['calculation']['event_subtotal'], 9)
        self.assertEqual(demo['calculation']['context_subtotal'], 3)
        self.assertEqual(demo['fixture_reference_score'], 13)
        self.assertEqual(demo['excluded_reference_events'][0]['event_id'], 'ev-004')
        self.assertIn('INTEGRAL SINTETICE', render(report))

    def test_invalid_zone_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError, 'Zone not found'):
            inspect_data(ROOT / 'context/output/observed/iasi', ROOT / 'false_data', zone_id='missing')


if __name__ == '__main__':
    unittest.main()
