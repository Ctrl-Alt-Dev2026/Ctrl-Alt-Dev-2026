import copy
import unittest

from measures.catalog import catalog
from measures.rules import evaluate
from measures.run import ROOT, build


def feature(**props):
    return dict(type='Feature', geometry=dict(type='Point', coordinates=[27.58, 47.16]),
                properties=dict(id='test', tip='trecere', semafor=None, benzi=None,
                                iluminat=None, tip_strada=None, scoala_150m=None,
                                statie_100m=None) | props)


def event(i, **fields):
    return dict(event_id=str(i), in_iasi=True, precizie_loc='trecere', lon=27.58,
                lat=47.16, ora=None, noapte=None, cauza_raportata=None,
                gravitate='usor', verificat=False, participanti=['pieton']) | fields


def run(f, es, **kwargs):
    return evaluate(f, es, mode='simulation_mixed_sources', **kwargs)


def states(result):
    return {r['measure_id']: r['status'] for r in result['rules']}


class RulesTests(unittest.TestCase):
    def test_unknowns_do_not_trigger_construction(self):
        result = run(feature(), [event(1), event(2)])
        self.assertEqual([c['measure_id'] for c in result['candidates']], ['observatie_teren'])
        self.assertEqual(states(result)['iluminat_trecere'], 'insufficient_data')
        self.assertEqual(states(result)['semafor_pietonal'], 'insufficient_data')

    def test_explicit_night_not_clock_and_unique_events(self):
        f = feature()
        e = event(1, noapte=True)
        self.assertEqual(states(run(f, [e, copy.deepcopy(e)]))['iluminat_trecere'], 'not_matched')
        self.assertEqual(states(run(f, [e, event(2, noapte=True)]))['iluminat_trecere'], 'matched')
        self.assertEqual(states(run(f, [event(1, ora='23:00', noapte=False), event(2, noapte=False)]))['iluminat_trecere'], 'not_matched')
        with self.assertRaises(ValueError):
            run(f, [e, event(1, noapte=False)])

    def test_signal_and_lanes_require_explicit_conditions(self):
        self.assertEqual(states(run(feature(semafor=False, benzi=4), []))['semafor_pietonal'], 'matched')
        self.assertEqual(states(run(feature(semafor=True, benzi=4), []))['semafor_pietonal'], 'not_matched')
        self.assertEqual(states(run(feature(semafor=None, benzi=4), []))['semafor_pietonal'], 'insufficient_data')
        self.assertEqual(states(run(feature(tip='intersectie', semafor=False, benzi=4), []))['semafor_pietonal'], 'not_matched')

    def test_school_needs_route_and_geometry_confirmations(self):
        f, es = feature(scoala_150m=True, benzi=2), [event(1)]
        self.assertEqual(states(run(f, es))['trecere_inaltata'], 'insufficient_data')
        checks = dict(no_bus_route=True, no_emergency_route=True, calming_road_compatible=True)
        self.assertEqual(states(run(f, es, checks=checks))['trecere_inaltata'], 'matched')
        checks['no_bus_route'] = False
        self.assertEqual(states(run(f, es, checks=checks))['limitator_viteza'], 'not_matched')
        self.assertEqual(states(run(f, []))['trecere_inaltata'], 'not_matched')

    def test_priority_requires_explicit_repetition_and_intersection(self):
        es = [event(i, precizie_loc='intersectie', cauza_raportata='neacordare_prioritate') for i in (1, 2)]
        self.assertEqual(states(run(feature(tip='intersectie'), es))['analiza_intersectie'], 'matched')
        self.assertEqual(states(run(feature(tip='intersectie'), es[:1]))['analiza_intersectie'], 'not_matched')

    def test_observed_unverified_mismatch_and_bad_types_refused(self):
        with self.assertRaises(ValueError):
            evaluate(feature(), [event(1)], mode='observed')
        with self.assertRaises(ValueError):
            run(feature(), [event(1, lon=27.6)])
        with self.assertRaises(ValueError):
            run(feature(semafor=0), [])
        with self.assertRaises(ValueError):
            run(feature(benzi=True), [])
        with self.assertRaises(ValueError):
            run(feature(), [event(1, participanti=['autoturism'])])
        with self.assertRaises(ValueError):
            evaluate(feature(sursa='OSM'), [event(1, verificat=True, data_mode='synthetic')], mode='observed')

    def test_three_scenarios_catalog_and_inputs_unchanged(self):
        path = ROOT / 'risk/output/frontend-scenario/data'
        before = {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}
        bundle = build(path)
        rows = bundle['scenario_measures.json']['locations']
        self.assertEqual([r['scenario_score_unchanged'] for r in rows], [13, 11, 9])
        self.assertEqual(sum(len(r['event_ids']) for r in rows), 9)
        for row in rows:
            self.assertLessEqual(len(row['suggested']), 3)
            self.assertTrue(all(c['motiv'].startswith('SCENARIU:') for c in row['candidates']))
            self.assertEqual([c['measure_id'] for c in row['suggested']],
                             ['observatie_teren', 'iluminat_trecere', 'semafor_pietonal'])
            self.assertEqual(states(row)['trecere_inaltata'], 'not_matched')
        for row in catalog():
            for key in ('cost_lei_min', 'cost_lei_max', 'sursa_cost', 'reducere_tipica', 'sursa_reducere'):
                self.assertIsNone(row[key])
        self.assertEqual(before, {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()})


if __name__ == '__main__':
    unittest.main()
