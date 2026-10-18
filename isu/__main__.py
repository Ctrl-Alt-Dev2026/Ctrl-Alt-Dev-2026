"""python -m isu [--seed] [--no-run] [--export DIR]

  (no flags)   one collection run into the shared database (what the server does every 30 minutes)
  --seed       then write isu/seed/ from the database: commit it and colleagues get the same data on clone/pull
  --no-run     skip the collection (with --seed: just write the seed from what the database has)
  --export DIR also write the contract files (manifest.json, accidents.json, …) of the newest dataset to DIR
"""
import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

from . import store
from .build import export
from .live import run_once, write_seed


def main() -> int:
    parser = argparse.ArgumentParser(description="ISU Iași releases + press + PMUD streets -> shared database")
    parser.add_argument("--seed", action="store_true", help="write isu/seed/ (commit it to share the data)")
    parser.add_argument("--no-run", action="store_true", help="do not collect, use the database as it is")
    parser.add_argument("--export", type=Path, help="also write the contract files of the newest dataset here")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if not args.no_run:
        detail = run_once()
        if detail is None:
            print("isu: another run is in progress")
            return 1
        print(json.dumps(detail, ensure_ascii=False, indent=1))
    with closing(store.connect()) as db:
        latest = store.latest_dataset(db)
        if latest is None:
            print("isu: the database has no dataset yet; run without --no-run first")
            return 1
        dataset = json.loads(latest["payload"])
        print(json.dumps(dataset["manifest"]["statistici"], ensure_ascii=False, indent=1))
        if args.seed:
            print(f"isu: seed -> {store.SEED}: {json.dumps(write_seed(db), ensure_ascii=False)}")
            print("isu: commit isu/seed/ to share this data (git add isu/seed && git commit)")
        if args.export:
            extras = store.latest_extras(db)
            if extras is None:
                print("isu: the newest dataset came from the seed (no article texts); run a collection first")
                return 1
            export(dataset, extras, args.export)
            print(f"isu: contract files -> {args.export}")
    print(f"isu: database {store.DB_PATH}, dataset built {latest['built_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
