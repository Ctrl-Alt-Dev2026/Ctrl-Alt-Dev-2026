import copy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from measures.chatgpt_exchange import (IDS, ROOT, SOURCE, VERSION, import_response,
                                      prepare, prompt, response_schema, strict_json, chat_message)


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.articles = strict_json(SOURCE)
        self.packet = prepare(self.articles)
        # Hand-authored TEST fixture, not a response obtained from ChatGPT.
        self.response = dict(schema_version=VERSION, packet_id=self.packet['packet_id'], articles=[
            dict(article_id=i, relevant=False, reason='Fixture de test fără propuneri.', suggestions=[]) for i in IDS])
        passage = self.packet['articles'][1]['passages'][0]
        self.response['articles'][1].update(relevant=True, reason='Incident pietonal relatat.', suggestions=[
            dict(title='Exemplu pentru test: verificare locală', rationale='Ipoteză pentru verificare, fără decizie de lucrare.',
                 evidence=[dict(passage_id=0, quote=passage['text'])], checks=['Verificarea configurației în teren'])])

    def test_package_covers_three_original_articles_and_exact_offsets(self):
        self.assertEqual([r['article']['article_id'] for r in self.packet['articles']], IDS)
        for row in self.packet['articles']:
            for p in row['passages']:
                self.assertEqual(row['article']['text'][p['start']:p['end']], p['text'])
        self.assertIn(self.packet['packet_id'], prompt(self.packet))
        self.assertEqual(response_schema(self.packet)['properties']['packet_id']['const'], self.packet['packet_id'])
        message = chat_message(self.packet)
        self.assertIn('fără fișiere', message)
        self.assertIn('DATE_ARTICOLE', message)
        for identifier in IDS:
            self.assertIn(identifier, message)

    def test_valid_import_no_network_no_approval_no_invented_cost(self):
        before = copy.deepcopy(self.articles)
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            result = import_response(self.packet, self.response, self.articles)
        self.assertEqual(self.articles, before)
        self.assertEqual(result['approved_suggestions'], 0)
        self.assertFalse(result['generation_origin_independently_verified'])
        item = result['rows'][1]['suggestions'][0]
        self.assertIsNone(item['cost_ron'])
        self.assertIsNone(item['reduction'])
        self.assertIsNone(item['location_id'])
        quote = item['evidence'][0]
        text = self.packet['articles'][1]['article']['text']
        self.assertEqual(text[quote['start']:quote['end']], quote['quote'])

    def test_wrong_packet_missing_and_duplicate_articles_rejected(self):
        for mutate in (lambda r: r.update(packet_id='other'),
                       lambda r: r['articles'].pop(),
                       lambda r: r['articles'][0].update(article_id=IDS[1]),
                       lambda r: r['articles'][0].update(article_id='unknown')):
            response = copy.deepcopy(self.response)
            mutate(response)
            with self.assertRaises(ValueError):
                import_response(self.packet, response, self.articles)

    def test_fabricated_cross_article_and_invalid_quote_reference_rejected(self):
        for replacement in (dict(passage_id=0, quote='Acesta este un citat complet inventat.'),
                            dict(passage_id=999, quote='Acesta este un citat complet inventat.'),
                            dict(passage_id=True, quote='Acesta este un citat complet inventat.'),
                            dict(passage_id=0, quote=self.packet['articles'][2]['passages'][0]['text'])):
            response = copy.deepcopy(self.response)
            response['articles'][1]['suggestions'][0]['evidence'][0] = replacement
            with self.assertRaises(ValueError):
                import_response(self.packet, response, self.articles)

    def test_modified_packet_or_source_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet['articles'][1]['passages'][0]['text'] = 'Modificat'
        with self.assertRaises(ValueError):
            import_response(packet, self.response, self.articles)
        source = copy.deepcopy(self.articles)
        source[0]['text'] += ' Update.'
        with self.assertRaises(ValueError):
            import_response(self.packet, self.response, source)

    def test_prices_percentages_extra_fields_and_bad_types_rejected(self):
        for mutate in (
                lambda r: r['articles'][1]['suggestions'][0].update(cost=100),
                lambda r: r['articles'][1]['suggestions'][0].update(rationale='Costul este 100 lei'),
                lambda r: r['articles'][1]['suggestions'][0].update(rationale='Efect estimat 30%'),
                lambda r: r['articles'][1].update(relevant='true'),
                lambda r: r['articles'][1].update(relevant=False)):
            response = copy.deepcopy(self.response)
            mutate(response)
            with self.assertRaises(ValueError):
                import_response(self.packet, response, self.articles)

    def test_strict_json_duplicate_keys_nonfinite_and_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'response.json'
            for data in ('{"a":1,"a":2}', '{"value":NaN}', '```json\n{}\n```'):
                path.write_text(data, encoding='utf-8')
                with self.assertRaises(ValueError):
                    strict_json(path)
            path.write_text('{"ok":true}', encoding='utf-8-sig')
            self.assertEqual(strict_json(path), {'ok': True})

    def test_cli_import_writes_only_valid_results_and_preserves_input(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'measures/output') as tmp:
            folder = Path(tmp)
            packet, response = folder/'packet.json', folder/'response.json'
            packet.write_text(json.dumps(self.packet, ensure_ascii=False), encoding='utf-8')
            response.write_text(json.dumps(self.response, ensure_ascii=False), encoding='utf-8')
            before = SOURCE.read_bytes()
            command = [sys.executable, '-m', 'measures.chatgpt_exchange', 'import',
                       '--packet', str(packet), '--response', str(response)]
            result = subprocess.run(command+['--output', str(folder/'accepted')], cwd=ROOT,
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(strict_json(folder/'accepted/chatgpt_suggestions.json')['approved_suggestions'], 0)
            self.response['packet_id'] = 'wrong'
            response.write_text(json.dumps(self.response), encoding='utf-8')
            result = subprocess.run(command+['--output', str(folder/'rejected')], cwd=ROOT,
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((folder/'rejected').exists())
            self.assertEqual(SOURCE.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
