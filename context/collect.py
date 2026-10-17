"""Small-area Overpass collection with validated, reusable local responses."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import os

import requests

ENDPOINT = 'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
# Original crossing bbox, enlarged by >200 m on every side at Palas latitude.
BBOX = (47.1517, 27.5807, 47.1611, 27.5946)


def queries(bbox=BBOX):
    box = ','.join(map(str, bbox))
    selectors = {
        'roads': f'way["highway"]({box});',
        'schools': f'nwr["amenity"~"^(school|kindergarten)$"]({box});',
        'stops': f'(nwr["highway"="bus_stop"]({box});nwr["public_transport"~"^(platform|stop_position)$"]({box});nwr["railway"="tram_stop"]({box}););',
    }
    return {name: f'[out:json][timeout:30];{selector}out geom;'
            for name, selector in selectors.items()}


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('elements'), list) or data.get('remark'):
        raise ValueError('Incomplete/invalid Overpass response, not cached')
    if not data.get('osm3s', {}).get('timestamp_osm_base'):
        raise ValueError('Missing OSM snapshot timestamp')
    for element in data['elements']:
        if element.get('type') not in ('node', 'way', 'relation') or type(element.get('id')) is not int:
            raise ValueError('Invalid OSM element')
    return data


def fetch(query, directory, endpoint=ENDPOINT, offline=False, bbox=BBOX):
    directory = Path(directory)
    key = hashlib.sha256(query.encode()).hexdigest()
    path = directory / (key + '.json')
    if path.exists():
        cached = json.loads(path.read_text(encoding='utf-8'))
        if cached['query'] != query:
            raise ValueError('Cache query mismatch')
        validate(cached['response'])
        return cached, True
    if offline:
        raise FileNotFoundError(f'No cached response: {key}')
    response = requests.post(endpoint, data={'data': query},
                             headers={'User-Agent': 'SafeIasi-Person4/0.1 (small-area research)'},
                             timeout=(10, 45))
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(f'{exc}; server detail: {response.text[:1000]}', response=response) from exc
    data = validate(response.json())
    cached = dict(query=query, endpoint=endpoint, bbox=list(bbox) if bbox else None,
                  fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(), response=data)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(cached, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)
    return cached, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default=ENDPOINT)
    parser.add_argument('--cache', type=Path, default=Path('context/cache/palas'))
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    for name, query in queries().items():
        cached, hit = fetch(query, args.cache, args.endpoint, args.offline)
        print(f"{name}: {len(cached['response']['elements'])} objects; cache={'hit' if hit else 'saved'}", flush=True)


if __name__ == '__main__':
    main()
