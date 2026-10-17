"""Offline worker tests with simulated transport, never represented as live AI."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from measures.chatgpt_exchange import ROOT, SOURCE, IDS, VERSION, prepare, strict_json
from measures.web_scraper import BrowserBlocked, exclusive, parse_response, run_worker
from measures.web_scraper import wait_for_composer


class WebScraperTests(unittest.TestCase):
    def test_manual_wait_only_observes_then_continues(self):
        page, record, editor = Mock(), Mock(), Mock()
        page.is_closed.return_value = False
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            with patch('measures.web_scraper.check_blocker', side_effect=[BrowserBlocked('challenge'), None]), \
                 patch('measures.web_scraper.composer', return_value=editor):
                self.assertIs(wait_for_composer(page, record, Path(tmp), manual_wait=60), editor)
            record.assert_called_once_with('waiting_for_user', url=page.url)
            page.wait_for_timeout.assert_called_once_with(1000)
            page.click.assert_not_called()
            page.get_by_role.assert_not_called()

    def test_manual_wait_disabled_or_headless_does_not_continue(self):
        with patch('measures.web_scraper.check_blocker', side_effect=BrowserBlocked('challenge')):
            with self.assertRaises(BrowserBlocked):
                wait_for_composer(Mock(), Mock(), Path('.'), manual_wait=0)
        with self.assertRaises(ValueError):
            run_worker(headless=True, manual_wait=60)

    def fixture(self):
        packet = prepare(strict_json(SOURCE))
        return json.dumps(dict(schema_version=VERSION, packet_id=packet['packet_id'], articles=[
            dict(article_id=i, relevant=False, reason='Synthetic transport fixture only.', suggestions=[]) for i in IDS]))

    def test_cache_hit_revalidates_without_browser(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            root, calls = Path(tmp), []
            def transport(message, record, directory, **kwargs):
                calls.append(message)
                self.assertIn('DATE_ARTICOLE', message)
                record('dispatch_started')
                record('waiting')
                return self.fixture(), 'https://chatgpt.com/c/test-fixture'
            first = run_worker(cache=root/'cache', output=root/'out', transport=transport)
            second = run_worker(cache=root/'cache', output=root/'out', transport=transport)
            self.assertEqual(len(calls), 1)
            self.assertFalse(first['cache_hit'])
            self.assertTrue(second['cache_hit'])
            self.assertEqual(second['approved_suggestions'], 0)
            self.assertEqual(second['provider'], 'chatgpt_browser_dom')

    def test_ambiguous_send_is_not_retried(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            root, calls = Path(tmp), []
            def transport(message, record, directory, **kwargs):
                calls.append(1)
                record('dispatch_started')
                raise BrowserBlocked('Simulated connection failure after click')
            for _ in range(2):
                with self.assertRaises(BrowserBlocked):
                    run_worker(cache=root/'cache', output=root/'out', transport=transport)
            self.assertEqual(calls, [1])
            self.assertFalse((root/'out/chatgpt_suggestions.json').exists())

    def test_invalid_response_is_saved_but_not_published(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            root = Path(tmp)
            def transport(message, record, directory, **kwargs):
                record('dispatch_started')
                return '{"articles": []}', 'https://chatgpt.com/'
            with self.assertRaises(ValueError):
                run_worker(cache=root/'cache', output=root/'out', transport=transport)
            self.assertFalse((root/'out/chatgpt_suggestions.json').exists())
            self.assertEqual(len(list((root/'cache').glob('*/response.txt'))), 1)

    def test_cache_tampering_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            root = Path(tmp)
            def transport(message, record, directory, **kwargs):
                return self.fixture(), 'https://chatgpt.com/c/test-fixture'
            run_worker(cache=root/'cache', output=root/'out', transport=transport)
            raw = next((root/'cache').glob('*/response.txt'))
            payload = json.loads(raw.read_text())
            payload['articles'][0]['reason'] = 'Changed fixture.'
            raw.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed'):
                run_worker(cache=root/'cache', output=root/'out', transport=transport)

    def test_lock_excludes_concurrent_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            lock = Path(tmp)/'worker.lock'
            with exclusive(lock):
                with self.assertRaises(BrowserBlocked):
                    with exclusive(lock):
                        self.fail('Lock must prevent entry')
            self.assertFalse(lock.exists())

    def test_parser_does_not_repair_or_ignore_trailing_prose(self):
        self.assertEqual(parse_response('```json\n{"ok": true}\n```'), {'ok': True})
        for bad in ('{"a":1,"a":2}', '{"a":NaN}', '{"ok":true} extra', 'prefix {"ok":true}'):
            with self.assertRaises(ValueError):
                parse_response(bad)


if __name__ == '__main__':
    unittest.main()
