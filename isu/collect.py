"""Fetches ISU Iași press releases about road crashes into the shared database (isu/store.py).

The yearly listing pages embed every attached PDF as JSON ({"titlu", "denumire"}), so one request per
year gives the full catalogue. Only titles that name a road crash are downloaded; each PDF is fetched once,
its layout text is kept in the database and the PDF itself is discarded.
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
import ssl
import time
import urllib.request

from . import config, store

# isuis.igsu.ro serves an incomplete certificate chain; the content is public and read-only.
_SSL = ssl._create_unverified_context()
_DOC = re.compile(r'"titlu":"((?:[^"\\]|\\.)*)","descriere":"(?:[^"\\]|\\.)*","denumire":"([0-9a-f-]{36}\.pdf)"')
# Text extracted by an earlier file-cache version of this module; read once instead of downloading again.
_LEGACY_TXT = config.ROOT / "cache" / "pdf"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(request, timeout=90, context=_SSL) as response:
        return response.read()


def is_crash_title(title: str) -> bool:
    t = title.lower().replace("-", " ")
    return bool(config.TITLE_CRASH.search(t)) and not config.TITLE_EXCLUDE.search(t)


def listing(slug: str) -> list[dict]:
    html = _get(f"{config.BASE}/comunicate-de-presa/{slug}").decode("utf-8")
    docs = {}
    for raw_title, file in _DOC.findall(html):
        docs[file] = json.loads(f'"{raw_title}"')
    return [{"titlu": t, "fisier": f, "url": f"{config.BASE}/resources/{f}", "listare": slug} for f, t in docs.items()]


def pdf_text(data: bytes) -> str:
    """Layout-mode text; the default pypdf mode splits words ("com una") and breaks the patterns."""
    from pypdf import PdfReader

    text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in PdfReader(io.BytesIO(data)).pages)
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def collect(db: sqlite3.Connection) -> tuple[list[dict], dict]:
    """Returns the crash releases with their text (from the database), and what this run did."""
    known = store.documents(db)
    releases, info = [], {"listari_esuate": [], "noi": 0, "esuate": 0}
    for slug in config.LISTINGS:
        try:
            crashes = [d for d in listing(slug) if is_crash_title(d["titlu"])]
        except OSError as error:
            # The site is down: keep serving what the database already has for this listing.
            print(f"isu: listing {slug} failed ({error}); using stored releases")
            info["listari_esuate"].append(slug)
            crashes = [{"titlu": r["title"], "fisier": r["id"], "url": r["url"], "listare": slug}
                       for r in known.values() if r["listing"] == slug]
        print(f"isu: {slug}: {len(crashes)} road-crash titles")
        releases += crashes

    missing = [r for r in releases if r["fisier"] not in known or known[r["fisier"]]["text"] is None]
    if missing:
        print(f"isu: fetching {len(missing)} new releases")
    for i, release in enumerate(missing, 1):
        legacy = _LEGACY_TXT / release["fisier"].replace(".pdf", ".txt")
        try:
            if legacy.exists():
                text = legacy.read_text(encoding="utf-8")
            else:
                text = pdf_text(_get(release["url"]))
                time.sleep(config.DELAY_S)
            store.save_document(db, release, text, None)
            info["noi"] += 1
        except Exception as error:  # a broken PDF must not stop the run; it is retried next time
            print(f"isu: {release['url']} failed: {error}")
            store.save_document(db, release, None, str(error)[:300])
            info["esuate"] += 1
        if i % 25 == 0:
            print(f"isu:   {i}/{len(missing)}")

    known = store.documents(db)
    for release in releases:
        release["text"] = known[release["fisier"]]["text"] if release["fisier"] in known else None
    return releases, info
