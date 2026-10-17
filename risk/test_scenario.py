import unittest
from unittest.mock import patch

from risk.inspect import read, breakdown
from risk.scenario import scenario


class ScenarioTests(unittest.TestCase):
    def test_real_infrastructure_drives_context_and_demo_is_separate(self):
        with patch('risk.scenario.read', wraps=read) as reader:
            report = scenario()
        self.assertEqual(report['data_mode'], 'simulation_mixed_sources')
        self.assertEqual(report['calculation']['event_subtotal'], 9)
        self.assertEqual(report['calculation']['context_subtotal'], 4)
        self.assertEqual(report['calculation']['result']['scor'], 13)
        paths = [str(c.args[0]).replace('\\', '/') for c in reader.call_args_list]
        self.assertFalse(any('false_data/crossings' in p for p in paths))
        self.assertTrue(any('observed/iasi/crossings.geojson' in p for p in paths))

    def test_other_real_crossing_changes_total_for_same_demo_accidents(self):
        a = scenario()
        b = scenario(crossing_id='osm-node-6194970559')
        self.assertEqual(a['calculation']['event_subtotal'], b['calculation']['event_subtotal'])
        self.assertEqual(b['calculation']['context_subtotal'], 2)
        self.assertEqual(b['calculation']['result']['scor'], 11)


if __name__ == '__main__':
    unittest.main()
