import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.patterns.corpus import build_corpus, digest
from ai.patterns.engine import discover, cosine
from ai.patterns.export import export
from ai.patterns.service import DEFAULT_DATA, MODULE, PatternService


class PatternTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=PatternService().load()

    def test_reports_do_not_inflate_unique_events(self):
        self.assertEqual(17,len(self.bundle['events']))
        self.assertEqual(3,self.bundle['coverage']['events_with_article_text'])
        event=next(e for e in self.bundle['events'] if e['id']=='ev-003')
        self.assertEqual(2,len(event['articles']))
        group=next(p for p in discover(self.bundle)['patterns'] if 'ev-003' in p['member_ids'])
        self.assertEqual(1,group['member_ids'].count('ev-003'))
        self.assertEqual(2,group['article_event_count'])
        self.assertEqual(3,group['article_count'])

    def test_unknown_lighting_is_not_absent(self):
        event=next(e for e in self.bundle['events'] if e['id']=='ev-001')
        self.assertIsNone(next(f for f in event['facts'] if f['field']=='iluminat')['value'])
        self.assertNotIn('unlit',event['facets'])
        self.assertNotIn('lit',event['facets'])

    def test_only_explicit_crossing_associations(self):
        event=next(e for e in self.bundle['events'] if e['id']=='ev-014')
        self.assertIsNone(event['site_id'])
        self.assertNotIn('school',event['facets'])
        self.assertNotIn('unsignalized',event['facets'])

    def test_matched_excerpts_really_exist(self):
        matched=0
        for event in self.bundle['events']:
            for fact in event['facts']:
                for article_id in fact['matched_article_ids']:
                    article=next(a for a in event['articles'] if a['id']==article_id)
                    self.assertIn(fact['excerpt'],article['text'])
                    self.assertEqual('article_excerpt',fact['provenance'])
                    matched+=1
        self.assertEqual(2,matched)

    def test_profiles_exclude_geography_outcome_and_unknowns(self):
        for event in self.bundle['events']:
            profile=event['profile']
            for word in ('Podu','Păcurari','Nicolina','Tătărași','Copou','deces','traumatisme','necunoscut','2025','ev-'):
                self.assertNotIn(word,profile)
        self.assertEqual(14,self.bundle['coverage']['fixture_only_events'])

    def test_source_mode_abstains_and_excludes_unmatched_facts(self):
        result=discover(self.bundle,scope='sources')
        self.assertEqual([],result['patterns'])
        self.assertEqual(['ev-001','ev-003'],result['eligible_ids'])
        self.assertIn('Insufficient source evidence',result['note'])
        for e in self.bundle['events']:
            self.assertTrue(all(f.startswith('cause:') for f in e['source_facets']))

    def test_observed_sources_and_source_overwrites_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'must not be written'):
            export(DEFAULT_DATA/'accidents.json')
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'data';shutil.copytree(DEFAULT_DATA,directory)
            path=directory/'articles.json';articles=json.loads(path.read_text(encoding='utf-8'))
            articles[0]['sursa']='OBSERVED'
            path.write_text(json.dumps(articles),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'SINTETIC'):
                build_corpus(directory)

    def test_discovery_requires_pairwise_support_and_multiple_sites(self):
        result=discover(self.bundle)
        self.assertEqual(2,len(result['patterns']))
        for p in result['patterns']:
            self.assertGreaterEqual(len(p['member_ids']),3)
            self.assertGreaterEqual(p['site_count'],2)
            self.assertGreaterEqual(p['min_similarity'],result['threshold'])
            self.assertTrue(all(f['count']<=f['total'] for f in p['facets']))
            self.assertNotIn('ev-017',p['member_ids'])

    def test_exclusion_recomputes_support_without_writing_data(self):
        before=digest(DEFAULT_DATA)
        initial=discover(self.bundle)['patterns'][0]
        result=discover(self.bundle,excluded=['ev-001'])
        for p in result['patterns']:
            self.assertNotIn('ev-001',p['member_ids'])
        current=next(p for p in result['patterns'] if 'ev-003' in p['member_ids'])
        self.assertEqual(4,len(initial['member_ids']))
        self.assertEqual(3,len(current['member_ids']))
        self.assertEqual(1,current['article_event_count'])
        self.assertEqual(before,digest(DEFAULT_DATA))
        self.assertEqual(initial,discover(self.bundle)['patterns'][0])

    def test_no_forced_pattern_at_high_threshold_or_sparse_data(self):
        self.assertEqual([],discover(self.bundle,threshold=.95)['patterns'])
        excluded=[e['id'] for e in self.bundle['events'] if e['id'] not in ['ev-001','ev-003']]
        self.assertEqual([],discover(self.bundle,excluded=excluded)['patterns'])

    def test_invalid_controls_and_corrupt_vectors_are_rejected(self):
        for args in ({'scope':'unknown'},{'threshold':.99},{'excluded':['not-an-event']}):
            with self.assertRaises(ValueError):discover(self.bundle,**args)
        self.assertEqual(0,cosine([0,0],[1,0]))
        broken=copy.deepcopy(self.bundle);broken['vectors']['ev-001'][0]=float('nan')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'broken.json';path.write_text(json.dumps(broken),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Invalid vector'):
                PatternService(path).load()

    def test_malformed_vector_types_are_data_errors(self):
        for value in ('not-a-number', True, None):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                broken=copy.deepcopy(self.bundle)
                broken['vectors']['ev-001'][0]=value
                path=Path(tmp)/'broken.json';path.write_text(json.dumps(broken),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'Invalid vector'):
                    PatternService(path).load()

    def test_source_changes_invalidate_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'data';shutil.copytree(DEFAULT_DATA,directory)
            with (directory/'articles.json').open('a',encoding='utf-8') as stream:stream.write(' ')
            with self.assertRaisesRegex(ValueError,'Stale'):
                PatternService(data_directory=directory).load()

    def test_offline_export_has_no_remote_scripts_or_required_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'demo.html';export(output)
            html=output.read_text(encoding='utf-8')
            self.assertNotIn('@@',html)
            self.assertNotIn('<script src=',html)
            self.assertNotIn('fetch(',html)
            self.assertIn('multilingual_sentence_embeddings',html)


class RoutesTests(unittest.TestCase):
    def test_health_and_schema_do_not_load_vectors_or_models(self):
        from api.main import create_app
        from fastapi.testclient import TestClient
        with patch('ai.patterns.router.service.load',side_effect=AssertionError('startup must not load pattern data')):
            with TestClient(create_app()) as client:
                self.assertEqual(200,client.get('/health').status_code)
                schema=client.get('/openapi.json')
                self.assertEqual(200,schema.status_code)
                self.assertIn('/api/v1/ai/patterns/discover',schema.json()['paths'])

    def test_current_and_legacy_entry_points_share_factory_and_register_once(self):
        from api.main import app, create_app
        from ai.app import app as ai_app
        from ai.patterns.app import app as pattern_app, create_app as pattern_factory
        from ai.patterns.router import register_patterns
        from fastapi.testclient import TestClient
        self.assertIs(app, ai_app)
        self.assertIs(app, pattern_app)
        self.assertIs(create_app, pattern_factory)
        with tempfile.TemporaryDirectory() as tmp:
            application=pattern_factory(review_directory=Path(tmp)/'custom-review')
            self.assertEqual((Path(tmp)/'custom-review').resolve(),application.state.review_directory)
            schema=application.openapi();count=len(application.routes)
            register_patterns(application);register_patterns(application)
            self.assertEqual(count,len(application.routes))
            self.assertEqual(schema,application.openapi())
            self.assertIn('/api/v1/ai/patterns/discover',schema['paths'])
            self.assertIn('/api/v1/imports',schema['paths'])
            self.assertIn('/api/v1/ai/extract',schema['paths'])
            with TestClient(application) as client:
                self.assertEqual(200,client.get('/patterns').status_code)

    def test_pattern_analysis_does_not_change_persisted_review(self):
        from api.main import create_app
        from fastapi.testclient import TestClient
        article=json.loads((DEFAULT_DATA/'articles.json').read_text(encoding='utf-8'))[0]
        with tempfile.TemporaryDirectory() as tmp:
            application=create_app(review_directory=Path(tmp)/'review')
            with TestClient(application,base_url='http://127.0.0.1',client=('127.0.0.1',50002)) as client:
                imported=client.post('/api/v1/imports',json={'article':article,'pipeline':'rules',
                    'data_mode':'synthetic','request_id':'pattern-integration','operator':'test-operator'})
                self.assertEqual(201,imported.status_code,imported.text)
                candidate_id=imported.json()['import']['candidate_ids'][0]
                before=client.get(f'/api/v1/candidates/{candidate_id}').json()
                stored=(Path(tmp)/'review'/'synthetic.json').read_bytes()
                self.assertEqual(200,client.post('/api/v1/ai/patterns/discover',json={'excluded':['ev-001']}).status_code)
                self.assertEqual(200,client.get('/patterns').status_code)
                self.assertEqual(before,client.get(f'/api/v1/candidates/{candidate_id}').json())
                self.assertEqual(stored,(Path(tmp)/'review'/'synthetic.json').read_bytes())
                self.assertEqual([],client.get('/api/v1/reviewed-events').json()['events'])

    def test_existing_backend_extraction_and_snapshot_rules_are_preserved(self):
        from fastapi.testclient import TestClient
        from ai.patterns.app import create_app
        # Serving uses prepared vectors only, without importing sentence-transformers.
        with TestClient(create_app()) as client:
            self.assertEqual(200,client.get('/health').status_code)
            self.assertEqual(503,client.get('/api/v1/events').status_code)
            self.assertEqual('invalid_snapshot',client.get('/api/v1/events').json()['detail']['code'])
            self.assertEqual(200,client.get('/api/v1/ai/replays/syn-001').status_code)
            self.assertEqual(200,client.get('/patterns').status_code)
            self.assertEqual(200,client.get('/api/v1/ai/patterns/corpus').status_code)
            response=client.post('/api/v1/ai/patterns/discover',json={'excluded':['ev-001']})
            self.assertEqual(200,response.status_code)
            self.assertNotIn('ev-001',response.json()['eligible_ids'])
            self.assertEqual(422,client.post('/api/v1/ai/patterns/discover',json={'scope':'causal'}).status_code)
            self.assertEqual(422,client.post('/api/v1/ai/patterns/discover',json={'excluded':['absent']}).status_code)
            self.assertEqual(422,client.post('/api/v1/ai/patterns/discover',json={'threshold':1}).status_code)
            self.assertEqual(422,client.post('/api/v1/ai/patterns/discover',json={'publish':True}).status_code)

    def test_missing_or_stale_bundle_returns_explicit_503(self):
        from fastapi.testclient import TestClient
        from ai.patterns.app import create_app
        with patch('ai.patterns.router.service',PatternService('missing-bundle.json')):
            with TestClient(create_app()) as client:
                self.assertEqual(503,client.get('/patterns').status_code)
                self.assertEqual(503,client.get('/api/v1/ai/patterns/corpus').status_code)
                self.assertEqual(503,client.post('/api/v1/ai/patterns/discover',json={}).status_code)

    def test_stale_html_cannot_be_served_as_the_current_demo(self):
        from fastapi.testclient import TestClient
        from api.main import create_app
        bundle=PatternService().load()
        html=(MODULE/'static'/'index.html').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'stale.html'
            path.write_text(html.replace(bundle['model']['revision'],'stale-revision'),encoding='utf-8')
            with patch('ai.patterns.router.DEMO_PATH',path),TestClient(create_app()) as client:
                response=client.get('/patterns')
                self.assertEqual(503,response.status_code)
                self.assertIn('Stale',response.json()['detail']['message'])
                self.assertEqual(200,client.get('/api/v1/ai/patterns/corpus').status_code)

    def test_corrupt_bundle_returns_503_on_all_pattern_routes(self):
        from fastapi.testclient import TestClient
        from api.main import create_app
        bundle=PatternService().load();bundle['vectors']['ev-001'][0]='corrupt'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'broken.json';path.write_text(json.dumps(bundle),encoding='utf-8')
            with patch('ai.patterns.router.service',PatternService(path)),TestClient(create_app()) as client:
                self.assertEqual(503,client.get('/patterns').status_code)
                self.assertEqual(503,client.get('/api/v1/ai/patterns/corpus').status_code)
                self.assertEqual(503,client.post('/api/v1/ai/patterns/discover',json={}).status_code)


if __name__=='__main__':unittest.main()
