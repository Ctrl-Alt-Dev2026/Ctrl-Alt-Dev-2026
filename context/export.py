"""Convert the existing crossing experiment without network requests."""
import argparse
import datetime
import json
from pathlib import Path

from risk.pipeline import point


def crossing_signal(tags):
    legacy = {'traffic_signals': True, 'uncontrolled': False}.get(tags.get('crossing'))
    explicit = {'yes': True, 'no': False}.get(tags.get('crossing:signals'))
    if legacy is not None and explicit is not None and legacy != explicit:
        return None
    return explicit if explicit is not None else legacy


def convert(source, downloaded):
    datetime.date.fromisoformat(downloaded)
    result = []
    seen = set()
    for feature in source['features']:
        tags = feature['properties']
        if tags.get('highway') != 'crossing':
            raise ValueError('Expected actual crossing node')
        if feature['geometry']['type'] != 'Point':
            raise ValueError('Expected Point')
        point(*feature['geometry']['coordinates'])
        identifier = f"osm-node-{tags['osm_id']}"
        if identifier in seen:
            raise ValueError('Duplicate OSM node')
        seen.add(identifier)
        signal = crossing_signal(tags)
        props = dict(id=identifier, tip='trecere', nume=tags.get('name'), semafor=signal,
                     benzi=None, iluminat={'yes': True, 'no': False}.get(tags.get('lit')),
                     tip_strada=None, scoala_150m=None, statie_100m=None,
                     sursa='OSM', descarcat_la=downloaded)
        result.append(dict(type='Feature', geometry=feature['geometry'], properties=props))
    return dict(type='FeatureCollection', features=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('crossings_test.geojson'))
    parser.add_argument('--downloaded', required=True, help='Actual download date YYYY-MM-DD, supplied by operator')
    parser.add_argument('--output', type=Path, default=Path('context/output/observed/crossings.geojson'))
    args = parser.parse_args()
    data = convert(json.loads(args.input.read_text(encoding='utf-8-sig')), args.downloaded)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
