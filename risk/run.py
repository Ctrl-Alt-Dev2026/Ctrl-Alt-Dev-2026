"""Read-only inputs -> E4, H3 r9 and location scores in a new output directory."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from shapely.geometry import Point, shape

from risk.pipeline import analyze, point
from risk.statistics import unique_events, event_statistics
from risk.h3_layer import aggregate, attach_hotspot_cells


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def prepare(input_dir, mode, context_dir=None):
    input_dir = Path(input_dir)
    manifest = load(input_dir / 'manifest.json')
    if manifest.get('schema_version') != '2.0' or manifest.get('data_mode') != mode:
        raise ValueError('Manifest schema/mode mismatch; synthetic and observed cannot be mixed')
    original = load(input_dir / 'accidents.json')
    if not isinstance(original, list) or any(not isinstance(e, dict) for e in original):
        raise ValueError('accidents.json must be an array of events')
    events = unique_events(original)
    context = Path(context_dir) if context_dir else input_dir
    crossings = load(context / 'crossings.geojson')
    features = crossings.get('features', [])
    if crossings.get('type') != 'FeatureCollection' or not isinstance(features, list):
        raise ValueError('Expected crossing FeatureCollection')
    expected_source = 'SINTETIC' if mode == 'synthetic' else 'OSM'
    if any(f.get('properties', {}).get('sursa') != expected_source for f in features):
        raise ValueError('Crossing source does not match data mode')
    for f in features:
        p = f['properties']
        for field in ('semafor', 'iluminat', 'scoala_150m', 'statie_100m'):
            if field not in p or (p[field] is not None and type(p[field]) is not bool):
                raise ValueError(f'Invalid crossing tri-state field: {field}')
        if p.get('benzi') is not None and (type(p['benzi']) is not int or p['benzi'] <= 0):
            raise ValueError('Crossing benzi must be a positive integer or null')
    sources = [input_dir / 'manifest.json', input_dir / 'accidents.json', context / 'crossings.geojson']
    boundary = None
    if mode == 'observed':
        if context_dir is None:
            raise ValueError('Observed run requires --context-dir with observed OSM boundary and crossings')
        context_report = load(context / 'geometry_report.json')
        if context_report.get('data_mode') != 'observed':
            raise ValueError('Expected observed context provenance')
        boundary = shape(load(context / 'boundary.geojson')['geometry'])
        if boundary.is_empty or not boundary.is_valid or boundary.geom_type not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Invalid municipality boundary')
        sources += [context / 'boundary.geojson', context / 'geometry_report.json']
        if any(not boundary.covers(Point(f['geometry']['coordinates'])) for f in features):
            raise ValueError('Context crossing outside municipality boundary')
    accepted, preflight = [], []
    for e in events:
        reason = None
        if e.get('in_iasi') is not True or e.get('precizie_loc') not in ('trecere', 'intersectie', 'segment'):
            reason = 'ineligible_location'
        elif mode == 'observed' and e.get('verificat') is not True:
            reason = 'not_manually_verified'
        else:
            point(e.get('lon'), e.get('lat'))
            event_statistics([e])
            if boundary is not None and not boundary.covers(Point(e['lon'], e['lat'])):
                reason = 'outside_municipality_despite_in_iasi_flag'
        if reason:
            preflight.append(dict(event_id=e['event_id'], status=reason))
        else:
            accepted.append(e)
    hotspots, report = analyze(accepted, crossings)
    hotspots = attach_hotspot_cells(hotspots)
    layer = aggregate(accepted, mode)
    h3_ids = [i for f in layer['features'] for i in f['properties']['event_ids']]
    if sorted(h3_ids) != sorted(e['event_id'] for e in accepted):
        raise ValueError('H3 aggregation lost or duplicated events')
    report.update(data_mode=mode, preflight=preflight,
        input_rows=len(original), unique_events=len(events), eligible_events=len(accepted),
        duplicate_rows_removed=len(original) - len(events),
        event_statistics=event_statistics(accepted),
        association_counts=dict(Counter(a['status'] for a in report['associations'])),
        h3_cells=len(layer['features']),
        policy=dict(observed_requires_manual_verification=True, association_radius_m=50,
                    hotspots_min_events=2, h3_resolution=9,
                    h3_includes_eligible_unmatched_and_ambiguous_events=True),
        sources=[dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources])
    location_stats = dict(data_mode=mode, locations=report['statistics'])
    return {'hotspots.json': hotspots, 'location_statistics.json': location_stats,
            'accidents_h3.geojson': layer, 'analysis_report.json': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--mode', choices=('synthetic', 'observed'), required=True)
    parser.add_argument('--context-dir', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be a new directory; existing data will not be overwritten')
    if args.output.resolve() == args.input.resolve() or (args.context_dir and args.output.resolve() == args.context_dir.resolve()):
        parser.error('Output must differ from inputs')
    try:
        result = prepare(args.input, args.mode, args.context_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True)
    for name, data in result.items():
        with (args.output / name).open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    r = result['analysis_report.json']
    print(json.dumps(dict(data_mode=args.mode, unique_events=r['unique_events'], eligible_events=r['eligible_events'],
                         hotspots=len(result['hotspots.json']), h3_cells=r['h3_cells'],
                         associations=r['association_counts']), indent=2))


if __name__ == '__main__':
    main()
