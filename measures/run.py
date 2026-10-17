"""Read the existing three scenarios and write a separate measures delivery."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from measures.catalog import catalog, provenance
from measures.rules import evaluate
from measures.research import evidence
from measures.frontend import attach_costs, frontend_payload
from risk.frontend_scenario import validate

ROOT = Path(__file__).resolve().parents[1]


def build(dataset):
    dataset = Path(dataset)
    names = ['manifest.json', 'crossings.geojson', 'hotspots.json', 'accidents.json', 'scenario_provenance.json']
    raw = {n: (dataset / n).read_bytes() for n in names}
    bundle = {n: json.loads(data) for n, data in raw.items()}
    validate(bundle)
    if bundle['scenario_provenance.json']['data_mode'] != 'simulation_mixed_sources':
        raise ValueError('Expected the explicit mixed-source scenario')
    features = {f['properties']['id']: f for f in bundle['crossings.geojson']['features']}
    events = {e['event_id']: e for e in bundle['accidents.json']}
    results = []
    catalog_rows, research = catalog(), evidence()
    for h in bundle['hotspots.json']:
        result = evaluate(features[h['crossing_id']], [events[i] for i in h['event_ids']],
                          mode='simulation_mixed_sources')
        result.update(nume=h['nume'], hotspot_id=h['id'], scenario_score_unchanged=h['scor'])
        result['measure_details'] = attach_costs(result, catalog_rows, research)
        results.append(result)
    warning = bundle['manifest.json']['avertisment'] + ' Măsuri candidate pentru verificare, nu decizii de lucrări.'
    source_hashes = {n: hashlib.sha256(data).hexdigest() for n, data in raw.items()}
    return {'measures.json': catalog_rows, 'catalog_provenance.json': provenance(),
            'research_evidence.json': research,
            'frontend_measures.json': frontend_payload(results, warning, source_hashes),
            'scenario_measures.json': dict(data_mode='simulation_mixed_sources',
                warning=warning, sources=source_hashes, locations=results)}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'risk/output/frontend-scenario/data')
    parser.add_argument('--output', type=Path, default=ROOT / 'measures/output/three-scenarios')
    parser.add_argument('--inspect', action='store_true', help='Calculate and print without writing files')
    args = parser.parse_args()
    if not args.inspect and args.output.exists():
        parser.error('Choose a new directory; existing files are protected')
    bundle = build(args.dataset)
    if not args.inspect:
        args.output.mkdir(parents=True)
        for name, document in bundle.items():
            (args.output / name).write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    for row in bundle['scenario_measures.json']['locations']:
        print(row['nume'], '| scor neschimbat:', row['scenario_score_unchanged'])
        for candidate in row['measure_details']:
            if not candidate['selected_for_display']:
                continue
            print('  -', candidate['measure_id'], ':', candidate['motiv'])
            print('    ', candidate['cost_display'])
            if candidate['indicative_cost']:
                print('     Sursă:', candidate['indicative_cost']['source_url'])
        print('  Reguli blocate:', ', '.join(r['measure_id'] for r in row['rules'] if r['status'] == 'insufficient_data') or 'niciuna')
    print('Fără scrieri.' if args.inspect else f'Output: {args.output}')


if __name__ == '__main__':
    main()
