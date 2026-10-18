"""Starts the FastAPI backend without Docker (`npm run backend:local`), automatic collection on (SAFEIASI_LIVE=1).
`npm run backend` runs the same API in Docker instead (scripts/backend.mjs), dependencies already installed.

    python web/scripts/backend.py

The server collects ISU releases and press articles into runtime/safeiasi.sqlite3 at start (unless the stored
data is younger than 30 minutes) and then every 30 minutes; the UI reads /api/v1/live/*.
A fresh clone starts from the committed seed (isu/seed/), so the map shows real data at once.

    python web/scripts/backend.py --share   # also refresh isu/seed/ after every collection; commit it to share
Uses the repo's .venv and creates it on first run. Port 8000 matches web/proxy.conf.json.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUIREMENTS = ["requirements.txt", "isu/requirements.txt", "scraping/requirements.txt"]


def run(*args: str | Path, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(a) for a in args], cwd=ROOT, env=env, check=True)


def ensure_venv() -> None:
    if not PYTHON.exists():
        print(f"backend: creating {VENV} (needs internet, once)")
        run(sys.executable, "-m", "venv", VENV)
    probe = subprocess.run([str(PYTHON), "-c", "import fastapi, pypdf, bs4, requests, h3, pyproj, shapely"], cwd=ROOT, capture_output=True)
    if probe.returncode != 0:
        print(f"backend: installing {', '.join(REQUIREMENTS)}")
        run(PYTHON, "-m", "pip", "install", *[arg for r in REQUIREMENTS for arg in ("-r", r)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--share", action="store_true", help="refresh isu/seed/ after each collection (then commit it)")
    args = parser.parse_args()

    ensure_venv()
    env = {**os.environ, "SAFEIASI_LIVE": "1", "PYTHONUTF8": "1"}
    if args.share:
        env["SAFEIASI_WRITE_SEED"] = "1"
        print("backend: --share: isu/seed/ is rewritten after each collection; commit it so colleagues get the data")
    print("backend: collection every 30 min into runtime/safeiasi.sqlite3; then `npm start` -> http://localhost:4200")
    try:
        run(PYTHON, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(args.port), env=env)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
