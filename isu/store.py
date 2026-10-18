"""SQLite store shared by the collector and the API: ISU release texts, the run log and the built dataset.

One file (SAFEIASI_DB, default runtime/safeiasi.sqlite3). The collector only ever adds documents; each run
writes one dataset row, and the API serves the newest one, so every viewer sees the same data.

The database is not in git; the seed is (isu/seed/, written by `python -m isu --seed`). Opening a database imports
the seed's release texts it lacks and the seed's dataset if it is newer than the local one, so a fresh clone or a
`git pull` shows the same data as whoever wrote the seed, and the local collector only fetches what came after.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

DB_PATH = Path(os.environ.get("SAFEIASI_DB", config.REPO / "runtime" / "safeiasi.sqlite3"))
KEEP_DATASETS = 5
SEED = config.ROOT / "seed"
SEED_DOCUMENTS = SEED / "documents.jsonl"     # ISU release texts (one JSON object per line, sorted by id)
SEED_DATASET = SEED / "dataset.json"          # the dataset as served by /api/v1/live/dataset
SEED_PRESS = SEED / "presa_candidati.csv"     # press articles found by the live scraper (scraper export format)
_seeded: set[Path] = set()
_seed_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,           -- PDF file name (UUID) on isuis.igsu.ro
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  listing TEXT NOT NULL,
  text TEXT,                     -- null = download or extraction failed; retried on the next run
  fetched_at TEXT NOT NULL,
  error TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,          -- running | ok | error
  detail TEXT                    -- JSON: per-source outcome or the error message
);
CREATE TABLE IF NOT EXISTS datasets (
  id INTEGER PRIMARY KEY,
  built_at TEXT NOT NULL,
  run_id INTEGER NOT NULL,
  payload TEXT NOT NULL          -- JSON served as is by /api/v1/live/dataset
);
CREATE TABLE IF NOT EXISTS extras (
  dataset_id INTEGER PRIMARY KEY,
  payload TEXT NOT NULL          -- {articles, raport_geocodare} of that dataset (full texts, not sent to the map)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    with _seed_lock:
        if path not in _seeded:
            import_seed(db)
            _seeded.add(path)
    return db


def import_seed(db: sqlite3.Connection) -> dict:
    """Adds the committed seed to this database: missing release texts, and the dataset if it is newer."""
    added = {"documente": 0, "set_de_date": False}
    if SEED_DOCUMENTS.exists():
        with open(SEED_DOCUMENTS, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        before = db.total_changes
        db.executemany(
            "INSERT OR IGNORE INTO documents (id, source, url, title, listing, text, fetched_at, error) "
            "VALUES (:id, :source, :url, :title, :listing, :text, :fetched_at, NULL)", rows)
        # A release whose download failed locally (text null) takes the seed's text.
        db.executemany("UPDATE documents SET text=:text, error=NULL WHERE id=:id AND text IS NULL", rows)
        added["documente"] = db.total_changes - before
    if SEED_DATASET.exists():
        payload = SEED_DATASET.read_text(encoding="utf-8").strip()
        built_at = json.loads(payload)["built_at"]
        latest = latest_dataset(db)
        if latest is None or latest["built_at"] < built_at:
            cursor = db.execute("INSERT INTO runs (started_at, finished_at, status, detail) VALUES (?,?,'ok',?)",
                                (now(), now(), json.dumps({"sursa": "seed din git (isu/seed)", "construit_la": built_at},
                                                          ensure_ascii=False)))
            db.execute("INSERT INTO datasets (built_at, run_id, payload) VALUES (?,?,?)", (built_at, cursor.lastrowid, payload))
            added["set_de_date"] = True
    db.commit()
    return added


def export_seed(db: sqlite3.Connection) -> dict:
    """Writes the seed from this database (stable order, so git only sees real changes)."""
    SEED.mkdir(parents=True, exist_ok=True)
    rows = db.execute("SELECT id, source, url, title, listing, text, fetched_at FROM documents "
                      "WHERE text IS NOT NULL ORDER BY id").fetchall()
    with open(SEED_DOCUMENTS, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n")
    latest = latest_dataset(db)
    if latest is not None:
        SEED_DATASET.write_text(latest["payload"] + "\n", encoding="utf-8", newline="\n")
    return {"documente": len(rows), "construit_la": latest["built_at"] if latest else None}


def documents(db: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {row["id"]: row for row in db.execute("SELECT * FROM documents")}


def save_document(db: sqlite3.Connection, doc: dict, text: str | None, error: str | None) -> None:
    db.execute(
        "INSERT INTO documents (id, source, url, title, listing, text, fetched_at, error) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET text=excluded.text, fetched_at=excluded.fetched_at, error=excluded.error, "
        "title=excluded.title, listing=excluded.listing",
        (doc["fisier"], "isu", doc["url"], doc["titlu"], doc["listare"], text, now(), error),
    )
    db.commit()


def start_run(db: sqlite3.Connection) -> int:
    cursor = db.execute("INSERT INTO runs (started_at, status) VALUES (?, 'running')", (now(),))
    db.commit()
    return cursor.lastrowid


def finish_run(db: sqlite3.Connection, run_id: int, status: str, detail: dict) -> None:
    db.execute("UPDATE runs SET finished_at=?, status=?, detail=? WHERE id=?",
               (now(), status, json.dumps(detail, ensure_ascii=False), run_id))
    db.commit()


def save_dataset(db: sqlite3.Connection, run_id: int, dataset: dict, extras: dict) -> str:
    built_at = now()
    payload = json.dumps({"built_at": built_at, **dataset}, ensure_ascii=False, separators=(",", ":"))
    cursor = db.execute("INSERT INTO datasets (built_at, run_id, payload) VALUES (?,?,?)", (built_at, run_id, payload))
    db.execute("INSERT INTO extras (dataset_id, payload) VALUES (?,?)",
               (cursor.lastrowid, json.dumps(extras, ensure_ascii=False, separators=(",", ":"))))
    old = "SELECT id FROM datasets ORDER BY id DESC LIMIT -1 OFFSET ?"
    db.execute(f"DELETE FROM extras WHERE dataset_id IN ({old})", (KEEP_DATASETS,))
    db.execute(f"DELETE FROM datasets WHERE id IN ({old})", (KEEP_DATASETS,))
    db.commit()
    return built_at


def latest_dataset(db: sqlite3.Connection) -> sqlite3.Row | None:
    return db.execute("SELECT id, built_at, payload FROM datasets ORDER BY id DESC LIMIT 1").fetchone()


def latest_extras(db: sqlite3.Connection) -> dict | None:
    """Article texts and geocoding report of the newest dataset; None for a dataset imported from the seed."""
    row = db.execute("SELECT extras.payload FROM extras JOIN (SELECT max(id) AS id FROM datasets) AS newest "
                     "ON extras.dataset_id = newest.id").fetchone()
    return json.loads(row["payload"]) if row else None


def last_runs(db: sqlite3.Connection, n: int = 1) -> list[dict]:
    rows = db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [{**dict(r), "detail": json.loads(r["detail"]) if r["detail"] else None} for r in rows]


def close_stale_runs(db: sqlite3.Connection) -> None:
    """A run still 'running' at startup was interrupted (process stopped)."""
    db.execute("UPDATE runs SET status='error', finished_at=?, detail=? WHERE status='running'",
               (now(), json.dumps({"eroare": "rulare întreruptă (serverul s-a oprit)"}, ensure_ascii=False)))
    db.commit()

