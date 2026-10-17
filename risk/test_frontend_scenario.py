import unittest
from unittest.mock import patch

from risk.frontend_scenario import build, validate
from risk.inspect import ROOT, read


class FrontendScenarioTests(unittest.TestCase):
    def test_frontend_bundle_uses_real_geometry_and_accurate_totals(self):
        with patch('risk.frontend_scenario.read', wraps=read) as reader:
            bundle = build()
        validate(bundle)
        self.assertFalse(any('false_data/crossings' in str(c.args[0]).replace('\\', '/') for c in reader.call_args_list))
        original = read(ROOT / 'context/output/observed/iasi/crossings.geojson')
        self.assertEqual(len(bundle['crossings.geojson']['features']), 1210)
        self.assertEqual([f['geometry'] for f in original['features']],
                         [f['geometry'] for f in bundle['crossings.geojson']['features']])
        self.assertEqual(bundle['manifest.json']['nr_evenimente'], 9)
        self.assertEqual(bundle['manifest.json']['nr_verificate'], 0)
        self.assertEqual(bundle['manifest.json']['nr_articole'], 0)
        self.assertEqual(sorted(h['scor'] for h in bundle['hotspots.json']), [9, 11, 13])
        self.assertEqual(bundle['measures.json'], [])

    def test_validation_detects_score_tampering(self):
        bundle = build()
        bundle['hotspots.json'][0]['scor'] += 1
        with self.assertRaises(ValueError):
            validate(bundle)


if __name__ == '__main__':
    unittest.main()
