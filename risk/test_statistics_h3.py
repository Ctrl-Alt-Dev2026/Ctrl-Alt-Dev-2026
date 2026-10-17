import copy
import json
from pathlib import Path
import tempfile
import unittest

import h3
from shapely.geometry import Point, shape

from risk.inspect import ROOT, read
from risk.statistics import event_statistics
from risk.h3_layer import aggregate
from risk.run import prepare


class StatisticsH3Tests(unittest.TestCase):
    def setUp(self):
        self.events = read(ROOT / 'false_data/accidents.json')

    def test_unknown_hours_and_day_night_causes_reconcile(self):
        events = [self.events[i] for i in (0, 1, 3)]
        s = event_statistics(events + [events[0]])
        self.assertEqual(s['nr_evenimente'], 3)
        self.assertEqual(sum(s['pe_ore']), 2)
        self.assertEqual(s['ora_necunoscuta'], 1)
        self.assertEqual(s['pe_ore'][0], 0)
        self.assertEqual(s['pe_ore'][21], 1)
        self.assertEqual((s['zi'], s['noapte'], s['necunoscut']), (1, 1, 1))
        self.assertEqual(sum(s['cauze'].values()), 3)
        self.assertEqual(s['cauze']['necunoscut'], 1)

    def test_invalid_time_and_conflicting_duplicate_rejected(self):
        for time in ('24:00', '7:30', '12:60', ''):
            with self.assertRaises(ValueError):
                event_statistics([dict(self.events[0], ora=time)])
        with self.assertRaises(ValueError):
            event_statistics([self.events[0], dict(self.events[0], gravitate='deces')])

    def test_h3_counts_resolution_and_geojson_coordinate_order(self):
        result = aggregate(self.events + [self.events[0]], 'synthetic')
        self.assertEqual(sum(f['properties']['nr_evenimente'] for f in result['features']), 14)
        indexed = {e['event_id']: e for e in self.events}
        for f in result['features']:
            p = f['properties']
            self.assertEqual(h3.get_resolution(p['h3']), 9)
            self.assertEqual(f['geometry']['coordinates'][0][0], f['geometry']['coordinates'][0][-1])
            for identifier in p['event_ids']:
                e = indexed[identifier]
                self.assertTrue(shape(f['geometry']).covers(Point(e['lon'], e['lat'])))
            self.assertEqual(sum(p['pe_ore']) + p['ora_necunoscuta'], p['nr_evenimente'])
        self.assertEqual(set(result['excluded_event_ids']), {'ev-015', 'ev-016', 'ev-017'})

    def test_runner_preserves_location_score_and_hotspot_h3(self):
        output = prepare(ROOT / 'false_data', 'synthetic')
        self.assertEqual([h['scor'] for h in output['hotspots.json']], [12, 8, 5])
        for h in output['hotspots.json']:
            self.assertEqual(h['h3'], h3.latlng_to_cell(h['lat'], h['lon'], 9))
        for s in output['location_statistics.json']['locations'].values():
            self.assertEqual(sum(s['pe_ore']) + s['ora_necunoscuta'], s['nr_evenimente'])

    def test_observed_mode_rejects_synthetic_manifest(self):
        with self.assertRaisesRegex(ValueError, 'Manifest schema/mode mismatch'):
            prepare(ROOT / 'false_data', 'observed', ROOT / 'context/output/observed/iasi')

    def test_observed_preflight_boundary_review_and_input_immutability(self):
        # Fabricated unit-test input exercising observed contract, never published as real data.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            event = dict(self.events[0], event_id='unit-only-reviewed', lat=47.1564, lon=27.5877, verificat=True)
            events = [event, dict(event, event_id='unit-only-unreviewed', verificat=False),
                      dict(event, event_id='unit-only-outside', lat=47.1795, lon=27.5098)]
            (directory / 'manifest.json').write_text(json.dumps(dict(schema_version='2.0', data_mode='observed')), encoding='utf-8')
            path = directory / 'accidents.json'
            path.write_text(json.dumps(events), encoding='utf-8')
            original = path.read_bytes()
            output = prepare(directory, 'observed', ROOT / 'context/output/observed/iasi')
            self.assertEqual(path.read_bytes(), original)
            report = output['analysis_report.json']
            self.assertEqual(report['eligible_events'], 1)
            self.assertEqual({r['status'] for r in report['preflight']},
                             {'not_manually_verified', 'outside_municipality_despite_in_iasi_flag'})
            self.assertEqual(sum(f['properties']['nr_evenimente'] for f in output['accidents_h3.geojson']['features']), 1)


if __name__ == '__main__':
    unittest.main()
