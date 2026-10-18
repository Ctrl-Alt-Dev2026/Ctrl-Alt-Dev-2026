"""Conservation and separation tests for street analysis, using explicit test fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import h3

from risk.streets import analyze_source, enrich_dataset, street_context

ROOT = Path(__file__).resolve().parents[1]


class StreetTests(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads((ROOT / 'isu/seed/dataset.json').read_text(encoding='utf-8'))

    def test_observed_membership_geometry_counts_and_formula_preserved(self):
        original = deepcopy(self.dataset)
        result = enrich_dataset(self.dataset)
        self.assertEqual(self.dataset, original)
        self.assertEqual(result, enrich_dataset(result))
        for before, after in zip(original['streets']['features'], result['streets']['features']):
            self.assertEqual(before['geometry'], after['geometry'])
            self.assertEqual(before['properties']['id'], after['properties']['id'])
            for source in ('isu', 'presa'):
                p = after['properties']
                a = p['analiza'][source]
                self.assertEqual(a['event_ids'], list(dict.fromkeys(p[source + '_event_ids'])))
                self.assertEqual(a['nr_evenimente'], p[source + '_evenimente'])
                self.assertEqual(a['scor'], p[source + '_evenimente'] + 4*p[source + '_deces'] + 2*p[source + '_grav'])
                self.assertEqual(sum(a['pe_ore']) + a['ora_necunoscuta'], a['nr_evenimente'])
                self.assertEqual(sum(a['cauze'].values()), a['nr_evenimente'])
                self.assertEqual(a['zi'] + a['noapte'] + a['necunoscut'], a['nr_evenimente'])
            self.assertEqual(after['properties']['context_osm']['event_ids'], [])

    def test_h3_never_assigns_coarse_events_even_if_they_have_coordinates(self):
        # A precise TEST event, explicitly synthetic; never written into observed outputs.
        d = deepcopy(self.dataset)
        d['manifest']['data_mode'] = 'synthetic'
        e = d['accidents'][0]
        e.update(precizie_loc='segment', lat=47.156, lon=27.588, in_iasi=True)
        coarse = d['accidents'][1]
        coarse.update(precizie_loc='strada', lat=47.156, lon=27.588)
        result = enrich_dataset(d)
        cells = result['accidents_h3']['features']
        ids = [identifier for f in cells for identifier in f['properties']['event_ids']]
        self.assertEqual(ids, [e['event_id']])
        self.assertEqual(cells[0]['properties']['h3'], h3.latlng_to_cell(e['lat'], e['lon'], 9))
        self.assertIsNone(result['accidents'][1]['lat'])
        self.assertIsNone(result['accidents'][1]['lon'])

    def test_measures_use_reported_causes_never_invent_locations_counts_or_totals(self):
        template = dict(self.dataset['accidents'][0], event_id='test-only', ora=None,
                        noapte=None, cauza_raportata=None, gravitate='necunoscut')
        self.assertEqual(analyze_source([template])['masuri'], [])
        for cause in ('viteza', 'neacordare_prioritate', 'traversare_neregulamentara', 'vizibilitate'):
            e = dict(template, cauza_raportata=cause)
            analysis = analyze_source([e, e])
            self.assertEqual(analysis['nr_evenimente'], 1)
            self.assertEqual(analysis['pe_ore'][0], 0)
            m = analysis['masuri'][0]
            self.assertEqual(m['event_ids'], ['test-only'])
            self.assertFalse(m['amplasament_verificat'])
            self.assertIsNone(m['numar_interventii'])
            self.assertIsNone(m['cost_total'])
            self.assertNotIn('lat', m)
            if m['cost_unitar']:
                self.assertIn('source_url', m['cost_unitar'])
                self.assertEqual(m['cost_unitar']['estimate_type'], 'historical_project_average_not_quote')

    def test_osm_is_street_context_unknown_remains_unknown(self):
        context = ({'crossings': [dict(id='c', roads=[dict(tags={'name': 'Exact street'})])]},
                   {'features': [dict(properties=dict(id='c', semafor=None, iluminat=False,
                       scoala_150m=True, statie_100m=None, descarcat_la='2026-10-17'))]})
        result = street_context({'Exact street'}, context)
        self.assertEqual(result['atribute']['semafor'], dict(da=0, nu=0, necunoscut=1))
        self.assertEqual(result['atribute']['iluminat']['nu'], 1)
        self.assertEqual(result['event_ids'], [])
        self.assertEqual(street_context({'Other street'}, context)['crossing_ids'], [])
        self.assertIsNone(street_context({'Exact street'}, None)['treceri_cartografiate'])

    def test_conflicting_or_duplicate_street_membership_rejected(self):
        d = deepcopy(self.dataset)
        populated = next(f for f in d['streets']['features'] if f['properties']['isu_event_ids'])
        d['streets']['features'].append(deepcopy(populated))
        with self.assertRaisesRegex(ValueError, 'multiple streets'):
            enrich_dataset(d)


if __name__ == '__main__':
    unittest.main()
