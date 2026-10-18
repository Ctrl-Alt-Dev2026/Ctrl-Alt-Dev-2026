"""The live endpoint upgrades old snapshots without changing their matched streets."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.live_router import register_live


class LiveStreetAnalysisTests(unittest.TestCase):
    def test_older_stored_payload_is_analyzed_without_recollection(self):
        d = json.loads((Path(__file__).resolve().parents[1] / 'isu/seed/dataset.json').read_text(encoding='utf-8'))
        for key in ('street_analysis', 'accidents_h3'):
            d.pop(key, None)
        for f in d['streets']['features']:
            f['properties'].pop('analiza', None)
            f['properties'].pop('context_osm', None)
        coarse = next(e for e in d['accidents'] if e['precizie_loc'] == 'strada')
        coarse.update(lat=47.156, lon=27.588)  # representative geocoder point, not accident evidence
        original = deepcopy(d)
        app = register_live(FastAPI())
        latest = dict(id=7, built_at=d['built_at'], payload=json.dumps(d))
        with patch('api.live_router.store.connect'), patch('api.live_router.store.latest_dataset', return_value=latest), TestClient(app) as client:
            response = client.get('/api/v1/live/dataset')
            repeated = client.get('/api/v1/live/dataset')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, repeated.content)
        self.assertIn('street-analysis-v1', response.headers['etag'])
        result = response.json()
        self.assertEqual(result['built_at'], original['built_at'])
        self.assertEqual(result['accidents_h3']['features'], [])
        self.assertIsNone(next(e for e in result['accidents'] if e['event_id'] == coarse['event_id'])['lat'])
        self.assertEqual([f['geometry'] for f in result['streets']['features']],
                         [f['geometry'] for f in original['streets']['features']])
        self.assertEqual(d, original)


if __name__ == '__main__':
    unittest.main()
