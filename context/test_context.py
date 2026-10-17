import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from context.collect import fetch
from context.enrich import enrich, geometry


def payload(elements):
    return dict(endpoint='test', fetched_at='2026-10-17T12:00:00+00:00', bbox=[],
                response=dict(elements=elements, osm3s=dict(timestamp_osm_base='2026-10-17T12:00:00Z')))


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.coord = dict(lon=27.5896262, lat=47.1556633)
        self.source = dict(type='FeatureCollection', features=[dict(type='Feature',
            geometry=dict(type='Point', coordinates=[self.coord['lon'], self.coord['lat']]),
            properties=dict(osm_id=1, highway='crossing', crossing='uncontrolled'))])
        self.road = dict(type='way', id=10, nodes=[1, 2],
                         geometry=[self.coord, dict(lon=27.5900, lat=47.1557)],
                         tags=dict(highway='residential', lanes='2'))

    def run_join(self, roads, schools=None, stops=None):
        return enrich(self.source, dict(roads=payload(roads), schools=payload(schools or []),
                                        stops=payload(stops or [])), '2026-10-17')

    def test_geometry_alone_does_not_link(self):
        self.road['nodes'] = [3, 4]
        result, _ = self.run_join([self.road])
        self.assertIsNone(result['features'][0]['properties']['benzi'])

    def test_membership_requires_coordinate_agreement(self):
        self.road['geometry'][0] = dict(lon=27.58, lat=47.15)
        result, report = self.run_join([self.road])
        self.assertIsNone(result['features'][0]['properties']['benzi'])
        self.assertEqual(len(report['crossings'][0]['rejected_roads']), 1)

    def test_conflicting_and_missing_road_tags_stay_unknown(self):
        other = copy.deepcopy(self.road)
        other['id'] = 11
        other['tags']['lanes'] = '4'
        result, _ = self.run_join([self.road, other])
        self.assertIsNone(result['features'][0]['properties']['benzi'])
        self.assertEqual(result['features'][0]['properties']['tip_strada'], 'residential')
        other['tags'].pop('lanes')
        self.assertIsNone(self.run_join([self.road, other])[0]['features'][0]['properties']['benzi'])

    def test_school_polygon_distance_and_missing_pois(self):
        school = dict(type='way', id=20, nodes=[5, 6, 7, 8, 5], tags=dict(amenity='school'),
                      geometry=[dict(lon=27.5895, lat=47.1555), dict(lon=27.59, lat=47.1555),
                                dict(lon=27.59, lat=47.156), dict(lon=27.5895, lat=47.156),
                                dict(lon=27.5895, lat=47.1555)])
        result, report = self.run_join([self.road], [school])
        self.assertIs(result['features'][0]['properties']['scoala_150m'], True)
        self.assertEqual(report['crossings'][0]['schools_150m'][0]['distance_m'], 0)
        self.assertIsNone(result['features'][0]['properties']['statie_100m'])
        school['tags']['amenity'] = 'kindergarten'
        self.assertIsNone(self.run_join([], [school])[0]['features'][0]['properties']['scoala_150m'])

    def test_cache_reuse_and_api_error_not_cached(self):
        response = Mock()
        response.json.return_value = payload([])['response']
        with tempfile.TemporaryDirectory() as directory, patch('context.collect.requests.post', return_value=response) as post:
            self.assertFalse(fetch('query', directory)[1])
            self.assertTrue(fetch('query', directory, offline=True)[1])
            self.assertEqual(post.call_count, 1)
            response.json.return_value = dict(elements=[], remark='runtime error')
            with self.assertRaises(ValueError):
                fetch('broken query', directory)
            self.assertEqual(len(list(Path(directory).glob('*.json'))), 1)
            with self.assertRaises(FileNotFoundError):
                fetch('uncached', directory, offline=True)

    def test_relation_without_geometry_rejected(self):
        with self.assertRaises(ValueError):
            geometry(dict(type='relation', id=5, tags=dict(type='multipolygon'), members=[]))


if __name__ == '__main__':
    unittest.main()
