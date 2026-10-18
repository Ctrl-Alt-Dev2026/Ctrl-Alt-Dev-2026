"""python -m isu [--export DIR]  ->  one collection run into the shared database (what the server does every
30 minutes). --export also writes the contract files (manifest.json, accidents.json, …) to DIR."""
import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

from . import store
from .build import export
from .live import run_once


def main() -> int:
    parser = argparse.ArgumentParser(description="ISU Iași releases + press + PMUD streets -> shared database")
    parser.add_argument("--export", type=Path, help="also write the contract files of the new dataset here")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    detail = run_once()
    if detail is None:
        print("isu: another run is in progress")
        return 1
    print(json.dumps(detail, ensure_ascii=False, indent=1))
    with closing(store.connect()) as db:
        dataset = json.loads(store.latest_dataset(db)["payload"])
        print(json.dumps(dataset["manifest"]["statistici"], ensure_ascii=False, indent=1))
        if args.export:
            export(dataset, store.latest_extras(db), args.export)
            print(f"isu: contract files -> {args.export}")
    print(f"isu: dataset stored in {store.DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
