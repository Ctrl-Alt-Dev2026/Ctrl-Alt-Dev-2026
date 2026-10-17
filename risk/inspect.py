"""Read-only, offline data status and a worked synthetic scoring example."""
import argparse
import json
from pathlib import Path
import sys

from shapely.geometry import Point, shape

from risk.pipeline import analyze, score_location

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def breakdown(feature, events):
    """Explain the existing scorer; assert that the explanation reconciles."""
    scored = score_location(feature, events)
    p = feature['properties']
    rows = []
    for e in events:
        severity_bonus = {'deces': 4, 'grav': 2}.get(e['gravitate'], 0)
        rows.append(dict(event_id=e['event_id'], severity=e['gravitate'], base=1,
                         severity_bonus=severity_bonus, total=1 + severity_bonus))
    conditions = [
        ('Trecere fara semafor pe minimum 4 benzi', 2,
         p['tip'] == 'trecere' and p.get('semafor') is False and type(p.get('benzi')) is int and p['benzi'] >= 4),
        ('Scoala la sub 150 m', 1, p.get('scoala_150m') is True),
        ('Statie la sub 100 m', 1, p.get('statie_100m') is True),
    ]
    evidence = [dict(tip=p['tip'], semafor=p.get('semafor'), benzi=p.get('benzi')),
                dict(scoala_150m=p.get('scoala_150m')), dict(statie_100m=p.get('statie_100m'))]
    context = [dict(label=label, points=weight if applies else 0, applies=applies, evidence=values)
               for (label, weight, applies), values in zip(conditions, evidence)]
    total = sum(r['total'] for r in rows) + sum(r['points'] for r in context)
    if total != scored['scor']:
        raise ValueError('Explanation does not match scorer')
    return dict(result=scored, events=rows, context=context,
                event_subtotal=sum(r['total'] for r in rows),
                context_subtotal=sum(r['points'] for r in context))


def inspect_data(city, fixtures=None, zone_id=None, demo_location=None):
    crossings = read(Path(city) / 'crossings.geojson')
    zones = read(Path(city) / 'zones.geojson')
    geometry = read(Path(city) / 'geometry_report.json')
    if geometry.get('data_mode') != 'observed':
        raise ValueError('Expected observed municipal context')
    if zone_id:
        selected = next((z for z in zones['features'] if z['properties']['id'] == zone_id), None)
    else:
        # Default view is the metric cell containing Palas, not a claimed neighborhood boundary.
        selected = next((z for z in zones['features'] if shape(z['geometry']).covers(Point(27.5877, 47.1564))), None)
    if selected is None:
        raise ValueError('Zone not found')
    ids = {f['properties']['id'] for f in crossings['features']}
    assigned = [i for z in zones['features'] for i in z['properties']['crossing_ids']]
    if len(ids) != len(crossings['features']) or sorted(assigned) != sorted(ids):
        raise ValueError('Crossing IDs or zone membership are inconsistent; run context.validate_city')
    observed = dict(data_mode='observed', score=None, score_status='accidents_not_integrated',
                    summary=geometry['summary'], collection_dates=geometry.get('collection_date_range'),
                    zone=selected['properties'])
    if fixtures is None:
        return dict(observed=observed)
    manifest = read(Path(fixtures) / 'manifest.json')
    if manifest.get('data_mode') != 'synthetic' or manifest.get('schema_version') != '2.0':
        raise ValueError('Scoring demonstration requires synthetic schema 2.0 fixtures')
    events = read(Path(fixtures) / 'accidents.json')
    demo_crossings = read(Path(fixtures) / 'crossings.geojson')
    hotspots, associations = analyze(events, demo_crossings)
    if not hotspots:
        raise ValueError('No synthetic hotspots could be calculated')
    selected_id = demo_location or hotspots[0]['crossing_id']
    hotspot = next((h for h in hotspots if h['crossing_id'] == selected_id), None)
    if hotspot is None:
        raise ValueError('Demo location has no hotspot with at least two conservatively associated events')
    feature = next(f for f in demo_crossings['features'] if f['properties']['id'] == selected_id)
    event_index = {e['event_id']: e for e in events}
    calculation = breakdown(feature, [event_index[i] for i in hotspot['event_ids']])
    reference = next((h for h in read(Path(fixtures) / 'hotspots.json') if h['crossing_id'] == selected_id), None)
    excluded_reference = []
    if reference:
        diagnostics = {a['event_id']: a for a in associations['associations']}
        excluded_reference = [diagnostics[i] for i in reference['event_ids'] if i not in hotspot['event_ids']]
    return dict(observed=dict(data_mode='observed', score=None, score_status='accidents_not_integrated',
                             summary=geometry['summary'], collection_dates=geometry.get('collection_date_range'),
                             zone=selected['properties']),
                synthetic=dict(data_mode='synthetic', calculation=calculation,
                               ranking=[dict(id=h['crossing_id'], name=h['nume'], score=h['scor']) for h in hotspots],
                               fixture_reference_score=reference['scor'] if reference else None,
                               excluded_reference_events=excluded_reference))


def render(report):
    live, demo = report['observed'], report.get('synthetic')
    zone, summary = live['zone'], live['summary']
    if demo is None:
        speeds = ', '.join(f"{float(speed):g} km/h la {count} treceri" for speed, count in zone['explicit_speed_limits_kmh'].items()) or 'necunoscute'
        return '\n'.join([
            'OSM REAL - exclusiv snapshot-ul API salvat; fara accidente sau fixture-uri demo.',
            f"Iasi: {summary['crossings']} treceri, {summary['zones']} zone.",
            f"Zona inspectata: {zone['id']} (celula de analiza de 1 km, nu cartier).",
            f"Treceri: {zone['mapped_crossings']}; semaforizate: {zone['traffic_signals_known']}; fara semafor: {zone['no_traffic_signals_confirmed']}; semafor necunoscut: {zone['missing_fields']['semafor']}.",
            f"Configuratii fara semafor pe 4+ benzi: {zone['unsignalized_4plus_lanes']} treceri.",
            f"Scoala la sub 150 m: {zone['school_within_150m']} treceri; statie la sub 100 m: {zone['stop_within_100m']} treceri.",
            'Limite explicite: ' + speeds + f"; necunoscute la {zone['unknown_speed']} treceri.",
            'SCOR DE RISC: indisponibil; nu avem accidente reale integrate.',
            'Ponderi existente pe trecere: +2 fara semafor SI 4+ benzi; +1 scoala; +1 statie. Viteza: fara puncte.',
            'Componenta de infrastructura are maximum 4 puncte pe trecere; nu este un scor nou pe zona.',
        ])
    lines = ['=== STAREA OSM REALA - FARA ACCIDENTE INTEGRATE ===',
             f"Municipiu: {summary['crossings']} treceri, {summary['zones']} zone.",
             f"Legaturi rutiere: {summary['road_status'].get('linked', 0)} confirmate; {summary['road_status'].get('unresolved', 0)} neclarificate.",
             f"Benzi cunoscute: {summary['with_lanes']}; viteza numerica explicita: {summary['explicit_numeric_speed']}.",
             f"Interval colectare UTC: {live['collection_dates']}",
             '', f"Zona inspectata: {zone['id']}",
             'Drumuri conectate trecerilor: ' + ', '.join(zone.get('mapped_road_names', [])),
             f"Punct de referinta [lon, lat]: [{zone['reference_lon']:.6f}, {zone['reference_lat']:.6f}]",
             f"Treceri cartografiate: {zone['mapped_crossings']}",
             f"Semaforizate: {zone['traffic_signals_known']}; explicit nesemaforizate: {zone['no_traffic_signals_confirmed']}",
             f"Fara semafor pe 4+ benzi: {zone['unsignalized_4plus_lanes']}",
             f"Cu scoala <150 m: {zone['school_within_150m']}; cu statie <100 m: {zone['stop_within_100m']}",
             'Limite de viteza explicite km/h -> numar treceri: ' + json.dumps(zone['explicit_speed_limits_kmh']),
             'Campuri necunoscute -> numar treceri: ' + json.dumps(zone['missing_fields']),
             'SCOR REAL: INDISPONIBIL (nu zero). Nu exista accidente reale integrate.',
             'Zona este o celula de analiza, nu un cartier; nu o clasificam sigur/periculos.',
             '', '=== DEMO SEPARAT - DATE INTEGRAL SINTETICE ===',
             'Clasament recalculat: ' + '; '.join(f"{h['name']}={h['score']}" for h in demo['ranking'])]
    calculation = demo['calculation']
    result = calculation['result']
    lines.extend([f"Exemplu: {result['nume']} ({result['crossing_id']})", 'Calcul pe evenimente unice:'])
    lines.extend(f"  {e['event_id']} ({e['severity']}): {e['base']} baza + {e['severity_bonus']} gravitate = {e['total']}"
                 for e in calculation['events'])
    lines.append(f"Subtotal accidente: {calculation['event_subtotal']}")
    lines.extend(f"  {c['label']}: +{c['points']} | valori: {json.dumps(c['evidence'])}" for c in calculation['context'])
    lines.append(f"TOTAL DEMO: {calculation['event_subtotal']} + {calculation['context_subtotal']} = {result['scor']}")
    if demo['fixture_reference_score'] != result['scor']:
        lines.append(f"Fixture-ul de referinta declara {demo['fixture_reference_score']}; gruparea sa nu este folosita automat.")
        for event in demo['excluded_reference_events']:
            lines.append(f"  {event['event_id']} exclus din grupare: {event['status']} (necesita verificare).")
    lines.extend(['Date lipsa: ' + '; '.join(result['date_lipsa']),
                  'null = necunoscut; nu adauga puncte si nu demonstreaza absenta infrastructurii.',
                  'Viteza limita: nu adauga puncte in formula existenta.',
                  'Acesta este un scor de prioritizare demonstrativ, nu probabilitate de accident.',
                  'Verificare: suma componentelor coincide cu scorul. Nu s-au modificat fisiere sau apelat API-uri.'])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city', type=Path, default=ROOT / 'context/output/observed/iasi')
    parser.add_argument('--fixtures', type=Path, help='Explicit synthetic directory; enables demonstration')
    parser.add_argument('--with-demo', action='store_true', help='Opt in to synthetic example from false_data/')
    parser.add_argument('--zone', help='Zone ID from zones.csv; default is the cell containing Palas')
    parser.add_argument('--demo-location', help='Synthetic crossing ID; default is the highest recalculated priority')
    parser.add_argument('--json', action='store_true', help='Machine-readable output with modes kept separate')
    args = parser.parse_args()
    try:
        fixtures = args.fixtures or (ROOT / 'false_data' if args.with_demo or args.demo_location else None)
        report = inspect_data(args.city, fixtures, args.zone, args.demo_location)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) if args.json else render(report))


if __name__ == '__main__':
    main()
