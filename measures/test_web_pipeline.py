"""Synthetic offline transports only; no browser or external messages in these tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from measures.chatgpt_exchange import ROOT, VERSION as EXCHANGE_VERSION, chat_message, prepare
from measures.storage import atomic_json, digest
from measures.web_pipeline import BrowserBlocked, packet_for, run_pipeline


def article(number):
    return dict(article_id=f'fixture-{number}', sursa='test-public-source',
        url=f'https://example.org/{number}', titlu=f'Offline fixture {number}',
        text='Un pieton a fost lovit de o mașină pe trecere.', publicat_la='2026-01-01', colectat_la='old')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT/'measures/output')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.cache, self.output = self.root/'source.json', self.root/'cache', self.root/'out'
        self.calls = []

    def write(self, articles):
        atomic_json(self.source, articles)

    def transport(self, message, record, directory, **kwargs):
        articles = json.loads((directory/'articles.json').read_text(encoding='utf-8'))
        packet = packet_for(articles)
        self.calls.append([a['article_id'] for a in articles])
        record('dispatch_started')
        record('waiting')
        return self.reply(packet), 'https://chatgpt.com/c/offline-fixture'

    def reply(self, packet):
        return json.dumps(dict(schema_version=EXCHANGE_VERSION, packet_id=packet['packet_id'], articles=[
            dict(article_id=a['article']['article_id'], relevant=True, reason='Synthetic offline fixture.',
                suggestions=[dict(title='Verificare în teren', rationale='Propunere sintetică de test.',
                    evidence=[dict(passage_id=0, quote=a['passages'][0]['text'][:40])],
                    checks=['Verificare umană.'])]) for a in packet['articles']]), ensure_ascii=False)

    def run_pipeline(self, **kwargs):
        return run_pipeline(source=self.source, cache=self.cache, output=self.output,
                            transport=kwargs.pop('transport', self.transport), **kwargs)

    def test_all_then_only_new_or_changed_not_reordered_or_collection_time(self):
        articles = [article(i) for i in range(5)]
        self.write(articles)
        first = self.run_pipeline(batch_size=2)
        self.assertEqual(first['counts']['new_processed'], 5)
        self.assertEqual(len(self.calls), 3)
        reordered = list(reversed(deepcopy(articles)))
        for a in reordered:
            a['colectat_la'] = 'new collection timestamp'
        self.write(reordered)
        second = self.run_pipeline(batch_size=3)
        self.assertEqual(second['counts']['cached'], 5)
        self.assertEqual(len(self.calls), 3)
        reordered.append(article(5))
        self.write(reordered)
        self.assertEqual(self.run_pipeline()['counts']['new_processed'], 1)
        self.assertEqual(self.calls[-1], ['fixture-5'])
        reordered[0]['text'] += ' O actualizare a articolului.'
        self.write(reordered)
        changed = self.run_pipeline()
        self.assertEqual(changed['counts']['new_processed'], 1)
        self.assertEqual(changed['counts']['cached'], 5)
        self.assertEqual(self.calls[-1], [reordered[0]['article_id']])

    def test_interrupted_batch_keeps_prior_results_and_no_automatic_resend(self):
        self.write([article(i) for i in range(5)])
        def flaky(message, record, directory, **kwargs):
            if self.calls:
                self.calls.append(['failed'])
                record('dispatch_started')
                raise BrowserBlocked('Uncertain send')
            return self.transport(message, record, directory, **kwargs)
        first = self.run_pipeline(batch_size=2, transport=flaky)
        self.assertEqual(first['state'], 'stopped')
        self.assertEqual(first['counts']['validated'], 2)
        self.assertEqual(first['counts']['blocked'], 2)
        self.assertEqual(first['counts']['pending'], 1)
        second = self.run_pipeline()
        self.assertEqual(second['counts']['cached'], 2)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(second['rows']), 2)

    def test_limit_and_restart_continue_without_resending_successes(self):
        self.write([article(i) for i in range(5)])
        first = self.run_pipeline(limit=2)
        self.assertEqual(first['state'], 'partial')
        self.assertEqual(first['counts']['pending'], 3)
        second = self.run_pipeline(batch_size=2)
        self.assertEqual(second['state'], 'complete')
        self.assertEqual(second['counts']['new_processed'], 3)
        self.assertEqual(second['counts']['cached'], 2)
        flattened = [i for batch in self.calls for i in batch]
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_plan_never_calls_browser_or_claims_articles(self):
        self.write([article(i) for i in range(4)])
        result = self.run_pipeline(plan=True)
        self.assertEqual(result['state'], 'planned')
        self.assertEqual(result['counts']['pending'], 4)
        self.assertFalse(self.calls)
        self.assertFalse((self.cache/'index.json').exists())
        self.assertFalse((self.output/'chatgpt_suggestions.json').exists())

    def test_removed_article_disappears_from_export_but_reappears_from_cache(self):
        articles = [article(i) for i in range(2)]
        self.write(articles)
        self.run_pipeline()
        self.write(articles[:1])
        self.assertEqual(len(self.run_pipeline()['rows']), 1)
        self.write(articles)
        self.assertEqual(self.run_pipeline()['counts']['cached'], 2)
        self.assertEqual(len(self.calls), 1)

    def test_duplicate_ids_stop_before_network(self):
        self.write([article(1), article(1)])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.run_pipeline()
        self.assertFalse(self.calls)

    def test_corrupt_cache_never_becomes_a_miss(self):
        self.write([article(1)])
        self.run_pipeline()
        next((self.cache/'jobs').glob('*/response.txt')).write_text('{}', encoding='utf-8')
        result = self.run_pipeline()
        self.assertEqual(result['state'], 'stopped')
        self.assertEqual(result['counts']['blocked'], 1)
        self.assertEqual(len(self.calls), 1)

    def test_oversize_and_invalid_articles_are_explicit_never_truncated(self):
        large = article(1)
        large['text'] *= 2000
        invalid = article(2)
        invalid['text'] = None
        self.write([large, invalid, article(3)])
        result = self.run_pipeline(max_chars=8000)
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(result['counts']['invalid'], 2)
        self.assertEqual(self.calls, [['fixture-3']])

    def test_adopt_old_pilot_cache_then_process_only_remaining_articles(self):
        articles = [article(i) for i in range(4)]
        self.write(articles)
        packet = prepare(articles, ids=[a['article_id'] for a in articles[:3]])
        raw = self.reply(packet)
        pilot = self.root/'old-pilot'/'job'
        pilot.mkdir(parents=True)
        atomic_json(pilot/'articles_packet.json', packet)
        (pilot/'message.txt').write_text(chat_message(packet), encoding='utf-8')
        (pilot/'response.txt').write_text(raw, encoding='utf-8')
        atomic_json(pilot/'job.json', dict(version='measures-web-scraper-1', state='validated',
            url='https://chatgpt.com/c/old-offline-pilot', response_sha256=digest(json.loads(raw)), history=[]))
        first = self.run_pipeline(seed_pilot_cache=pilot.parent)
        self.assertEqual(first['counts']['cached'], 3)
        self.assertEqual(first['counts']['new_processed'], 1)
        self.assertEqual(self.calls, [['fixture-3']])
        # The original source snapshot stays available after unrelated new input arrives.
        self.write(articles+[article(4)])
        second = self.run_pipeline(seed_pilot_cache=pilot.parent)
        self.assertEqual(second['counts']['cached'], 4)
        self.assertEqual(self.calls[-1], ['fixture-4'])

    def test_failed_validation_preserves_raw_but_does_not_publish_rows(self):
        self.write([article(1)])
        def bad(message, record, directory, **kwargs):
            record('dispatch_started')
            return '{}', 'https://chatgpt.com/c/bad-fixture'
        result = self.run_pipeline(transport=bad)
        self.assertEqual(result['state'], 'stopped')
        self.assertFalse(result['rows'])
        self.assertEqual(len(list((self.cache/'jobs').glob('*/response.txt'))), 1)


if __name__ == '__main__':
    unittest.main()
