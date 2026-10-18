"""Press articles (BZI, Ziarul de Iași) -> events, kept apart from ISU.

Preferred input: the team's press pipeline output (accidents.json in the contract, from `ai/` + `coordonate/`),
passed with --presa. Until that exists, a provisional rule pass reads the articles the scraper collected
(scraping/articole_extrase_accident_clean.csv). It is strict on purpose: enforcement round-ups, court cases
and follow-ups about old crashes are dropped, and every event says it came from these rules.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from . import config
from .parse import STREET, TIME, _clean_place, _sentence, participants, severity

ARTICLES_CSV = config.REPO / "scraping" / "articole_extrase_accident_clean.csv"
SOURCE_NAMES = {"bzi": "BZI", "zdi": "Ziarul de Iași"}

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


def from_contract(path: Path) -> list[dict]:
    """The team's press pipeline output (contract accidents.json); kept as is, labelled with its source."""
    return json.loads(path.read_text(encoding="utf-8"))
