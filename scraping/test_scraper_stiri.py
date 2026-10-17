import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from scraping.scraper_stiri import (Deferred, Fetcher, article_url, classify, database,
                           discover, enqueue, export, extract, main, normalize, parse_date, prefilter)


class ScraperStiriTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.db = database(self.directory / "test.sqlite3")
        self.addCleanup(self.db.close)

    def test_urls(self):
        self.assertEqual(article_url("/accident-5489167?utm_source=x#foo", "bzi"),
                         "https://www.bzi.ro/accident-5489167")
        self.assertIsNone(normalize("https://evil.example/x", "https://www.bzi.ro"))
        self.assertIsNone(normalize("https://www.bzi.ro.evil.example/x", "https://www.bzi.ro"))

    def test_dates(self):
        self.assertEqual(parse_date("10 mart. 2026, 11:35"), "2026-03-10")
        self.assertEqual(parse_date("2026-10-17T23:35:00+03:00"), "2026-10-17")
        self.assertIsNone(parse_date("31 feb. 2026"))

    def test_jsonld_before_script_removal_and_short_paragraphs(self):
        result = extract('''<h1>Copil lovit</h1><script type="application/ld+json">
        {"@graph":[{"@type":"NewsArticle","datePublished":"2026-03-10T11:35:00+02:00"}]}
        </script><article><p>Iași.</p><p>Rănit.</p><p>Strada X.</p></article>''')
        self.assertEqual(result["data_publicarii"], "2026-03-10")
        self.assertIn("Strada X.", result["text"])

    def test_no_full_page_fallback(self):
        result = extract("<h1>Știre</h1><aside><p>Pieton rănit</p></aside><p>Recomandări</p>")
        self.assertEqual(result["text"], "")

    def test_zdi_editorial_container_not_recommendation_article(self):
        result = extract('''<h1>Știre</h1><article class="article-card__container"><p>Recomandare</p></article>
        <div class="pa__content-main"><div class="pa__excerpt"><p>Introducere.</p></div>
        <div class="zdi-wysiwyg"><p>Corpul știrii.</p></div></div>''')
        self.assertIn("Corpul știrii.", result["text"])
        self.assertNotIn("Recomandare", result["text"])

    def test_cli_queue_selection_and_resume_without_network(self):
        from urllib.robotparser import RobotFileParser
        rp = RobotFileParser()
        rp.parse(["User-agent: *", "Allow: /"])
        def fake_get(fetcher, url, source):
            fetcher.robots[source] = rp
            return '<main><a href="/stire-5489167">Titlu neutru</a></main>'
        with patch.object(Fetcher, "get", fake_get):
            main(["--director", str(self.directory / "cli"), "--surse", "bzi", "--max-taskuri", "1"])
        c = database(self.directory / "cli" / "colectare.sqlite3")
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT status FROM tasks WHERE kind='listing'").fetchone()[0], "done")
        self.assertEqual(c.execute("SELECT status FROM tasks WHERE kind='article'").fetchone()[0], "filtered")

    def test_prefilter_summary_and_reactivation(self):
        url = 'https://www.bzi.ro/titlu-neutru-5489167'
        enqueue(self.db, url, 'bzi', 'article', 'test')
        self.assertFalse(prefilter(self.db, url, 'Titlu neutru'))
        self.assertEqual(self.db.execute('SELECT status FROM tasks').fetchone()[0], 'filtered')
        self.assertTrue(prefilter(self.db, url, summary='Un copil a fost călcat pe trecere.'))
        self.assertEqual(self.db.execute('SELECT status FROM tasks').fetchone()[0], 'pending')

    def test_news_mode_stops_at_known_cards(self):
        url = 'https://www.bzi.ro/local-s14'
        article = 'https://www.bzi.ro/accident-5489167'
        enqueue(self.db, url, 'bzi', 'listing', 'test')
        row = self.db.execute('SELECT * FROM tasks').fetchone()
        html = '''<div class="arcive__articles"><div class="article">
        <a href="/accident-5489167">Accident</a></div></div>
        <a rel="next" href="/local-s14/page/2">2</a>'''
        discover(self.db, row, html, 100, known_urls={article})
        self.assertEqual(self.db.execute("SELECT count(*) FROM tasks WHERE url LIKE '%/page/2'").fetchone()[0], 0)

    def test_resume_from_database_without_html_cache(self):
        from urllib.robotparser import RobotFileParser
        directory = self.directory / "resume"
        directory.mkdir()
        db = database(directory / "colectare.sqlite3")
        seed = "https://www.bzi.ro/local-s14"
        frontier = seed + "/page/179"
        enqueue(db, seed, "bzi", "listing", "config")
        enqueue(db, frontier, "bzi", "listing", seed, 178)
        db.execute("UPDATE tasks SET status='done' WHERE url=?", (seed,))
        db.commit()
        db.close()
        visited = []
        rp = RobotFileParser()
        rp.parse(["User-agent: *", "Allow: /"])
        def fake_get(fetcher, url, source):
            visited.append(url)
            fetcher.robots[source] = rp
            return "<main>Pagina de listare fără alte rezultate.</main>"
        with patch.object(Fetcher, "get", fake_get):
            main(["--director", str(directory), "--surse", "bzi", "--max-taskuri", "1"])
        self.assertEqual(visited, [frontier])

    def test_news_mode_refreshes_next_page_but_keeps_article_payload(self):
        url = 'https://www.bzi.ro/local-s14'
        next_url = url + '/page/2'
        enqueue(self.db, url, 'bzi', 'listing', 'test')
        row = self.db.execute('SELECT * FROM tasks WHERE url=?', (url,)).fetchone()
        enqueue(self.db, next_url, 'bzi', 'listing', 'test')
        self.db.execute("UPDATE tasks SET status='done' WHERE url=?", (next_url,))
        html = '''<div class="arcive__articles"><div class="article">
        <a href="/accident-5489167">Accident</a></div></div>
        <a rel="next" href="/local-s14/page/2">2</a>'''
        discover(self.db, row, html, 100, known_urls=set(), refresh_cache=self.directory)
        self.assertEqual(self.db.execute("SELECT status FROM tasks WHERE url=?", (next_url,)).fetchone()[0], 'pending')

    def test_cards_filter_and_sequential_pagination(self):
        url = 'https://www.bzi.ro/local-s14'
        enqueue(self.db, url, 'bzi', 'listing', 'test')
        row = self.db.execute('SELECT * FROM tasks').fetchone()
        discover(self.db, row, '''<div class="arcive__articles">
        <div class="article"><h3><a href="/titlu-neutru-5489167">Ce s-a întâmplat</a></h3><p>Pieton lovit de mașină.</p></div>
        <div class="article"><a href="/politica-5489168">Politică</a></div></div>
        <a class="page-numbers" href="/local-s14/page/2">2</a>
        <a class="page-numbers" href="/local-s14/page/900">900</a>''', 100)
        self.assertEqual(self.db.execute("SELECT status FROM tasks WHERE url LIKE '%5489167'").fetchone()[0], 'pending')
        self.assertEqual(self.db.execute("SELECT status FROM tasks WHERE url LIKE '%5489168'").fetchone()[0], 'filtered')
        self.assertEqual(self.db.execute("SELECT count(*) FROM tasks WHERE url LIKE '%900'").fetchone()[0], 0)

    def test_interval_stops_only_with_all_card_dates_known(self):
        enqueue(self.db, 'https://www.bzi.ro/local-s14', 'bzi', 'listing', 'test')
        row = self.db.execute('SELECT * FROM tasks').fetchone()
        html = '''<div class="arcive__articles"><div class="article">31 dec. 2025
        <a href="/accident-5489167">Accident</a></div></div>
        <a rel="next" href="/local-s14/page/2">Next</a>'''
        discover(self.db, row, html, 100, start='2026-01-01')
        self.assertEqual(self.db.execute("SELECT count(*) FROM tasks WHERE url LIKE '%/page/2'").fetchone()[0], 0)

    def test_listing_collects_without_title_keywords_and_next(self):
        enqueue(self.db, "https://www.bzi.ro/local-s14", "bzi", "listing", "test")
        row = self.db.execute("SELECT * FROM tasks").fetchone()
        discover(self.db, row, '''<main><a href="/titlu-neutru-5489167">Ce s-a întâmplat</a>
        <a class="page-numbers" href="/local-s14/page/2">2</a></main>
        <aside><a href="/recomandare-5489168">Accident</a></aside>''', 10)
        self.assertEqual(self.db.execute("SELECT count(*) FROM tasks").fetchone()[0], 3)

    def test_sitemap_namespace_and_duplicate_origins(self):
        enqueue(self.db, "https://www.bzi.ro/map.xml", "bzi", "sitemap", "test")
        row = self.db.execute("SELECT * FROM tasks").fetchone()
        discover(self.db, row, '''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://www.bzi.ro/stire-5489167</loc></url></urlset>''', 10)
        enqueue(self.db, "https://www.bzi.ro/stire-5489167", "bzi", "article", "second")
        self.assertEqual(self.db.execute("SELECT count(*) FROM tasks WHERE kind='article'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM origins WHERE url LIKE '%5489167'").fetchone()[0], 2)

    def test_red_light_is_not_priority_confirmation(self):
        article = {"titlu": "Pieton lovit", "text": "Pieton rănit pe trecerea de pietoni în municipiul Iași. Traversase pe culoarea roșie.", "data_publicarii": "2026-03-10"}
        result = classify(article, "2026-01-01", "2026-10-17")
        self.assertTrue(result["candidat"])
        self.assertTrue(result["pieton_ranit"])
        self.assertIsNone(result["neacordare_prioritate"])
        self.assertIsNone(result["data_accidentului"])
        self.assertTrue(result["dovezi"]["contradictii"])

    def test_court_story_old_event_and_unknown_city(self):
        article = {"titlu": "Pieton lovit", "text": "Accidentul a avut loc la 12 octombrie 2022 în județul Iași.", "data_publicarii": "2026-07-15"}
        result = classify(article, "2026-01-01", "2026-10-17")
        self.assertFalse(result["accident_in_interval"])
        self.assertTrue(result["publicare_in_interval"])
        self.assertIsNone(result["municipiul_iasi"])

    def test_429_persists_cooldown(self):
        fetcher = Fetcher(self.db, self.directory, 1, "Test/1")
        response = Mock(status_code=429, headers={"Retry-After": "120"})
        fetcher.session.get = Mock(return_value=response)
        with patch("scraping.scraper_stiri.time.time", return_value=1000):
            with self.assertRaises(Deferred):
                fetcher.request("https://www.bzi.ro/a", "bzi")
        self.assertEqual(self.db.execute("SELECT next_request FROM hosts").fetchone()[0], 1120)

    def test_robots_failure_never_fetches_article(self):
        fetcher = Fetcher(self.db, self.directory, 1, "Test/1")
        fetcher.request = Mock(side_effect=requests.ConnectionError("offline"))
        with self.assertRaises(requests.ConnectionError):
            fetcher.get("https://www.bzi.ro/stire-5489167", "bzi")
        self.assertEqual(fetcher.request.call_count, 1)
        self.assertEqual(fetcher.robots, {})

    def test_export_keeps_unknown_dates_and_failed_tasks(self):
        url = "https://www.bzi.ro/stire-5489167"
        enqueue(self.db, url, "bzi", "article", "manual")
        article = {"titlu": "Pieton lovit", "text": "Un pieton a fost lovit.", "data_publicarii": None,
                   "sectiune": None, "metoda_extragere": "html"}
        self.db.execute("UPDATE tasks SET status='done',payload=? WHERE url=?", (json.dumps(article), url))
        enqueue(self.db, "https://www.bzi.ro/local-s14", "bzi", "listing", "test")
        self.db.execute("UPDATE tasks SET attempts=1,error='timeout' WHERE kind='listing'")
        export(self.db, self.directory, "2026-01-01", "2026-10-17")
        self.assertIn(url, (self.directory / "candidati.csv").read_text(encoding="utf-8-sig"))
        report = json.loads((self.directory / "raport.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["probleme"]), 1)


if __name__ == "__main__":
    unittest.main()
