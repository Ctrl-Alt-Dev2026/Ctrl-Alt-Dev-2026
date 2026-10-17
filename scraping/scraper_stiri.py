"""python -m scraping.scraper_stiri --help; colectează listări și textele știrilor."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sqlite3
import time
import unicodedata
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOTS = {"bzi": "https://www.bzi.ro", "zdi": "https://www.ziaruldeiasi.ro"}
LISTS = {"bzi": "/local-s14", "zdi": "/stiri/local"}
ARTICLE = {"bzi": re.compile(r"/[^/]+-\d{6,9}/?$"),
           "zdi": re.compile(r"/stiri/[^/]+--\d+\.html$")}
UA = "SafeIasiResearch/1.0"
PREFILTER = re.compile(r"accident|pieton|trecer|calcat|lovit|mortal|\bmort\w*|deced|deces|ucis|omorat|murit|"
                       r"acros|spulber|izbit|ranit|travers|coliziun|impact|tampon|victim|prioritat")
MONTHS = {"ian": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "iun": 6,
          "iul": 7, "aug": 8, "sep": 9, "oct": 10, "noi": 11, "nov": 11, "dec": 12}


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.lower())
                   if unicodedata.category(c) != "Mn").replace("ţ", "t").replace("ş", "s")


def normalize(url, base):
    p = urlsplit(urljoin(base, url))
    if p.scheme not in ("http", "https") or p.username or p.password:
        return None
    host = p.hostname or ""
    root_host = urlsplit(base).hostname or ""
    if host.removeprefix("www.") != root_host.removeprefix("www."):
        return None
    return urlunsplit(("https", root_host, p.path or "/", p.query, ""))


def article_url(url, source):
    clean = normalize(url, ROOTS[source])
    if clean and ARTICLE[source].fullmatch(urlsplit(clean).path):
        return clean.split("?")[0]
    return None


def parse_date(value):
    """Publication day only; never invent an event time."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        pass
    value = fold(value)
    numeric = re.search(r"\b(\d{2})\.(\d{2})\.(20\d{2})\b", value)
    if numeric:
        try:
            return date(int(numeric[3]), int(numeric[2]), int(numeric[1])).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+([a-z]+)\.?\s+(20\d{2})\b", value)
    if m:
        day, month, year = m.groups()
        try:
            return date(int(year), MONTHS[month[:3]], int(day)).isoformat()
        except (KeyError, ValueError):
            pass
    return None


def json_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from json_nodes(child)


def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    structured = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            structured.extend(json_nodes(json.loads(tag.string or tag.get_text())))
        except (ValueError, TypeError):
            continue
    story = next((n for n in structured if any(t in (n.get("@type") if isinstance(n.get("@type"), list)
                           else [n.get("@type")]) for t in ("NewsArticle", "Article", "ReportageNewsArticle"))), {})
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else story.get("headline", "")
    meta = soup.select_one('meta[property="article:published_time"]')
    published = parse_date(meta.get("content", "") if meta else "") or parse_date(story.get("datePublished", ""))
    if not published:
        tag = soup.find("time")
        published = parse_date((tag.get("datetime") or tag.get_text(" ", strip=True)) if tag else "")
    section = soup.select_one('meta[property="article:section"]')
    section = section.get("content") if section else story.get("articleSection")
    for tag in soup.select("script, style, nav, footer, aside, form, .related-posts, .comments, #comments, .article-card__container, .sidebar-block__item-content"):
        tag.decompose()
    body = soup.select_one('.pa__content-main')
    if body is None:
        body = soup.select_one('[itemprop="articleBody"], .entry-content, .article-content, .td-post-content')
    if body is None:
        body = soup.find("article")
    method = "html" if body else "missing"
    if body:
        paragraphs = [p.get_text(" ", strip=True) for p in body.select("p, h2, h3")]
        text = "\n".join(dict.fromkeys(p for p in paragraphs if p and p != "Lasă un răspuns Anulează răspunsul"))
    else:
        text = ""
    if len(story.get("articleBody", "")) > len(text):
        text = BeautifulSoup(story["articleBody"], "html.parser").get_text(" ", strip=True)
        method = "jsonld"
    # Limit fallback date search to the article header, never the entire page.
    if not published and h1:
        header = h1.parent
        published = parse_date(header.get_text(" ", strip=True)[:1000])
    return {"titlu": title, "data_publicarii": published, "sectiune": section,
            "text": text, "metoda_extragere": method}


def classify(article, start, end):
    """Conservative evidence hints, never a legal conclusion or automatic approval."""
    text = article["titlu"] + "\n" + article["text"]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    def evidence(pattern):
        return [s for s in sentences if re.search(pattern, fold(s))]
    pedestrian = evidence(r"\bpieton\w*\b|\btravers\w*\b")
    collision = evidence(r"accident|acros|lovit|izbit|spulber|ranit|deced|deces|murit|calcat|\bmort\w*|ucis")
    crossing = evidence(r"trecer\w* (?:pentru |de )?pieton|marcaj\w* pietonal")
    injury = evidence(r"ranit|ranita|ranire|leziun|traumatis|transportat\w* la spital|ajuns la spital|deced|murit|ucis")
    negative = evidence(r"fara (?:victime|raniti)|nu (?:au fost|exista) (?:victime|raniti)")
    priority = evidence(r"nu (?:a|ar fi) acordat prioritate|neacord\w* (?:de )?prioritat|nu (?:a|ar fi) dat prioritate")
    red = evidence(r"(?:culoarea|semafor\w*) ros\w*|travers\w* neregulamentar")
    city = evidence(r"(?:municipiul|orasul) iasi")
    county = evidence(r"judetul iasi")
    event_dates = []
    for s in evidence(r"accident|impact|acros|lovit|spulber"):
        # Keep all explicit dates for human review; do not treat publication as event date.
        for m in re.finditer(r"\b\d{1,2}\s+[a-zăâîșşțţ]+\.?\s+20\d{2}\b", s, re.I):
            d = parse_date(m.group())
            if d:
                event_dates.append({"data": d, "fragment": s})
    unique = sorted({d["data"] for d in event_dates})
    event_day = unique[0] if len(unique) == 1 else None
    in_range = start <= event_day <= end if event_day else None
    published = article["data_publicarii"]
    pub_range = start <= published <= end if published else None
    return {"candidat": bool(pedestrian and collision),
            "municipiul_iasi": True if city else None,
            "mentiune_judet_iasi": bool(county),
            "pieton_ranit": True if injury and pedestrian and not negative else (False if negative and not injury else None),
            "mentiune_trecere": True if crossing else None,
            "neacordare_prioritate": True if priority and pedestrian and not red else None,
            "data_accidentului": event_day, "accident_in_interval": in_range,
            "publicare_in_interval": pub_range,
            "necesita_verificare": True, "incident_id": None,
            "dovezi": {"pieton": pedestrian, "impact": collision, "ranire": injury,
                       "trecere": crossing, "prioritate": priority, "contradictii": red + negative,
                       "municipiu": city, "judet": county, "date_posibile": event_dates}}


def database(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
      url TEXT PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
      next_try REAL NOT NULL DEFAULT 0, error TEXT, payload TEXT, depth INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS origins (url TEXT, origin TEXT, PRIMARY KEY(url,origin));
    CREATE TABLE IF NOT EXISTS hosts (source TEXT PRIMARY KEY, next_request REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS hints (url TEXT PRIMARY KEY, title TEXT, summary TEXT, published TEXT);
    """)
    return db


def enqueue(db, url, source, kind, origin, depth=0):
    db.execute("INSERT OR IGNORE INTO tasks(url,source,kind,depth) VALUES(?,?,?,?)", (url, source, kind, depth))
    db.execute("INSERT OR IGNORE INTO origins VALUES(?,?)", (url, origin))
    if kind == "listing":
        db.execute("UPDATE tasks SET status='pending' WHERE url=? AND status='paused_listing'", (url,))


def prefilter(db, url, title="", summary="", published=None, exhaustive=False):
    previous = db.execute("SELECT * FROM hints WHERE url=?", (url,)).fetchone()
    if previous:
        title = title if len(title) > len(previous["title"] or "") else previous["title"] or ""
        summary = summary if len(summary) > len(previous["summary"] or "") else previous["summary"] or ""
        published = published or previous["published"]
    db.execute("INSERT OR REPLACE INTO hints VALUES(?,?,?,?)", (url, title, summary, published))
    match = exhaustive or bool(PREFILTER.search(fold(title + " " + summary + " " + urlsplit(url).path.replace("-", " "))))
    db.execute("UPDATE tasks SET status=? WHERE url=? AND status IN ('pending','filtered')",
               ("pending" if match else "filtered", url))
    return match


class Deferred(Exception):
    def __init__(self, message, seconds=60):
        super().__init__(message)
        self.seconds = seconds


class Fetcher:
    def __init__(self, db, directory, delay, user_agent):
        self.db, self.directory, self.delay = db, directory, delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.agent = user_agent
        self.robots = {}

    def request(self, url, source, delay=None):
        row = self.db.execute("SELECT next_request FROM hosts WHERE source=?", (source,)).fetchone()
        wait = (row[0] if row else 0) - time.time()
        if wait > 60:
            raise Deferred("Domeniu în pauză", wait)
        if wait > 0:
            time.sleep(wait)
        # Do not follow an unchecked redirect to another host or a disallowed URL.
        try:
            response = self.session.get(url, timeout=(10, 35), allow_redirects=False)
        finally:
            self.db.execute("INSERT OR REPLACE INTO hosts VALUES(?,?)", (source, time.time() + max(self.delay, delay or 0)))
            self.db.commit()
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "")
            try:
                seconds = float(retry)
            except ValueError:
                try:
                    seconds = parsedate_to_datetime(retry).timestamp() - time.time()
                except (ValueError, TypeError, OverflowError):
                    seconds = 300
            seconds = max(60, seconds)
            self.db.execute("INSERT OR REPLACE INTO hosts VALUES(?,?)", (source, time.time() + seconds))
            self.db.commit()
            raise Deferred("HTTP 429", seconds)
        if response.status_code == 403:
            self.db.execute("INSERT OR REPLACE INTO hosts VALUES(?,?)", (source, time.time() + 3600))
            self.db.commit()
            raise Deferred("HTTP 403; domeniu amânat", 3600)
        if 300 <= response.status_code < 400:
            raise Deferred("Redirect necesită verificare: " + response.headers.get("Location", ""), 3600)
        response.raise_for_status()
        return response

    def get(self, url, source):
        if source not in self.robots:
            response = self.request(ROOTS[source] + "/robots.txt", source)
            if "<html" in response.text[:500].lower():
                raise Deferred("robots.txt nu este text valid", 3600)
            rp = RobotFileParser()
            rp.parse(response.text.splitlines())
            self.robots[source] = rp
        rp = self.robots[source]
        if not rp.can_fetch(self.agent, url):
            raise PermissionError("robots.txt interzice URL-ul")
        cache = self.directory / (hashlib.sha256(url.encode()).hexdigest() + ".body")
        if cache.exists():
            return cache.read_text(encoding="utf-8")
        response = self.request(url, source, rp.crawl_delay(self.agent))
        if url.endswith(".gz"):
            raw = response.content
            content = (gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw).decode("utf-8")
        else:
            response.encoding = response.apparent_encoding or "utf-8"
            content = response.text
        if re.search(r"<title[^>]*>\s*(?:Just a moment|Access denied|Attention Required)", content, re.I):
            raise Deferred("Pagină de verificare, nu conținut editorial", 3600)
        cache.write_text(content, encoding="utf-8")
        return content


def discover(db, row, content, max_depth, exhaustive=False, start=None, known_urls=None, refresh_cache=None):
    source, url, kind, depth = row["source"], row["url"], row["kind"], row["depth"]
    if kind == "sitemap":
        root = ET.fromstring(content)
        if root.tag.split("}")[-1] not in ("sitemapindex", "urlset"):
            raise ValueError("Răspunsul nu este sitemap XML")
        is_index = root.tag.split("}")[-1] == "sitemapindex"
        for child in root:
            loc = next((n.text for n in child if n.tag.split("}")[-1] == "loc"), None)
            target = normalize(loc, ROOTS[source]) if loc else None
            if not target:
                continue
            article = article_url(target, source)
            if article:
                enqueue(db, article, source, "article", url)
                prefilter(db, article, exhaustive=exhaustive)
            elif is_index and depth < max_depth:
                enqueue(db, target, source, "sitemap", url, depth + 1)
        return
    soup = BeautifulSoup(content, "html.parser")
    cards = soup.select('.arcive__articles .article') if source == "bzi" else soup.select('.cat__content .article-card__container')
    # Restrict candidates to editorial listing cards when the known layout is available.
    card_dates = []
    card_urls = set()
    if cards:
        for card in cards:
            summary = card.get_text(" ", strip=True)
            published = parse_date(summary)
            card_dates.append(published)
            for a in card.select('a[href]'):
                article = article_url(a['href'], source)
                if article:
                    card_urls.add(article)
                    enqueue(db, article, source, "article", url)
                    prefilter(db, article, a.get_text(" ", strip=True), summary, published, exhaustive)
    for tag in soup.select("nav, footer, aside, .related-posts, .comments"):
        # Pagination may live inside nav, so process it separately below.
        if tag.name != "nav":
            tag.decompose()
    pagination = []
    for a in soup.select("a[href]"):
        target = normalize(a["href"], ROOTS[source])
        if not target:
            continue
        article = article_url(target, source)
        if article:
            if not cards:
                enqueue(db, article, source, "article", url)
                prefilter(db, article, a.get_text(" ", strip=True), exhaustive=exhaustive)
        elif depth < max_depth and ("next" in a.get("rel", []) or
                ((a.find_parent(class_=re.compile(r"pagin|page-numbers")) or
                  any(re.search(r"pagin|page-numbers", c) for c in a.get("class", []))) and
                 re.search(r"/page/\d+|[?&](?:page|paged)=\d+", target))):
            pagination.append(target)
    # Follow only the next numeric page, never the archive's "last page" jump.
    def page_number(value):
        match = re.search(r"/page/(\d+)|[?&](?:page|paged)=(\d+)", value)
        return int(next(v for v in match.groups() if v)) if match else 1
    next_pages = [p for p in pagination if page_number(p) == page_number(url) + 1]
    old = bool(card_dates) and all(d is not None and d < start for d in card_dates) if start else False
    if old:
        print("LIMITĂ INTERVAL: toate cardurile datate sunt anterioare", start, url, flush=True)
    elif known_urls is not None and cards and card_urls and card_urls <= known_urls:
        print("NOUTATI: pagina cu articole deja cunoscute; opresc extinderea", url, flush=True)
    elif next_pages:
        enqueue(db, next_pages[0], source, "listing", url, depth + 1)
        if known_urls is not None:
            db.execute("UPDATE tasks SET status='pending' WHERE url=? AND status='done'", (next_pages[0],))
            if refresh_cache is not None:
                (refresh_cache / (hashlib.sha256(next_pages[0].encode()).hexdigest() + ".body")).unlink(missing_ok=True)
    if cards:
        count = db.execute("SELECT count(*) FROM origins JOIN tasks USING(url) WHERE origin=? AND kind='article' AND status IN ('pending','done')", (url,)).fetchone()[0]
        print(f"LISTARE: {len(cards)} carduri, {count} articole selectate", flush=True)


def export(db, directory, start, end):
    with (directory / "inventar_urluri.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["url", "sursa", "stare", "incercari", "eroare", "titlu_listare", "rezumat_listare", "data_listare"])
        writer.writerows(tuple(row) for row in db.execute(
            "SELECT tasks.url,source,status,attempts,error,title,summary,published FROM tasks LEFT JOIN hints USING(url) WHERE kind='article' ORDER BY source,tasks.url"))
    fields = ["url", "sursa", "titlu", "data_publicarii", "sectiune", "text", "metoda_extragere",
              "candidat", "municipiul_iasi", "mentiune_judet_iasi", "pieton_ranit", "mentiune_trecere",
              "neacordare_prioritate", "data_accidentului", "accident_in_interval", "publicare_in_interval",
              "necesita_verificare", "incident_id", "dovezi", "descoperit_din"]
    with (directory / "articole.jsonl").open("w", encoding="utf-8") as all_file, \
         (directory / "candidati.csv").open("w", encoding="utf-8-sig", newline="") as candidates:
        writer = csv.DictWriter(candidates, fieldnames=fields)
        writer.writeheader()
        for row in db.execute("SELECT * FROM tasks WHERE kind='article' AND status='done' ORDER BY url"):
            article = json.loads(row["payload"])
            result = {"url": row["url"], "sursa": row["source"], **article, **classify(article, start, end),
                      "descoperit_din": [r[0] for r in db.execute("SELECT origin FROM origins WHERE url=? ORDER BY origin", (row["url"],))]}
            all_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            # Unknown event dates remain candidates; old court stories are explicitly flagged.
            if result["candidat"] and result["publicare_in_interval"] is not False:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in result.items()})
    report = {"inceput": start, "sfarsit": end, "generat_utc": datetime.now(timezone.utc).isoformat(),
              "avertisment": "Eșantion de presă, acoperire necunoscută; candidați nevalidați, nu accidente confirmate.",
              "stari": [dict(r) for r in db.execute("SELECT source,kind,status,count(*) AS numar FROM tasks GROUP BY source,kind,status")],
              "probleme": [dict(r) for r in db.execute("SELECT url,kind,status,attempts,error,next_try FROM tasks WHERE error IS NOT NULL")],
              "in_asteptare": db.execute("SELECT count(*) FROM tasks WHERE status='pending'").fetchone()[0]}
    (directory / "raport.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--de-la", default="2026-01-01", type=date.fromisoformat)
    ap.add_argument("--pana-la", default=date.today().isoformat(), type=date.fromisoformat)
    ap.add_argument("--surse", nargs="+", choices=ROOTS, default=list(ROOTS))
    ap.add_argument("--director", type=Path, default=Path("scraping/data"))
    ap.add_argument("--pauza", type=float, default=5)
    ap.add_argument("--max-taskuri", type=int, default=200, help="buget per rulare; reluarea păstrează coada")
    ap.add_argument("--faza", choices=("toate", "descoperire", "articole"), default="toate")
    ap.add_argument("--exhaustiv", action="store_true", help="descarcă și articolele fără cuvinte-cheie")
    ap.add_argument("--sitemap", action="store_true", help="include sitemap-uri; implicit se parcurge doar arhiva Local")
    ap.add_argument("--adancime-max", type=int, default=1000)
    ap.add_argument("--urluri", type=Path, help="fișier cu URL-uri de articole/listări/sitemap-uri, unul pe linie")
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--noutati", action="store_true", help="reîncarcă listările recente până la o pagină cu URL-uri deja cunoscute; păstrează articolele descărcate")
    ap.add_argument("--reincearca", action="store_true", help="rearmează erorile/URL-urile blocate; păstrează pauza domeniului")
    ap.add_argument("--actualizeaza", action="store_true", help="reverifică taskurile terminate și golește cache-ul lor; păstrează coada și proveniența")
    ap.add_argument("--user-agent", default=UA, help="identificare și, preferabil, contact real")
    args = ap.parse_args(argv)
    if args.de_la > args.pana_la or args.pauza < 1 or args.max_taskuri < 1 or args.adancime_max < 0:
        ap.error("Interval/buget invalid; pauza minimă este 1 secundă")
    args.director.mkdir(parents=True, exist_ok=True)
    cache = args.director / "cache"
    cache.mkdir(exist_ok=True)
    db = database(args.director / "colectare.sqlite3")
    start, end = args.de_la.isoformat(), args.pana_la.isoformat()
    if not args.export_only:
        known_urls = {row[0] for row in db.execute("SELECT url FROM tasks WHERE kind='article'")} if args.noutati else None
        if args.noutati:
            # Only news refresh pauses the historical frontier. Ordinary resume
            # must retain pending listings even when no HTML cache was transferred.
            db.execute("UPDATE tasks SET status='paused_listing' WHERE kind='listing' AND status='pending'")
        for row in ([] if args.noutati else db.execute("SELECT * FROM tasks WHERE kind='listing' AND status='done'").fetchall()):
            cached = cache / (hashlib.sha256(row["url"].encode()).hexdigest() + ".body")
            if cached.exists():
                discover(db, row, cached.read_text(encoding='utf-8'), args.adancime_max, args.exhaustiv, start)
        for row in db.execute("SELECT url FROM tasks WHERE kind='article' AND status IN ('pending','filtered')").fetchall():
            prefilter(db, row['url'], exhaustive=args.exhaustiv)
        for source in args.surse:
            seed = ROOTS[source] + LISTS[source]
            enqueue(db, seed, source, "listing", "config")
            if args.noutati:
                db.execute("UPDATE tasks SET status='pending' WHERE url=? AND status='done'", (seed,))
                (cache / (hashlib.sha256(seed.encode()).hexdigest() + ".body")).unlink(missing_ok=True)
        if args.urluri:
            for raw in args.urluri.read_text(encoding="utf-8-sig").splitlines():
                raw = raw.strip()
                if not raw or raw.startswith("#"):
                    continue
                matched = False
                for source in args.surse:
                    url = normalize(raw, ROOTS[source]) if raw.startswith(("https://", "http://")) else None
                    if url:
                        matched = True
                        article = article_url(url, source)
                        kind = "article" if article else ("sitemap" if re.search(r"\.xml(?:\.gz)?(?:\?|$)", url) else "listing")
                        enqueue(db, article or url, source, kind, str(args.urluri))
                        # Explicitly supplied article URLs override the title prefilter.
                        if article:
                            db.execute("UPDATE tasks SET status='pending' WHERE url=? AND status='filtered'", (article,))
                if not matched:
                    print("URL ignorat (domeniu neacceptat):", raw)
        if args.reincearca:
            db.execute("UPDATE tasks SET status='pending',attempts=0,next_try=0 WHERE status IN ('error','blocked')")
        if args.actualizeaza:
            for row in db.execute("SELECT url FROM tasks WHERE status='done'"):
                (cache / (hashlib.sha256(row[0].encode()).hexdigest() + ".body")).unlink(missing_ok=True)
            db.execute("UPDATE tasks SET status='pending',attempts=0,next_try=0 WHERE status='done'")
        db.commit()
        fetcher = Fetcher(db, cache, args.pauza, args.user_agent)
        # A task is done only AFTER successful parsing; a crash leaves it eligible again.
        try:
            for iteration in range(args.max_taskuri):
                placeholders = ",".join("?" for _ in args.surse)
                kinds = {"toate": "1=1", "descoperire": "kind IN ('listing','sitemap')",
                         "articole": "kind='article'"}[args.faza]
                if not args.sitemap:
                    kinds += " AND kind!='sitemap'"
                preferred = ("listing", "article", "article")[iteration % 3]
                row = db.execute(f"""SELECT tasks.* FROM tasks LEFT JOIN hosts USING(source)
                  WHERE status='pending' AND next_try<=? AND source IN ({placeholders})
                  AND ({kinds}) AND coalesce(next_request,0)<=?
                  ORDER BY CASE WHEN kind=? THEN 0 ELSE 1 END, depth, tasks.rowid LIMIT 1""",
                  (time.time(), *args.surse, time.time() + 60, preferred)).fetchone()
                if row is None:
                    print("Nu mai sunt taskuri eligibile acum; verifică raport.json pentru pauze și erori.")
                    break
                payload = None
                try:
                    content = fetcher.get(row["url"], row["source"])
                    # Sitemaps declared by robots.txt, not guessed endpoints.
                    for sitemap in (fetcher.robots[row["source"]].site_maps() or []) if args.sitemap else []:
                        target = normalize(sitemap, ROOTS[row["source"]])
                        if target:
                            enqueue(db, target, row["source"], "sitemap", ROOTS[row["source"]] + "/robots.txt")
                    payload = None
                    if row["kind"] == "article":
                        article = extract(content)
                        if not article["titlu"] or not article["text"]:
                            raise ValueError("Titlu/corp editorial lipsă; necesită verificarea selectorilor")
                        payload = json.dumps(article, ensure_ascii=False)
                        result = classify(article, start, end)
                        print("CANDIDAT" if result['candidat'] else "NERELEVANT DUPĂ TEXT", article['titlu'], flush=True)
                    else:
                        discover(db, row, content, args.adancime_max, args.exhaustiv, start,
                                 known_urls, cache if args.noutati else None)
                    db.execute("UPDATE tasks SET status='done',payload=?,error=NULL WHERE url=?", (payload, row["url"]))
                    print("OK", row["kind"], row["url"], flush=True)
                except PermissionError as exc:
                    db.execute("UPDATE tasks SET status='blocked',error=? WHERE url=?", (str(exc), row["url"]))
                except (requests.RequestException, Deferred, ValueError, ET.ParseError, OSError) as exc:
                    attempts = row["attempts"] + 1
                    seconds = max(getattr(exc, "seconds", 0), min(3600, 30 * 2 ** min(attempts, 7)))
                    db.execute("UPDATE tasks SET status=?, attempts=?, next_try=?, error=? WHERE url=?",
                               ("error" if attempts >= 5 else "pending", attempts, time.time() + seconds, str(exc), row["url"]))
                    print("AMÂNAT", row["url"], str(exc), flush=True)
                db.commit()
                if iteration % 10 == 0 or (row['kind'] == 'article' and payload is not None):
                    export(db, args.director, start, end)
        except KeyboardInterrupt:
            db.rollback()
            print("Oprit; coada salvată poate fi reluată.")
    export(db, args.director, start, end)
    db.close()
    print("Export:", args.director.resolve())


if __name__ == "__main__":
    main()
