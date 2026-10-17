import copy
import json
from pathlib import Path
import unittest

from context.export import convert
from risk.pipeline import analyze, score_location

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8-sig'))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.events = read('false_data/accidents.json')
        self.crossings = read('false_data/crossings.geojson')

    def test_documented_scores_on_supplied_groups(self):
        events = {e['event_id']: e for e in self.events}
        features = {f['properties']['id']: f for f in self.crossings['features']}
        for expected in read('false_data/hotspots.json'):
            actual = score_location(features[expected['crossing_id']], [events[i] for i in expected['event_ids']])
            self.assertEqual(actual['scor'], expected['scor'])
            self.assertEqual(actual['componente_scor'], expected['componente_scor'])
            self.assertEqual(actual['pe_ore'], expected['pe_ore'])

    def test_unknown_does_not_add_context(self):
        f = copy.deepcopy(self.crossings['features'][0])
        for key in ('semafor', 'benzi', 'scoala_150m', 'statie_100m'):
            f['properties'][key] = None
        self.assertEqual(score_location(f, [self.events[0]])['scor'], 3)

    def test_duplicates_conflicts_and_eligibility(self):
        baseline = analyze(self.events, self.crossings)
        self.assertEqual(analyze(self.events + [self.events[0]], self.crossings), baseline)
        changed = dict(self.events[0], gravitate='deces')
        with self.assertRaises(ValueError):
            analyze(self.events + [changed], self.crossings)
        statuses = {x['event_id']: x['status'] for x in baseline[1]['associations']}
        self.assertEqual(statuses['ev-004'], 'precision_mismatch')
        self.assertEqual(statuses['ev-016'], 'ineligible')
        self.assertEqual(statuses['ev-017'], 'ineligible')

    def test_ambiguous_and_outside_radius(self):
        f = copy.deepcopy(self.crossings['features'][0])
        f['properties']['id'] = 'another'
        _, report = analyze([self.events[0]], dict(features=self.crossings['features'] + [f]))
        self.assertEqual(report['associations'][0]['status'], 'ambiguous')
        far = dict(self.events[0], lon=27.4)
        self.assertEqual(analyze([far], self.crossings)[1]['associations'][0]['status'], 'unmatched')

    def test_cached_osm_export(self):
        result = convert(read('crossings_test.geojson'), '2026-10-17')
        self.assertEqual(len(result['features']), 27)
        for f in result['features']:
            self.assertEqual(f['properties']['tip'], 'trecere')
            for key in ('benzi', 'tip_strada', 'scoala_150m', 'statie_100m'):
                self.assertIsNone(f['properties'][key])


if __name__ == '__main__':
    unittest.main()
