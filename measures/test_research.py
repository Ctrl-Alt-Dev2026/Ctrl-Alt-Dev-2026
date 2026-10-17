import unittest

from measures.catalog import catalog
from measures.research import evidence
from measures.run import ROOT, build


class ResearchTests(unittest.TestCase):
    def test_unit_approximations_preserve_basis_and_do_not_invent_ranges(self):
        rows = {r['measure_id']: r for r in evidence()['indicative_unit_estimates']}
        self.assertEqual(rows['semafor_pietonal']['arithmetic_average_ron'], 293670.09)
        self.assertEqual(rows['semafor_pietonal']['indicative_rounded_ron'], 294000)
        self.assertEqual(rows['iluminat_trecere']['indicative_rounded_ron'], 140000)
        self.assertEqual(rows['semafor_pietonal']['vat'], 'excluded')
        self.assertEqual(rows['iluminat_trecere']['vat'], 'not_explicit_on_page')
        self.assertTrue(all(r['uncertainty_range_ron'] is None for r in rows.values()))

    def test_every_measure_has_explicit_coverage_and_valid_references(self):
        data = evidence()
        measures = {r['id'] for r in catalog()}
        self.assertEqual(measures, {r['measure_id'] for r in data['coverage']})
        for kind in ('cost_references', 'effect_references'):
            rows = data[kind]
            ids = {r['id'] for r in rows}
            self.assertEqual(len(ids), len(rows))
            for row in rows:
                self.assertIn(row['measure_id'], measures)
                self.assertTrue(row['url'].startswith('https://'))
                self.assertFalse(row['catalog_eligible'])
                self.assertTrue(row['source_access'])
            link_key = 'cost_ids' if kind == 'cost_references' else 'effect_ids'
            for coverage in data['coverage']:
                self.assertTrue(set(coverage[link_key]) <= ids)
                self.assertTrue(coverage['remaining'])

    def test_cmf_and_crf_consistent_and_context_preserved(self):
        data = evidence()
        for row in data['effect_references']:
            self.assertAlmostEqual(1 - row['cmf'], row['crf_fraction'])
            for key in ('conditions', 'reason', 'decision', 'study', 'quality'):
                self.assertTrue(row[key])
        lighting = next(r for r in data['effect_references'] if r['id'] == 'cmf-2873')
        self.assertEqual(lighting['decision'], 'rejected_for_current_urban_scenarios')
        self.assertIn('rural', lighting['conditions'])

    def test_research_does_not_become_catalog_estimates_or_change_scenarios(self):
        data = build(ROOT/'risk/output/frontend-scenario/data')
        self.assertEqual(data['research_evidence.json'], evidence())
        self.assertEqual([r['scenario_score_unchanged'] for r in data['scenario_measures.json']['locations']], [13, 11, 9])
        for row in data['measures.json']:
            for key in ('cost_lei_min', 'cost_lei_max', 'sursa_cost', 'reducere_tipica', 'sursa_reducere'):
                self.assertIsNone(row[key])


if __name__ == '__main__':
    unittest.main()
