"""Paths and fixed rules for the ISU Iași crash pipeline. Changing a rule changes the published data."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
# Collected texts, run log and built datasets live in the SQLite store (store.py, SAFEIASI_DB).
PMUD_CSV = ROOT / "pmud2022_tabel_2_11.csv"

BASE = "https://isuis.igsu.ro"
# One listing page per year. The ids are not discoverable from the index page; add next year's here.
# 2024 starts in October (the site archive begins then).
LISTINGS = ["stiri-de-presa-2024-57", "stiri-de-presa-2025-56", "stiri-de-presa-2026-175"]
USER_AGENT = "SafeIasi-POC/0.1 (hackathon; date publice ISU Iasi)"
DELAY_S = 0.4

# Titles are a generous pre-filter (only these PDFs are downloaded); parse.BODY_CRASH confirms from the text.
TITLE_CRASH = re.compile(r"accident|coliziune|tampon|carambol|acro[șs]at|lovit|descarcer|r[ăa]sturnat|"
                         r"afar[aă] carosabilului")
# Releases that name a crash but are not a road crash on a public road, or are drills/statistics.
TITLE_EXCLUDE = re.compile(r"feroviar|aviatic|de muncă|exerci[țt]i|simulare|bilan[țt]|statistic|campani|recomand")

SOURCE = "ISU Iași (comunicat de presă)"
