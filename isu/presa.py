"""Press articles (BZI, Ziarul de Iași) -> events, kept apart from ISU.

Main input: the team's Gemini extraction (`ai/gemini_pipeline`, the run behind
POST /api/v1/ai/extract {"mode": "gemini_csv", "cache_only": true}). It selects current reports of
pedestrians hit and extracts them; its saved responses (ai/cache_presa) cover the committed sample
scraping/articole_extrase_accident_clean.csv, so no key or network is needed and every event says it is a replay.
Articles the live scraper finds later are not in that cache: with SAFEIASI_GEMINI_LIVE=1 and a key
(GEMINI_API_KEY or ai/gemini.local.json) they are sent to Gemini one by one and cached in runtime/gemini;
otherwise a strict provisional rule pass reads them, keeps only pedestrians, and labels them as rules.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path

from . import config
from .parse import STREET, TIME, _clean_place, _sentence, participants, severity

ARTICLES_CSV = config.REPO / "scraping" / "articole_extrase_accident_clean.csv"
SOURCE_NAMES = {"bzi": "BZI", "zdi": "Ziarul de Iași"}
GEMINI_WORK = config.REPO / "runtime" / "gemini"
GEMINI_LIVE = os.environ.get("SAFEIASI_GEMINI_LIVE", "0") == "1"
AI_REPLAY = "Gemini, răspuns salvat (reluare)"
AI_LIVE = "Gemini"
RULES = "reguli provizorii"

INCIDENT = re.compile(r"accident|lovit|acro[șs]at|spulberat|c[ăa]lcat|carambol|tampon|izbit|r[ăa]sturnat|"
                      r"intrat (?:cu ma[șs]ina )?(?:în|într-un)|proiectat\w*", re.I)
NOT_INCIDENT = re.compile(r"poli[țt]i[șs]tii|ac[țt]iun|control|verifica[țt]i|razie|amenz|dosar|condamnat|instan[țt]|"
                          r"judec|proces|tribunal|arestat|recurs|despăgubir|aventura|cazul|după (?:două|trei|\d+) (?:luni|ani)|"
                          r"statistic|bilan[țt]|campanie|feroviar|tren\b", re.I)
# Neighbourhoods/landmarks the press uses instead of a street; the geocoder knows them as zones (no point).
ZONE = re.compile(r"\b(Podu Ro[șs]|T[ăa]t[ăa]ra[șs]i|Nicolina|P[ăa]curari|Copou|Dacia|Galata|Alexandru cel Bun|Canta|"
                  r"Bucium|Frumoasa|Moara de V[âa]nt|CUG|Mircea cel B[ăa]tr[âa]n|Gara|T[âa]rgu Cucu|Bularga|Baza 3|"
                  r"Splai Bahlui|Socola|Tudor Vladimirescu)\b")
CITY = re.compile(r"municipiul Ia[șs]i|din Ia[șs]i|în Ia[șs]i|ie[șs]ean", re.I)
CAUSES = [  # reported by the press, never our verdict (Planificare §4)
    ("neacordare_prioritate", r"(?:nu a|neacordar\w*|fără să) (?:acorda\w*|oferit|dat)\w* prioritate|nu a acordat prioritate"),
    ("traversare_neregulamentara", r"travers\w* (?:neregulamentar|prin loc nepermis)|prin loc nepermis"),
    ("viteza", r"vitez[ăa] (?:excesiv|neadaptat|mare)|a pierdut controlul"),
    ("vizibilitate", r"vizibilitate (?:redus|sc[ăa]zut)|cea[țt][ăa] dens|orbit"),
]


def _cause(text: str) -> tuple[str | None, str | None]:
    for name, pattern in CAUSES:
        m = re.search(pattern, text, re.I)
        if m:
            return name, _sentence(text, m.start(), m.end())
    return None, None


def _location(title: str, lede: str) -> tuple[str | None, str | None]:
    for source in (title, lede):
        for m in STREET.finditer(source):
            phrase = re.sub(r"\s*\b(?:FOTO|VIDEO)\b.*$", "", _clean_place(m.group(0))).strip(" /|–-")
            # "trecerea de pietoni" alone names no place: a capitalised name must follow the street word.
            if len(phrase.split()) >= 2 and re.search(r"\s[A-ZĂÂÎȘȚ0-9]", phrase):
                return phrase, _sentence(source, m.start(), m.end())
    for source in (title, lede):
        m = ZONE.search(source)
        if m:
            return f"zona {m.group(1)}", _sentence(source, m.start(), m.end())
    return None, None


def _rows(paths: list[Path]) -> list[dict]:
    """Scraper exports (same columns as candidati.csv); a later file wins for the same URL."""
    by_url = {}
    for path in paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                by_url[row.get("url") or row.get("﻿url")] = row
    return list(by_url.values())


def from_articles(paths: list[Path]) -> list[dict]:
    """Provisional rule pass over the scraped articles. Returns one dict per kept article."""
    rows = _rows(paths)
    events = []
    for r in rows:
        title, text = r["titlu"] or "", r["text"] or ""
        lede = re.sub(r"\s+", " ", text[:1500])
        if not INCIDENT.search(title) or NOT_INCIDENT.search(title) or NOT_INCIDENT.search(lede[:250]):
            continue
        if r.get("accident_in_interval") == "False":
            continue  # the scraper found an accident date outside the period: a follow-up or court story
        loc, loc_ev = _location(title, lede)
        in_city = bool(CITY.search(title) or CITY.search(lede[:600]))
        gravity, gravity_ev, _ = severity(title, lede)
        cause, cause_ev = _cause(lede)
        hour, hour_ev = None, None
        m = TIME.search(lede[:700])
        if m and int(m.group(1)) < 24:
            hour, hour_ev = f"{int(m.group(1)):02d}:{m.group(2)}", _sentence(lede, m.start(), m.end())
        dovezi = {k: v for k, v in {"loc_text": loc_ev, "gravitate": gravity_ev, "cauza_raportata": cause_ev,
                                    "ora": hour_ev}.items() if v}
        events.append({
            "article_id": _article_id(r),
            "sursa": SOURCE_NAMES.get(r["sursa"], r["sursa"]),
            "url": r["﻿url"] if "﻿url" in r else r["url"],
            "titlu": title,
            "text": text,
            "publicat_la": r["data_publicarii"] or None,
            "data_eveniment": r["data_accidentului"] or None,
            "ora": hour,
            "loc_text": (f"{loc}, municipiul Iași" if loc and in_city else loc),
            "strada": loc if loc and not loc.startswith("zona ") else None,
            "municipiu": in_city,
            "participanti": participants(lede),
            "gravitate": gravity,
            "cauza_raportata": cause,
            "dovezi": dovezi,
        })
    return events


def _article_id(row: dict) -> str:
    url = row.get("url") or row.get("﻿url") or ""
    slug = re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").rsplit("/", 1)[-1].lower())[:48].strip("-")
    return f"{row['sursa']}-{slug}"


def _url(row: dict) -> str:
    return row.get("url") or row.get("﻿url") or ""


def _gemini(source: Path, output: Path, cache_only: bool) -> dict:
    from ai.gemini_pipeline import run_gemini_csv
    try:
        return run_gemini_csv(source=source, output=output, cache_only=cache_only)
    except Exception as exc:  # a missing key, a quota error or a changed CSV: the rules take over
        return {"status": "error", "errors": [str(exc)], "articole_valide": [], "api_calls": 0}


def _from_ai(article: dict, cand: dict, label: str) -> dict:
    """One Gemini candidate in the shape from_articles returns, so grouping and geocoding stay shared."""
    loc = cand["loc_text"]
    title, lede = article["titlu"] or "", re.sub(r"\s+", " ", (article["text"] or "")[:1500])
    street, _ = _location(loc, "") if loc else (None, None)
    in_city = bool(CITY.search(loc or "") or CITY.search(title) or CITY.search(lede[:600]))
    return {
        "article_id": _article_id(article),
        "sursa": SOURCE_NAMES.get(article["sursa"], article["sursa"]),
        "url": article["url"],
        "titlu": title,
        "text": article["text"],
        "publicat_la": article["publicat_la"] or None,
        "data_eveniment": cand["data_eveniment"],
        "ora": cand["ora"],
        "loc_text": loc,
        # Verbatim quote for the reader; the geocoder gets the street plus the city when the article names it.
        "geo_text": f"{street}, municipiul Iași" if street and in_city else loc,
        "strada": street if street and not street.startswith("zona ") else None,
        "municipiu": in_city,
        "participanti": sorted({"motocicleta" if p == "motociclist" else p for p in cand["participanti"]}),
        "gravitate": cand["gravitate"],
        "cauza_raportata": cand["cauza_raportata"],
        "noapte": cand["noapte"],
        "dovezi": {k: v for k, v in (cand.get("dovezi") or {}).items() if v},
        "extractie": label,
    }


def from_gemini(paths: list[Path]) -> tuple[list[dict], set[str], dict]:
    """Gemini verdicts for the articles it has seen. Returns (kept articles as from_articles dicts,
    URLs Gemini judged, whatever its verdict, summary for the manifest)."""
    GEMINI_WORK.mkdir(parents=True, exist_ok=True)
    runs: list[tuple[dict, str]] = []
    if ARTICLES_CSV.exists():
        # The cache key hashes the prompt: a Windows checkout (autocrlf) turns the LF inside the quoted article
        # texts into CRLF and misses every batch. The committed file is LF, so restore it before hashing.
        sample = GEMINI_WORK / "esantion.csv"
        sample.write_bytes(ARTICLES_CSV.read_bytes().replace(b"\r\n", b"\n"))
        runs.append((_gemini(sample, GEMINI_WORK / "esantion", cache_only=True), AI_REPLAY))
    seen = {_url(r) for r in _rows([ARTICLES_CSV])}
    for row in _rows([p for p in paths if p != ARTICLES_CSV]):
        if _url(row) in seen:
            continue
        # One article per run: its prompt (and cache key) stays the same whatever else gets scraped.
        folder = GEMINI_WORK / "nou" / hashlib.sha1(_url(row).encode()).hexdigest()[:16]
        folder.mkdir(parents=True, exist_ok=True)
        clean = {("url" if k == "﻿url" else k): v for k, v in row.items()}
        with open(folder / "articol.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(clean), lineterminator="\n")
            writer.writeheader()
            writer.writerow(clean)
        result = _gemini(folder / "articol.csv", folder, cache_only=not GEMINI_LIVE)
        runs.append((result, AI_LIVE if result.get("api_calls") else AI_REPLAY))

    kept, judged = [], set()
    info = {"model": None, "prompt": None, "valide": 0, "respinse": 0, "neclare": 0,
            "fara_raspuns": 0, "apeluri": 0, "erori": []}
    for result, label in runs:
        info["apeluri"] += result.get("api_calls", 0)
        if result.get("status") not in ("completed", "completed_with_errors"):
            info["fara_raspuns"] += result.get("selected", 1)
            info["erori"] += result.get("errors", [])[:1]
            continue
        info["model"], info["prompt"] = result.get("model"), result.get("prompt_version")
        info["valide"] += result["valid"]
        info["respinse"] += result["rejected"]
        info["neclare"] += result["uncertain"]
        with open(Path(result["output"]) / "clasificare.csv", encoding="utf-8-sig", newline="") as f:
            judged |= {r["url"] for r in csv.DictReader(f)}
        for article in result["articole_valide"]:
            kept += [_from_ai(article, c, label) for c in article["extragere"].get("candidates", [])]
    return kept, judged, info


def from_contract(path: Path) -> list[dict]:
    """The team's press pipeline output (contract accidents.json); kept as is, labelled with its source."""
    return json.loads(path.read_text(encoding="utf-8"))
