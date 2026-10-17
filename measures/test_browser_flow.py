import json
from pathlib import Path
import tempfile
import unittest

from measures.browser_flow import ROOT, create_job, finish_job, load_job, mark_job
from measures.chatgpt_exchange import IDS, VERSION


class BrowserFlowTests(unittest.TestCase):
    def test_journal_prevents_duplicate_send_and_keeps_input_hashes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            folder = Path(tmp)/'job'
            create_job(folder)
            mark_job(folder, 'dispatch_started')
            with self.assertRaises(ValueError):
                mark_job(folder, 'dispatch_started')
            mark_job(folder, 'sent', 'test-conversation')
            self.assertEqual(load_job(folder)[1]['state'], 'sent')
            with self.assertRaises(ValueError):
                mark_job(folder, 'sent', 'test-conversation')
            (folder/'PROMPT.txt').write_text('tampered', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_job(folder)

    def test_finish_validates_before_writing_and_remains_unapproved(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            folder = Path(tmp)/'job'
            job = create_job(folder)
            mark_job(folder, 'dispatch_started')
            mark_job(folder, 'sent', 'test-conversation')
            response = Path(tmp)/'response.json'
            response.write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                finish_job(folder, response)
            self.assertFalse((folder/'chatgpt_suggestions.json').exists())
            # Synthetic transport fixture, not an actual browser/ChatGPT response.
            response.write_text(json.dumps(dict(schema_version=VERSION, packet_id=job['packet_id'], articles=[
                dict(article_id=i, relevant=False, reason='Fixture de test.', suggestions=[]) for i in IDS])), encoding='utf-8')
            result = finish_job(folder, response)
            self.assertEqual(result['approved_suggestions'], 0)
            self.assertEqual(load_job(folder)[1]['state'], 'validated')
            with self.assertRaises(ValueError):
                finish_job(folder, response)


if __name__ == '__main__':
    unittest.main()
