"""Read-only checks for municipal exports; rebuild from cache without network."""
import argparse
import json
from pathlib import Path

from shapely.geometry import Point, shape

from context.collect import fetch
from context.city import BOUNDARY_QUERY, boundary_from, collection_jobs, build


def validate(directory, cache):
    directory = Path(directory)
    documents = {name: json.loads((directory / f'{name}.{suffix}').read_text(encoding='utf-8'))
                 for name, suffix in [('crossings', 'geojson'), ('zones', 'geojson'),
                                       ('boundary', 'geojson'), ('geometry_report', 'json')]}
    boundary_payload, _ = fetch(BOUNDARY_QUERY, cache, offline=True)
    _, boundary = boundary_from(boundary_payload)
    payloads = [fetch(j['query'], cache, offline=True)[0] for j in collection_jobs(boundary)]
    rebuilt = json.loads(json.dumps(build(boundary_payload, payloads), allow_nan=False))
    if rebuilt != documents:
        raise ValueError('Saved output differs from an offline rebuild using current code')
    features = documents['crossings']['features']
    ids = [f['properties']['id'] for f in features]
    assigned = [identifier for zone in documents['zones']['features'] for identifier in zone['properties']['crossing_ids']]
    if len(ids) != len(set(ids)) or sorted(assigned) != sorted(ids):
        raise ValueError('Duplicate/missing crossing or zone assignment')
    wgs_boundary = shape(documents['boundary']['geometry'])
    for f in features:
        # Micrometre tolerance for projection/roundtrip precision at the boundary.
        if not wgs_boundary.buffer(1e-10).covers(Point(f['geometry']['coordinates'])):
            raise ValueError('Crossing outside municipality')
        for key in ('semafor', 'iluminat', 'scoala_150m', 'statie_100m'):
            value = f['properties'][key]
            if value is not None and type(value) is not bool:
                raise ValueError(f'Invalid tri-state value: {key}')
    if any(not shape(z['geometry']).is_valid or 'scor' in z['properties'] for z in documents['zones']['features']):
        raise ValueError('Invalid zone geometry or unexpected score')
    if abs(sum(z['properties']['area_m2'] for z in documents['zones']['features']) - boundary.area) > 2:
        raise ValueError('Zone areas do not cover the municipality')
    return dict(status='ok', network_requests=0, crossings=len(ids), zones=len(documents['zones']['features']),
                offline_rebuild='identical', unique_zone_assignment=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('context/output/observed/iasi'))
    parser.add_argument('--cache', type=Path, default=Path('context/cache/iasi'))
    args = parser.parse_args()
    print(json.dumps(validate(args.input, args.cache), indent=2))


if __name__ == '__main__':
    main()
