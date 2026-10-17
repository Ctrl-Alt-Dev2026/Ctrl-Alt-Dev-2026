import hashlib
import unittest

from measures.run import ROOT, build


class FrontendTests(unittest.TestCase):
    def test_all_three_scenarios_include_cost_basis_and_unknowns(self):
        dataset = ROOT/'risk/output/frontend-scenario/data'
        before = {p.name: p.read_bytes() for p in dataset.iterdir() if p.is_file()}
        bundle = build(dataset)
        payload = bundle['frontend_measures.json']
        self.assertEqual(payload['data_mode'], 'simulation_mixed_sources')
        self.assertIn('SCENARIU', payload['warning'])
        self.assertEqual([r['scenario_score'] for r in payload['locations']], [13, 11, 9])
        for row in payload['locations']:
            self.assertEqual(row['hotspot_id'], 'scenario-' + row['crossing_id'])
            self.assertIsNone(row['total_cost_ron'])
            selected = {r['measure_id']: r for r in row['measures'] if r['selected_for_display']}
            self.assertEqual(len(selected), 3)
            self.assertIsNone(selected['observatie_teren']['indicative_cost'])
            for identifier, amount, year, vat in (
                ('iluminat_trecere', 140000, 2024, 'not_explicit_on_page'),
                ('semafor_pietonal', 294000, 2020, 'excluded')):
                estimate = selected[identifier]['indicative_cost']
                self.assertEqual((estimate['indicative_rounded_ron'], estimate['year'], estimate['vat']), (amount, year, vat))
                self.assertTrue(estimate['source_url'].startswith('https://'))
                self.assertTrue(estimate['publisher'])
                self.assertTrue(estimate['calculation'])
                self.assertIn(str(year), estimate['display_label'])
            self.assertTrue(all(r['applicable_reduction'] is None for r in row['measures']))
        self.assertEqual(before, {p.name: p.read_bytes() for p in dataset.iterdir() if p.is_file()})
        for name, digest in payload['source_dataset_sha256'].items():
            self.assertEqual(digest, hashlib.sha256(before[name]).hexdigest())
        for detailed, ui in zip(bundle['scenario_measures.json']['locations'], payload['locations']):
            self.assertEqual(detailed['measure_details'], ui['measures'])


if __name__ == '__main__':
    unittest.main()
