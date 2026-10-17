"""Explicit simulation: synthetic accident severities on an actual OSM crossing."""
import argparse
import json
from pathlib import Path
import sys

from risk.inspect import ROOT, read, breakdown


def scenario(city=ROOT / 'context/output/observed/iasi', fixtures=ROOT / 'false_data',
             crossing_id='osm-node-3372032447', event_ids=('ev-001', 'ev-002', 'ev-003')):
    city, fixtures = Path(city), Path(fixtures)
    manifest = read(fixtures / 'manifest.json')
    if manifest.get('data_mode') != 'synthetic' or manifest.get('schema_version') != '2.0':
        raise ValueError('Expected synthetic schema 2.0 accidents')
    features = read(city / 'crossings.geojson')['features']
    feature = next((f for f in features if f['properties']['id'] == crossing_id), None)
    if feature is None:
        raise ValueError(f'Unknown real crossing: {crossing_id}')
    evidence = read(city / 'geometry_report.json')
    if evidence.get('data_mode') != 'observed' or feature['properties'].get('sursa') != 'OSM':
        raise ValueError('Infrastructure must be observed OSM data')
    detail = next(c for c in evidence['crossings'] if c['id'] == crossing_id)
    indexed = {}
    for e in read(fixtures / 'accidents.json'):
        if e['event_id'] in indexed and indexed[e['event_id']] != e:
            raise ValueError('Conflicting duplicate synthetic event')
        indexed[e['event_id']] = e
    if not event_ids or len(set(event_ids)) != len(event_ids):
        raise ValueError('Choose distinct synthetic event IDs')
    # Deliberately discard the fixture locations: this is an assumed scenario,
    # not a spatial association or a claim that these events happened here.
    events = []
    for identifier in event_ids:
        if identifier not in indexed:
            raise ValueError(f'Unknown synthetic event: {identifier}')
        e = indexed[identifier]
        events.append({k: e.get(k) for k in ('event_id', 'gravitate', 'ora', 'noapte', 'cauza_raportata')})
    calculation = breakdown(feature, events)
    names = sorted({r['tags']['name'] for r in detail['roads'] if r['tags'].get('name')})
    return dict(data_mode='simulation_mixed_sources',
                assumption='Synthetic accident severities assumed at this crossing; original accident coordinates are not used.',
                infrastructure_source=str(city / 'crossings.geojson'),
                accident_source=str(fixtures / 'accidents.json'),
                crossing_id=crossing_id, road_names=names, coordinates=feature['geometry']['coordinates'],
                infrastructure=feature['properties'], evidence=detail, calculation=calculation)


def render(report):
    c, p, evidence = report['calculation'], report['infrastructure'], report['evidence']
    name = ' / '.join(report['road_names']) or report['crossing_id']
    counts = {severity: sum(e['severity'] == severity for e in c['events']) for severity in ('usor', 'grav', 'deces', 'necunoscut')}
    lines = [f"{name} — {c['result']['scor']} puncte (SCENARIU, nu scor real al locatiei)",
             f"Trecere OSM: {report['crossing_id']} | [lon, lat]: {report['coordinates']}",
             '', f"Accidente DEMO presupuse aici: {counts['usor']} usoare, {counts['grav']} grave, {counts['deces']} cu deces.",
             f"  {len(c['events'])} accidente x 1 + {counts['grav']} grave x 2 + {counts['deces']} decese x 4 = {c['event_subtotal']} puncte.",
             '', 'Datele OSM REALE colectate de noi adauga:']
    for row in c['context']:
        line = f"  +{row['points']} {row['label']}"
        if row['label'].startswith('Trecere'):
            line += f" (semafor={p['semafor']}, benzi={p['benzi']})"
        else:
            matches = evidence['schools_150m'] if row['label'].startswith('Scoala') else evidence['stops_100m']
            line += f" (obiect OSM la {matches[0]['distance_m']:.1f} m)" if matches else ' (necunoscut, nu absenta confirmata)'
        lines.append(line)
    speed = evidence['speed']['maxspeed_kmh']
    speed_text = f'{speed:g} km/h' if speed is not None else 'necunoscuta'
    lines.extend([f"TOTAL: {c['event_subtotal']} din accidente demo + {c['context_subtotal']} din OSM real = {c['result']['scor']}.",
                  'Necunoscute: ' + '; '.join(c['result']['date_lipsa']),
                  f"Limita viteza: {speed_text}; +0 puncte conform formulei existente.",
                  '', 'Accidentele demo NU sunt documentate la aceasta trecere. Nu calculam cea mai periculoasa zona.',
                  'Nu citim infrastructura demo; nu modificam si nu publicam date observate.'])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--crossing', default='osm-node-3372032447')
    parser.add_argument('--events', nargs='+', default=['ev-001', 'ev-002', 'ev-003'])
    parser.add_argument('--city', type=Path, default=ROOT / 'context/output/observed/iasi')
    parser.add_argument('--fixtures', type=Path, default=ROOT / 'false_data')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        report = scenario(args.city, args.fixtures, args.crossing, args.events)
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.error(str(exc))
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))


if __name__ == '__main__':
    main()
