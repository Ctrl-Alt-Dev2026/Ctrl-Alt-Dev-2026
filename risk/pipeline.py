"""Offline schema 2.0 analysis. No recommendations or input mutations."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from pyproj import Transformer


PROJECT = Transformer.from_crs(4326, 32635, always_xy=True)


def point(lon, lat):
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (lon, lat)):
        raise ValueError("Invalid coordinates")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Coordinates out of range")
    return PROJECT.transform(lon, lat, errcheck=True)


def score_location(feature, events):
    p = feature['properties']
    components = dict(evenimente=len(events), deces=4 * sum(e['gravitate'] == 'deces' for e in events),
                      grav=2 * sum(e['gravitate'] == 'grav' for e in events), context=0)
    reasons = []
    if (p['tip'] == 'trecere' and p.get('semafor') is False
            and type(p.get('benzi')) is int and p['benzi'] >= 4):
        components['context'] += 2
        reasons.append('trecere confirmată fără semafor pe 4+ benzi (+2)')
    for field, label in [('scoala_150m', 'școală la mai puțin de 150 m'),
                         ('statie_100m', 'stație la mai puțin de 100 m')]:
        if p.get(field) is True:
            components['context'] += 1
            reasons.append(label + ' (+1)')
    missing = [f'{key} necunoscut' for key in
               ('semafor', 'benzi', 'iluminat', 'tip_strada', 'scoala_150m', 'statie_100m')
               if p.get(key) is None]
    hours = [0] * 24
    unknown_hours = 0
    for event in events:
        hour = event.get('ora')
        if hour is None:
            unknown_hours += 1
        else:
            import datetime
            parsed = datetime.datetime.strptime(hour, '%H:%M')
            hours[parsed.hour] += 1
    for field in ('gravitate', 'noapte', 'cauza_raportata'):
        count = sum(e.get(field) in (None, 'necunoscut') for e in events)
        if count:
            missing.append(f'{field} necunoscut la {count} evenimente')
    if unknown_hours:
        missing.append(f'ora necunoscută la {unknown_hours} evenimente')
    lon, lat = feature['geometry']['coordinates']
    return dict(id='h-' + p['id'], crossing_id=p['id'], nume=p.get('nume'), lat=lat, lon=lon,
                h3=None, scor=sum(components.values()), componente_scor=components,
                event_ids=[e['event_id'] for e in events], nr_evenimente=len(events), pe_ore=hours,
                explicatie='; '.join([f"{len(events)} evenimente documentate; bonus deces {components['deces']}; bonus grav {components['grav']}"] + reasons),
                date_lipsa=missing, masuri=[], verificat=False)


def analyze(events, crossings):
    features = crossings['features']
    indexed = {}
    for f in features:
        p = f['properties']
        if p['id'] in indexed or p['tip'] not in ('trecere', 'intersectie'):
            raise ValueError('Duplicate location or invalid location type')
        if f['geometry']['type'] != 'Point':
            raise ValueError('Expected Point')
        indexed[p['id']] = (f, point(*f['geometry']['coordinates']))
    unique = {}
    for e in events:
        identifier = e['event_id']
        if identifier in unique and unique[identifier] != e:
            raise ValueError(f'Conflicting duplicate event_id: {identifier}')
        unique[identifier] = e
    groups = defaultdict(list)
    diagnostics = []
    for e in unique.values():
        if e.get('in_iasi') is not True or e.get('precizie_loc') not in ('trecere', 'intersectie', 'segment'):
            diagnostics.append(dict(event_id=e['event_id'], status='ineligible'))
            continue
        if e.get('gravitate') not in ('deces', 'grav', 'usor', 'necunoscut'):
            raise ValueError('Invalid severity')
        xy = point(e.get('lon'), e.get('lat'))
        candidates = [(identifier, math.dist(xy, loc)) for identifier, (f, loc) in indexed.items()
                      if math.dist(xy, loc) <= 50]
        # Proximity is only a candidate, never proof. Multiple candidates stay unresolved.
        status = 'unmatched'
        if len(candidates) > 1:
            status = 'ambiguous'
        elif candidates:
            identifier, distance = candidates[0]
            f = indexed[identifier][0]
            if e['precizie_loc'] != f['properties']['tip']:
                status = 'precision_mismatch'
            else:
                groups[identifier].append(e)
                status = 'provisional_nearby'
        diagnostics.append(dict(event_id=e['event_id'], status=status,
                                candidates=[dict(id=i, distance_m=d) for i, d in candidates]))
    hotspots = [score_location(indexed[i][0], group) for i, group in groups.items() if len(group) >= 2]
    hotspots.sort(key=lambda h: (-h['scor'], h['crossing_id']))
    statistics = {i: dict(noapte=sum(e.get('noapte') is True for e in group),
                         zi=sum(e.get('noapte') is False for e in group),
                         necunoscut=sum(e.get('noapte') is None for e in group),
                         cauze=dict(Counter(e.get('cauza_raportata') or 'necunoscut' for e in group)))
                  for i, group in groups.items()}
    return hotspots, dict(associations=diagnostics, statistics=statistics,
                          warning='Asocieri provizorii prin proximitate; necesită verificare. Scorul nu este probabilitate.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Directory containing schema 2.0 synthetic snapshot')
    parser.add_argument('--output', type=Path, default=Path('risk/output/synthetic'))
    args = parser.parse_args()
    def read(name):
        return json.loads((args.input / name).read_text(encoding='utf-8-sig'))
    manifest = read('manifest.json')
    if manifest.get('schema_version') != '2.0' or manifest.get('data_mode') != 'synthetic':
        parser.error('This initial runner accepts synthetic schema 2.0 only; observed integration pending')
    if args.output.resolve() == args.input.resolve():
        parser.error('Output must differ from input')
    hotspots, report = analyze(read('accidents.json'), read('crossings.geojson'))
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in [('hotspots.json', hotspots), ('analysis_report.json', dict(data_mode='synthetic', **report))]:
        path = args.output / name
        with path.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
