"""Prepare an isolated frontend dataset: observed crossings + explicit demo assignments."""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

from risk.inspect import ROOT, read, breakdown
from risk.h3_layer import aggregate, attach_hotspot_cells
from risk.statistics import event_statistics, unique_events

WARNING = ('SCENARIU DEMONSTRATIV: infrastructură OSM reală + accidente sintetice '
           'plasate ipotetic la treceri reale. Accidentele NU sunt documentate aici. '
           'Scorurile NU reprezintă riscul real sau un clasament real de pericol.')
# Explicit demonstration assignments; never obtained by moving real accident records.
ASSIGNMENTS = [
    ('osm-node-3372032447', ['ev-001', 'ev-002', 'ev-003']),
    ('osm-node-6194970559', ['ev-005', 'ev-006', 'ev-007']),
    ('osm-node-6910606104', ['ev-010', 'ev-011', 'ev-013']),
]


def build(city=ROOT / 'context/output/observed/iasi', fixtures=ROOT / 'false_data'):
    city, fixtures = Path(city), Path(fixtures)
    if read(fixtures / 'manifest.json').get('data_mode') != 'synthetic':
        raise ValueError('Accident template source must be synthetic')
    evidence = read(city / 'geometry_report.json')
    if evidence.get('data_mode') != 'observed':
        raise ValueError('Infrastructure source must be observed')
    crossings = copy.deepcopy(read(city / 'crossings.geojson'))
    features = {f['properties']['id']: f for f in crossings['features']}
    details = {c['id']: c for c in evidence['crossings']}
    originals = {e['event_id']: e for e in unique_events(read(fixtures / 'accidents.json'))}
    for identifier, f in features.items():
        if f['properties']['sursa'] != 'OSM':
            raise ValueError('Non-OSM crossing in observed source')
        names = sorted({r['tags']['name'] for r in details[identifier]['roads'] if r['tags'].get('name')})
        f['properties']['nume'] = f['properties'].get('nume') or ' / '.join(names) or f'Trecere OSM {identifier}'
    accidents, hotspots, provenance, statistics = [], [], [], {}
    used = set()
    for crossing_id, template_ids in ASSIGNMENTS:
        f = features[crossing_id]
        p = f['properties']
        lon, lat = f['geometry']['coordinates']
        group = []
        for template_id in template_ids:
            if template_id in used:
                raise ValueError('Synthetic template reused across locations')
            used.add(template_id)
            original = originals[template_id]
            event = copy.deepcopy(original)
            event.update(event_id=f'scenario-{template_id}', article_ids=[], urls=[],
                         loc_text=f'SCENARIU IPOTETIC la trecerea {p["nume"]}; nu este accident documentat aici.',
                         lat=lat, lon=lon, precizie_loc='trecere', in_iasi=True, verificat=False,
                         cauza_raportata=None,
                         dovezi={'loc_text': 'Plasare ipotetică pentru test; nu este geocodare dintr-un articol.',
                                 'gravitate': f'Severitate preluată din fixture-ul sintetic {template_id}.'})
            # Reported causes from the old fixture are not evidence about the real road.
            group.append(event)
            accidents.append(event)
            provenance.append(dict(event_id=event['event_id'], source_template=template_id,
                                   assigned_crossing_id=crossing_id, assignment='explicit_hypothetical_not_geocoding'))
        calc = breakdown(f, group)
        h = calc['result']
        h['id'] = 'scenario-' + crossing_id
        h['nume'] = 'SCENARIU — ' + p['nume']
        pieces = []
        for row in calc['context']:
            label = row['label']
            matches = details[crossing_id]['schools_150m'] if label.startswith('Scoala') else details[crossing_id]['stops_100m']
            extra = f' (OSM: {matches[0]["distance_m"]:.1f} m)' if row['points'] and not label.startswith('Trecere') and matches else ''
            pieces.append(f'+{row["points"]} {label}{extra}')
        h['explicatie'] = (f'SCENARIU, nu accidente reale aici: {calc["event_subtotal"]} puncte din accidente DEMO; '
                           + '; '.join(pieces) + f'. Total {h["scor"]}. '
                           'Infrastructura și coordonatele provin din OSM real. Viteza nu adaugă puncte.')
        h['date_lipsa'].insert(0, 'SCENARIU: accidente ipotetice; nu există dovezi de accidente reale la această locație.')
        hotspots.append(h)
        statistics[crossing_id] = event_statistics(group)
    hotspots = attach_hotspot_cells(sorted(hotspots, key=lambda h: (-h['scor'], h['crossing_id'])))
    dates = sorted(e['data_eveniment'] for e in accidents if e.get('data_eveniment'))
    manifest = dict(schema_version='2.0', data_mode='synthetic', perioada=[dates[0], dates[-1]],
                    generat_la=dt.datetime.now(dt.timezone.utc).isoformat(), nr_articole=0,
                    nr_evenimente=len(accidents), nr_localizate_precis=len(accidents),
                    nr_verificate=0, avertisment=WARNING)
    source_paths = [city / 'crossings.geojson', city / 'geometry_report.json', fixtures / 'accidents.json']
    return {'manifest.json': manifest, 'crossings.geojson': crossings,
            'accidents.json': accidents, 'hotspots.json': hotspots,
            'articles.json': [], 'measures.json': [], 'cameras.json': [],
            'accidents_h3.geojson': aggregate(accidents, 'synthetic'),
            'scenario_provenance.json': dict(data_mode='simulation_mixed_sources', avertisment=WARNING,
                assignments=provenance, location_statistics=statistics,
                sources=[dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in source_paths])}


def validate(bundle):
    manifest = bundle['manifest.json']
    events = {e['event_id']: e for e in bundle['accidents.json']}
    crossings = {f['properties']['id']: f for f in bundle['crossings.geojson']['features']}
    if manifest['data_mode'] != 'synthetic' or 'SCENARIU' not in manifest['avertisment']:
        raise ValueError('Missing scenario labels')
    if manifest['nr_evenimente'] != len(events) or len(events) != len(bundle['accidents.json']):
        raise ValueError('Incorrect event totals')
    assigned = []
    for h in bundle['hotspots.json']:
        f = crossings[h['crossing_id']]
        group = [events[i] for i in h['event_ids']]
        if h['scor'] != breakdown(f, group)['result']['scor'] or 'SCENARIU' not in h['nume']:
            raise ValueError('Incorrect score or label')
        for e in group:
            if [e['lon'], e['lat']] != f['geometry']['coordinates'] or e['verificat'] or e['urls'] or e['article_ids']:
                raise ValueError('Scenario presented as sourced/verified or wrong geometry')
        assigned += h['event_ids']
    if sorted(assigned) != sorted(events):
        raise ValueError('Event assignments are not unique and complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'risk/output/frontend-scenario')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory; existing files are protected')
    bundle = build()
    validate(bundle)
    target = args.output / 'data'
    target.mkdir(parents=True)
    for name, data in bundle.items():
        (target / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(data_mode='simulation_mixed_sources', crossings=len(bundle['crossings.geojson']['features']),
                         demo_events=len(bundle['accidents.json']),
                         scenarios=[dict(name=h['nume'], score=h['scor']) for h in bundle['hotspots.json']],
                         output=str(args.output)), ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
