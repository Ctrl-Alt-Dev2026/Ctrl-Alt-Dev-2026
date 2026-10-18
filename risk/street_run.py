"""Offline street analysis of an already matched live dataset; no collection/geocoding.

python -m risk.street_run --dataset isu/seed/dataset.json --output risk/output/observed/streets
"""
import argparse
import json
from pathlib import Path

from risk.streets import enrich_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--update-dataset', action='store_true', help='Also replace the supplied derived dataset, preserving built_at')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory; existing analysis is not overwritten')
    dataset = enrich_dataset(json.loads(args.dataset.read_text(encoding='utf-8')))
    args.output.mkdir(parents=True)
    outputs = {'dataset.json': dataset, 'streets.geojson': dataset['streets'],
               'accidents_h3.geojson': dataset['accidents_h3'],
               'street_analysis.json': dataset['street_analysis']}
    for name, value in outputs.items():
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if args.update_dataset:
        # Match the committed SQLite seed format; do not reformat all collected evidence.
        args.dataset.write_text(json.dumps(dataset, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(streets=len(dataset['streets']['features']),
                         cells=len(dataset['accidents_h3']['features']),
                         assigned_events=len(dataset['street_analysis']['street_event_ids']),
                         unmatched_street_events=len(dataset['street_analysis']['unmatched_street_event_ids']))))


if __name__ == '__main__':
    main()
