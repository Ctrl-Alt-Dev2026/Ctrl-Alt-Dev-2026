import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from shapely.geometry import box, shape

from context.city import merge_payloads, speed_profile, zone_profiles, tiles, TO_WGS84, fetch_job, boundary_from, build
from context.export import crossing_signal


class CityTests(unittest.TestCase):
    def test_city_pipeline_filters_boundary_and_preserves_contract(self):
        def payload(elements):
            return dict(endpoint='test', fetched_at='2026-10-17T12:00:00+00:00', bbox=[], query='test',
                        response=dict(elements=elements, osm3s=dict(timestamp_osm_base='2026-10-17T12:00:00Z')))
        ring = [dict(lon=x, lat=y) for x, y in [(27.57, 47.15), (27.60, 47.15),
                (27.60, 47.17), (27.57, 47.17), (27.57, 47.15)]]
        boundary = payload([dict(type='relation', id=1207838, tags=dict(name='Iași', boundary='administrative', admin_level='8'),
                                 members=[dict(type='way', role='outer', ref=10, geometry=ring)])])
        crossing = dict(type='node', id=1, lon=27.5877, lat=47.1564,
                        tags={'highway': 'crossing', 'crossing:signals': 'no'})
        outside = dict(crossing, id=2, lat=47.20)
        road = dict(type='way', id=3, nodes=[1, 5], geometry=[dict(lon=27.5877, lat=47.1564), dict(lon=27.588, lat=47.1564)],
                    tags=dict(highway='secondary', lanes='4', maxspeed='30'))
        school = dict(type='node', id=4, lon=27.5877, lat=47.1565, tags=dict(amenity='school'))
        result = build(boundary, [payload([crossing, outside, road, school])])
        self.assertEqual(result['geometry_report']['outside_crossings_removed'], 1)
        f = result['crossings']['features'][0]
        self.assertEqual(f['properties']['benzi'], 4)
        self.assertTrue(f['properties']['scoala_150m'])
        self.assertIsNone(f['properties']['statie_100m'])
        self.assertNotIn('maxspeed_kmh', f['properties'])
        self.assertEqual(result['geometry_report']['crossings'][0]['speed']['maxspeed_kmh'], 30)
        self.assertEqual(sum(z['properties']['mapped_crossings'] for z in result['zones']['features']), 1)

    def test_retry_is_bounded(self):
        args = SimpleNamespace(cache='unused', endpoint='unused', offline=False)
        response = requests.Response()
        response.status_code = 502
        with patch('context.city.fetch', side_effect=requests.HTTPError(response=response)) as fetch_mock, \
                patch('context.city.time.sleep') as sleep_mock, patch('builtins.print'):
            with self.assertRaises(requests.HTTPError):
                fetch_job(dict(id='tile', query='query', bbox=[]), args)
            self.assertEqual(fetch_mock.call_count, 3)
            self.assertEqual([c.args[0] for c in sleep_mock.call_args_list], [5, 10])

    def test_boundary_identity_is_not_guessed(self):
        with self.assertRaises(ValueError):
            boundary_from(dict(response=dict(elements=[])))
        with self.assertRaises(ValueError):
            boundary_from(dict(response=dict(elements=[dict(type='relation', tags=dict(name='Iași', admin_level='4'))])))

    def test_signal_tags_conflict_and_absence(self):
        self.assertIs(crossing_signal({'crossing:signals': 'yes'}), True)
        self.assertIs(crossing_signal({'crossing:signals': 'no'}), False)
        self.assertIsNone(crossing_signal({'crossing:markings': 'yes'}))
        self.assertIsNone(crossing_signal({'crossing': 'uncontrolled', 'crossing:signals': 'yes'}))

    def test_overlap_deduplication_and_conflict(self):
        element = dict(type='node', id=1, lat=47.15, lon=27.58)
        p = dict(response=dict(elements=[element]))
        self.assertEqual(merge_payloads([p, p]), [element])
        other = copy.deepcopy(p)
        other['response']['elements'][0]['lat'] = 47.16
        with self.assertRaises(ValueError):
            merge_payloads([p, other])

    def test_speed_is_explicit_and_consistent(self):
        def road(value=None, **extra):
            return dict(id=1, tags=dict(extra, **({'maxspeed': value} if value is not None else {})))
        self.assertEqual(speed_profile([road('50')])['maxspeed_kmh'], 50)
        self.assertEqual(speed_profile([road('30 km/h')])['maxspeed_kmh'], 30)
        self.assertEqual(speed_profile([road('50', **{'maxspeed:type': 'RO:urban'})])['maxspeed_kmh'], 50)
        for roads in ([road()], [road('RO:urban')], [road('50'), road('30')],
                      [road('50'), road()], [road('50', **{'maxspeed:conditional': '30 @ (school_hours)'})]):
            self.assertIsNone(speed_profile(roads)['maxspeed_kmh'])

    def test_grid_covers_boundary_and_empty_zones_are_unknown(self):
        boundary = box(540100, 5220100, 542100, 5222100)
        lon, lat = TO_WGS84(541000, 5221000)
        props = dict(id='x-1', semafor=False, benzi=4, iluminat=None, tip_strada='secondary',
                     scoala_150m=None, statie_100m=True)
        crossings = dict(features=[dict(properties=props, geometry=dict(type='Point', coordinates=[lon, lat]))])
        report = dict(crossings=[dict(id='x-1', speed=dict(maxspeed_kmh=None), roads=[])])
        result = zone_profiles(boundary, crossings, report)
        self.assertEqual(sum(z['properties']['mapped_crossings'] for z in result['features']), 1)
        self.assertEqual(sum(z['properties']['unsignalized_4plus_lanes'] for z in result['features']), 1)
        self.assertTrue(any(z['properties']['data_status'].startswith('no_mapped') for z in result['features']))
        for z in result['features']:
            self.assertNotIn('scor', z['properties'])
            self.assertTrue(shape(z['geometry']).is_valid)
        self.assertAlmostEqual(sum(z['properties']['area_m2'] for z in result['features']), boundary.area, places=2)
        self.assertTrue(list(tiles(boundary)))


if __name__ == '__main__':
    unittest.main()
