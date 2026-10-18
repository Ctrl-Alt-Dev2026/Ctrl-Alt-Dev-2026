"""Scheduled collection: every SAFEIASI_REFRESH_MIN minutes (default 30) the server fetches new ISU releases and
new press articles, rebuilds the dataset and stores it in the shared database. The API serves the newest one.

Press: the team's scraper (scraping/scraper_stiri.py --noutati) runs as a bounded subprocess in its own folder
(SAFEIASI_PRESS_DIR, default runtime/presa); its candidati.csv is read on top of the committed 2026 sample.
SAFEIASI_SCRAPE_PRESS=0 skips the scraper and keeps only the committed sample.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, store
from .build import build

REFRESH_MIN = max(5, int(os.environ.get("SAFEIASI_REFRESH_MIN", "30")))
PRESS_DIR = Path(os.environ.get("SAFEIASI_PRESS_DIR", config.REPO / "runtime" / "presa"))
PRESS_SAMPLE = config.REPO / "scraping" / "articole_extrase_accident_clean.csv"
SCRAPE_PRESS = os.environ.get("SAFEIASI_SCRAPE_PRESS", "1") != "0"
# One run must end well before the next one: a few listing pages and at most 40 articles, 5 s apart.
SCRAPER_ARGS = ["--noutati", "--de-la", "2026-01-01", "--pauza", "5", "--max-taskuri", "40"]
SCRAPER_TIMEOUT_S = 15 * 60

_run_lock = threading.Lock()


def scrape_press() -> dict:
    if not SCRAPE_PRESS:
        return {"stare": "oprit", "motiv": "SAFEIASI_SCRAPE_PRESS=0"}
    try:
        import bs4, requests  # noqa: F401  (scraping/requirements.txt)
    except ImportError:
        return {"stare": "indisponibil", "motiv": "lipsesc dependențele din scraping/requirements.txt"}
    command = [sys.executable, "-m", "scraping.scraper_stiri", *SCRAPER_ARGS, "--director", str(PRESS_DIR)]
    try:
        result = subprocess.run(command, cwd=config.REPO, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=SCRAPER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"stare": "expirat", "motiv": f"peste {SCRAPER_TIMEOUT_S // 60} minute; coada continuă la rularea următoare"}
    lines = (result.stdout + result.stderr).strip().splitlines()
    return {"stare": "ok" if result.returncode == 0 else "eroare", "cod": result.returncode, "jurnal": lines[-5:]}


def run_once() -> dict | None:
    """One collection run. Returns its summary, or None if another run is in progress."""
    if not _run_lock.acquire(blocking=False):
        return None
    try:
        with closing(store.connect()) as db:
            run_id = store.start_run(db)
            try:
                press = scrape_press()
                dataset, extras, fetched = build(db, [PRESS_SAMPLE, PRESS_DIR / "candidati.csv"])
                built_at = store.save_dataset(db, run_id, dataset, extras)
                detail = {"isu": fetched, "presa": press, "evenimente": len(dataset["accidents"]), "construit_la": built_at}
                store.finish_run(db, run_id, "ok", detail)
                return detail
            except Exception as error:
                store.finish_run(db, run_id, "error", {"eroare": f"{type(error).__name__}: {error}"})
                raise
    finally:
        _run_lock.release()


class Scheduler:
    """Background thread started by the API lifespan. The first run starts at once unless the stored dataset
    is younger than the interval (a restart does not re-fetch everything)."""

    def __init__(self, minutes: int = REFRESH_MIN):
        self.interval = timedelta(minutes=minutes)
        self.next_run_at: datetime | None = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="safeiasi-collector", daemon=True)

    @property
    def running(self) -> bool:
        return _run_lock.locked()

    def start(self) -> None:
        with closing(store.connect()) as db:
            store.close_stale_runs(db)
            latest = store.latest_dataset(db)
        now = datetime.now(timezone.utc)
        built = datetime.fromisoformat(latest["built_at"]) if latest else None
        self.next_run_at = built + self.interval if built and built + self.interval > now else now
        self._thread.start()

    def trigger(self) -> None:
        self.next_run_at = datetime.now(timezone.utc)
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            delay = (self.next_run_at - datetime.now(timezone.utc)).total_seconds()
            if delay > 0 and self._wake.wait(delay):
                self._wake.clear()
                continue  # triggered or stopping: re-read next_run_at / the stop flag
            if self._stop.is_set():
                break
            try:
                run_once()
            except Exception:
                traceback.print_exc()  # recorded in the run log; the next run retries
            self.next_run_at = datetime.now(timezone.utc) + self.interval
