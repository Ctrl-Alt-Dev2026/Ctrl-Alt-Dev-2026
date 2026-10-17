import copy
import unittest

from shapely.geometry import box

from context.index_review import audit_extras, junctions, normalize_additions


class IndexReviewTests(unittest.TestCase):
    def setUp(self):
        self.boundary = box(27.58, 47.15, 27.60, 47.17)
        self.points = {'1': [47.16, 27.59], '2': [47.16, 27.589],
                       '3': [47.16, 27.591], '4': [47.161, 27.59]}
        self.index = dict(meta=dict(descarcat_la='2026-10-17'), noduri=self.points,
            strazi={'a': [dict(nume='A', highway=['residential'], way_ids=[10], segmente=[[2, 1], [1, 3]])],
                    'b': [dict(nume='B', highway=['residential'], way_ids=[11], segmente=[[1, 4]])]})
        def road(identifier, nodes, name):
            return dict(type='way', id=identifier, nodes=nodes, tags=dict(highway='residential', name=name),
                        geometry=[dict(lat=self.points[str(n)][0], lon=self.points[str(n)][1]) for n in nodes])
        self.roads = [road(10, [2, 1, 3], 'A'), road(11, [1, 4], 'B')]

    def test_shared_node_three_arms_and_geometry_required(self):
        geo, rows, counts = junctions(self.index, self.boundary, self.roads, set())
        self.assertEqual(len(geo['features']), 1)
        self.assertEqual(geo['features'][0]['properties']['tip'], 'intersectie')
        self.assertTrue(rows[0]['manual_review_required'])
        self.assertEqual(rows[0]['verified_degree'], 3)
        self.assertIsNone(geo['features'][0]['properties']['benzi'])

    def test_name_change_with_two_arms_is_not_junction(self):
        index = copy.deepcopy(self.index)
        index['strazi']['a'][0]['segmente'] = [[2, 1]]
        index['strazi']['b'][0]['segmente'] = [[1, 3]]
        self.assertEqual(junctions(index, self.boundary, self.roads, set())[0]['features'], [])

    def test_overlapping_lines_without_shared_node_do_not_form_junction(self):
        index = copy.deepcopy(self.index)
        index['noduri']['5'] = index['noduri']['1']
        index['strazi']['b'][0]['segmente'] = [[5, 4]]
        self.assertEqual(junctions(index, self.boundary, self.roads, set())[0]['features'], [])

    def test_layer_conflict_and_coordinate_conflict_are_not_exported(self):
        roads = copy.deepcopy(self.roads)
        roads[1]['tags']['layer'] = '1'
        geo, rows, _ = junctions(self.index, self.boundary, roads, set())
        self.assertEqual(geo['features'], [])
        self.assertEqual(rows[0]['status'], 'index_only_or_conflicting_geometry')
        roads = copy.deepcopy(self.roads)
        roads[1]['geometry'][0]['lon'] = 27.595
        self.assertEqual(junctions(self.index, self.boundary, roads, set())[0]['features'], [])

    def test_crossing_node_not_duplicated_as_junction(self):
        geo, rows, _ = junctions(self.index, self.boundary, self.roads, {'osm-node-1'})
        self.assertEqual(geo['features'], [])
        self.assertEqual(rows[0]['coincident_crossing_id'], 'osm-node-1')

    def test_crossing_no_informal_and_alternative_signal_tag_are_distinct(self):
        extras = [dict(osm=f'node/{n}', lat=47.16, lon=27.59) for n in (1, 2, 3)]
        raw = dict(fetched_at='2026-10-17T12:00:00Z', response=dict(elements=[
            dict(type='node', id=1, lat=47.16, lon=27.59, tags=dict(highway='traffic_signals', crossing='no')),
            dict(type='node', id=2, lat=47.16, lon=27.59, tags=dict(crossing='informal')),
            dict(type='node', id=3, lat=47.16, lon=27.59, tags=dict(highway='traffic_signals', crossing='traffic_signals'))]))
        geo, rows, accepted = audit_extras(extras, raw, self.boundary)
        self.assertEqual([r['status'] for r in rows], ['excluded_explicit_crossing_no',
                          'excluded_informal_not_formal_crossing', 'alternative_tagging_review_required'])
        self.assertEqual(len(geo['features']), 1)
        self.assertEqual(accepted, [])

    def test_explicit_legacy_signalized_marked_crossing_is_supported_without_inventing_highway_tag(self):
        raw = dict(fetched_at='2026-10-17T12:00:00Z', response=dict(elements=[
            dict(type='node', id=1, lat=47.16, lon=27.59,
                 tags={'crossing': 'traffic_signals', 'crossing:markings': 'yes'}), *self.roads]))
        _, rows, accepted = audit_extras([dict(osm='node/1', lat=47.16, lon=27.59)], raw, self.boundary)
        self.assertEqual(rows[0]['status'], 'confirmed_legacy_signalized_crossing')
        self.assertNotIn('highway', accepted[0]['properties'])
        normalized, _ = normalize_additions(accepted, rows, [], [], '2026-10-17')
        self.assertIs(normalized['features'][0]['properties']['semafor'], True)
        self.assertIsNone(normalized['features'][0]['properties']['benzi'])
        self.assertIsNone(normalized['features'][0]['properties']['scoala_150m'])


if __name__ == '__main__':
    unittest.main()
