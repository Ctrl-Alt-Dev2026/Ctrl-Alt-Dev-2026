"""Municipal OSM collection and descriptive 1 km infrastructure profiles, no risk score."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import time

import requests

from pyproj import Transformer
from shapely.geometry import Point, box, mapping
from shapely import transform as shapely_transform

from context.collect import ENDPOINT, fetch, queries
from context.enrich import enrich, geometry
from risk.pipeline import point

TO_WGS84 = Transformer.from_crs(32635, 4326, always_xy=True).transform


def transform(func, geom):
    return shapely_transform(geom, func, interleaved=False)
BOUNDARY_BOX = (47.0, 27.3, 47.4, 27.9)
# Candidate ID is verified against the returned tags and geometry before use.
BOUNDARY_QUERY = '[out:json][timeout:30];rel(1207838);out geom;'


def boundary_from(payload):
    candidates = payload['response']['elements']
    if len(candidates) != 1:
        raise ValueError(f'Expected exactly one municipality, found {len(candidates)}; inspect boundary cache')
    element = candidates[0]
    tags = element.get('tags', {})
    if (element.get('type') != 'relation' or tags.get('boundary') != 'administrative'
            or tags.get('admin_level') != '8' or tags.get('name', '').replace('ş', 'ș') != 'Iași'):
        raise ValueError('Boundary does not identify municipality Iași at admin level 8')
    # Administrative boundary relations use the same outer/inner topology as multipolygons.
    candidate = dict(element, tags=dict(element['tags'], type='multipolygon'))
    geom = geometry(candidate)
    if not geom.is_valid or geom.is_empty or not geom.covers(Point(point(27.5877, 47.1564))):
        raise ValueError('Invalid municipality polygon or Palas is outside it')
    return element, geom


def tiles(boundary, size=5000, margin=200):
    xmin, ymin, xmax, ymax = boundary.bounds
    for x in range(math.floor(xmin / size) * size, math.ceil(xmax / size) * size, size):
        for y in range(math.floor(ymin / size) * size, math.ceil(ymax / size) * size, size):
            core = box(x, y, x + size, y + size)
            if not boundary.intersects(core):
                continue
            bounds = transform(TO_WGS84, core.buffer(margin).envelope).bounds
            west, south, east, north = bounds
            yield dict(id=f'tile-{x}-{y}', bbox=[south, west, north, east])


def tile_queries(bbox):
    result = queries(bbox)
    b = ','.join(map(str, bbox))
    return {'crossings': f'[out:json][timeout:30];node["highway"="crossing"]({b});out body;', **result}


def collection_jobs(boundary):
    # Keep large road geometries tiled. Crossings/POIs are small enough for one
    # city-envelope query per layer, avoiding dozens of tiny duplicate requests.
    west, south, east, north = transform(TO_WGS84, boundary.buffer(200).envelope).bounds
    municipal_bbox = [south, west, north, east]
    jobs = [dict(id='municipality-' + layer, layer=layer, bbox=municipal_bbox, query=query)
            for layer, query in tile_queries(municipal_bbox).items() if layer != 'roads']
    jobs.extend(dict(id=t['id'] + '-roads', layer='roads', bbox=t['bbox'],
                     query=tile_queries(t['bbox'])['roads']) for t in tiles(boundary))
    return jobs


def fetch_job(job, args):
    for attempt in range(3):
        try:
            return fetch(job['query'], args.cache, args.endpoint, args.offline, job['bbox'])
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if args.offline or attempt == 2 or status not in (None, 429, 500, 502, 503, 504):
                raise
            delay = 5 * 2 ** attempt
            print(f"{job['id']}: transient HTTP/network error {status}; retry {attempt+1}/2 in {delay}s", flush=True)
            time.sleep(delay)


def merge_payloads(payloads):
    """Deduplicate overlapping tiles; inconsistent snapshots require a new run, not guessing."""
    merged = {}
    for payload in payloads:
        for e in payload['response']['elements']:
            key = (e['type'], e['id'])
            if key in merged and merged[key] != e:
                raise ValueError(f'Conflicting OSM snapshots for {key}; use a fresh cache directory')
            merged[key] = e
    return sorted(merged.values(), key=lambda e: (e['type'], e['id']))


def partition(elements):
    roads, schools, stops, crossings = [], [], [], []
    for e in elements:
        tags = e.get('tags', {})
        if e['type'] == 'way' and 'highway' in tags:
            roads.append(e)
        if tags.get('amenity') in ('school', 'kindergarten'):
            schools.append(e)
        if (tags.get('highway') == 'bus_stop' or tags.get('public_transport') in ('platform', 'stop_position')
                or tags.get('railway') == 'tram_stop'):
            stops.append(e)
        if e['type'] == 'node' and tags.get('highway') == 'crossing':
            crossings.append(e)
    return dict(roads=roads, schools=schools, stops=stops), crossings


def speed_profile(roads):
    """Only an explicit numeric maxspeed with consensus is a numeric limit here."""
    raw = [{'id': r['id'], 'tags': {k: v for k, v in r['tags'].items()
                                   if k.startswith('maxspeed') or k in ('source:maxspeed', 'zone:maxspeed')}}
           for r in roads]
    values = [r['tags'].get('maxspeed') for r in roads]
    if not values or any(v is None for v in values):
        return dict(maxspeed_kmh=None, status='missing_or_partial', evidence=raw)
    if len(set(values)) != 1:
        return dict(maxspeed_kmh=None, status='conflicting', evidence=raw)
    value = values[0]
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?(?: km/h)?', value):
        return dict(maxspeed_kmh=None, status='symbolic_or_conditional', evidence=raw)
    # Directional or conditional tags can override the general value; retain raw evidence.
    overrides = ('maxspeed:conditional', 'maxspeed:forward', 'maxspeed:backward', 'maxspeed:lanes')
    if any(any(k.startswith(overrides) for k in r['tags']) for r in roads):
        return dict(maxspeed_kmh=None, status='directional_or_conditional', evidence=raw)
    return dict(maxspeed_kmh=float(value.removesuffix(' km/h')), status='explicit_numeric', evidence=raw)


def zone_profiles(boundary, crossings, report, size=1000):
    evidence = {c['id']: c for c in report['crossings']}
    groups = {}
    for f in crossings['features']:
        x, y = point(*f['geometry']['coordinates'])
        key = (math.floor(x / size) * size, math.floor(y / size) * size)
        groups.setdefault(key, []).append(f)
    zones = []
    xmin, ymin, xmax, ymax = boundary.bounds
    for x in range(math.floor(xmin / size) * size, math.ceil(xmax / size) * size, size):
        for y in range(math.floor(ymin / size) * size, math.ceil(ymax / size) * size, size):
            clipped = boundary.intersection(box(x, y, x + size, y + size))
            if clipped.is_empty or clipped.area == 0:
                continue
            features = groups.get((x, y), [])
            props = [f['properties'] for f in features]
            speeds = [evidence[p['id']]['speed']['maxspeed_kmh'] for p in props]
            unknowns = {field: sum(p.get(field) is None for p in props)
                        for field in ('semafor', 'benzi', 'iluminat', 'tip_strada', 'scoala_150m', 'statie_100m')}
            center_lon, center_lat = TO_WGS84(clipped.representative_point().x, clipped.representative_point().y)
            road_names = sorted({r['tags']['name'] for p in props for r in evidence[p['id']]['roads']
                                 if r['tags'].get('name')})
            zones.append(dict(type='Feature', geometry=mapping(transform(TO_WGS84, clipped)), properties=dict(
                id=f'utm35n-{size}-{x}-{y}', zone_type='metric_grid_clipped_to_municipality',
                reference_lon=center_lon, reference_lat=center_lat,
                mapped_road_names=road_names,
                area_m2=round(clipped.area, 2), crossing_ids=[p['id'] for p in props],
                mapped_crossings=len(props), traffic_signals_known=sum(p['semafor'] is True for p in props),
                no_traffic_signals_confirmed=sum(p['semafor'] is False for p in props),
                lighting_known_yes=sum(p['iluminat'] is True for p in props),
                lighting_known_no=sum(p['iluminat'] is False for p in props),
                unsignalized_4plus_lanes=sum(p['semafor'] is False and type(p['benzi']) is int and p['benzi'] >= 4 for p in props),
                school_within_150m=sum(p['scoala_150m'] is True for p in props),
                stop_within_100m=sum(p['statie_100m'] is True for p in props),
                missing_fields=unknowns,
                field_coverage_percent={key: round(100 * (len(props) - value) / len(props), 1) if props else None
                                        for key, value in unknowns.items()},
                lanes_distribution=dict(Counter(str(p['benzi']) for p in props if p['benzi'] is not None)),
                road_type_distribution=dict(Counter(p['tip_strada'] for p in props if p['tip_strada'] is not None)),
                explicit_speed_limits_kmh=dict(Counter(str(v) for v in speeds if v is not None)),
                unknown_speed=sum(v is None for v in speeds),
                data_status='mapped_crossings_present' if props else 'no_mapped_crossings_not_evidence_of_safety')))
    return dict(type='FeatureCollection', features=zones)


def build(boundary_payload, tile_payloads):
    element, boundary = boundary_from(boundary_payload)
    layers, nodes = partition(merge_payloads(tile_payloads))
    inside = [n for n in nodes if boundary.covers(Point(point(n['lon'], n['lat'])))]
    source = dict(type='FeatureCollection', features=[dict(type='Feature',
        geometry=dict(type='Point', coordinates=[n['lon'], n['lat']]),
        properties=dict(n.get('tags', {}), osm_id=n['id'])) for n in inside])
    dates = sorted(p['fetched_at'] for p in tile_payloads)
    envelope = dict(endpoint='multiple_cached_tiles', fetched_at=dates[-1], bbox=None)
    payloads = {k: dict(envelope, response=dict(elements=v, osm3s=dict(timestamp_osm_base='see_collection_sources')))
                for k, v in layers.items()}
    output, report = enrich(source, payloads, dates[0][:10])
    report.update(area='Municipiul Iași — OSM administrative boundary', boundary_relation_id=element['id'],
                  boundary_tags=element['tags'], outside_crossings_removed=len(nodes) - len(inside),
                  boundary_source={k: boundary_payload[k] for k in ('endpoint', 'fetched_at', 'query')},
                  collection_sources=[dict(fetched_at=p['fetched_at'], bbox=p['bbox'], endpoint=p['endpoint'],
                     query_hash=hashlib.sha256(p['query'].encode()).hexdigest(),
                     timestamp_osm_base=p['response']['osm3s']['timestamp_osm_base']) for p in tile_payloads],
                  collection_date_range=[dates[0], dates[-1]])
    # Preserve each crossing's collection date even if the collection spans multiple days.
    node_dates = {}
    for p in tile_payloads:
        for e in p['response']['elements']:
            if e['type'] == 'node' and e.get('tags', {}).get('highway') == 'crossing':
                node_dates.setdefault(e['id'], p['fetched_at'][:10])
    for f, c in zip(output['features'], report['crossings']):
        f['properties']['descarcat_la'] = node_dates[int(f['properties']['id'].removeprefix('osm-node-'))]
        c['speed'] = speed_profile(c['roads'])
        if c['rejected_roads']:
            c['speed']['maxspeed_kmh'] = None
            c['speed']['status'] = 'rejected_road_geometry'
    zones = zone_profiles(boundary, output, report)
    report['summary'].update(zones=len(zones['features']), area_km2=round(boundary.area / 1e6, 3),
                            explicit_numeric_speed=sum(c['speed']['maxspeed_kmh'] is not None for c in report['crossings']))
    if sum(z['properties']['mapped_crossings'] for z in zones['features']) != len(output['features']):
        raise ValueError('Zone assignment did not preserve the crossing count')
    boundary_geojson = dict(type='Feature', geometry=mapping(transform(TO_WGS84, boundary)),
                           properties=dict(osm_relation_id=element['id'], **element['tags']))
    return dict(crossings=output, geometry_report=report, zones=zones, boundary=boundary_geojson)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('context/cache/iasi'))
    parser.add_argument('--endpoint', default=ENDPOINT)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--boundary-only', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('context/output/observed/iasi'))
    args = parser.parse_args()
    boundary_payload, _ = fetch(BOUNDARY_QUERY, args.cache, args.endpoint, args.offline, BOUNDARY_BOX)
    element, boundary = boundary_from(boundary_payload)
    planned = list(tiles(boundary))
    jobs = collection_jobs(boundary)
    print(json.dumps(dict(boundary_relation=element['id'], tags=element['tags'], area_km2=boundary.area / 1e6,
                         road_tiles=len(planned), requests=len(jobs)), ensure_ascii=True), flush=True)
    if args.boundary_only:
        return
    if args.output.exists():
        parser.error('Output exists; choose a new directory')
    payloads = []
    failures = []
    for i, job in enumerate(jobs):
        try:
            p, hit = fetch_job(job, args)
        except (requests.RequestException, ValueError, FileNotFoundError) as exc:
            failures.append(dict(id=job['id'], error=str(exc)))
            print(f"{i+1}/{len(jobs)} {job['id']}: unavailable; remaining jobs will still be cached", flush=True)
            continue
        payloads.append(p)
        print(f"{i+1}/{len(jobs)} {job['id']}: {len(p['response']['elements'])} objects; cache={'hit' if hit else 'saved'}", flush=True)
        if not hit:
            time.sleep(2)
    if failures:
        raise RuntimeError('Municipal export not published; missing jobs: ' + ', '.join(f['id'] for f in failures))
    outputs = build(boundary_payload, payloads)
    args.output.mkdir(parents=True)
    for name, data in outputs.items():
        suffix = 'json' if name == 'geometry_report' else 'geojson'
        (args.output / f'{name}.{suffix}').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    # A flat companion for review by the team; no change to shared contracts.
    fields = ['id', 'reference_lon', 'reference_lat', 'mapped_crossings', 'traffic_signals_known',
              'no_traffic_signals_confirmed', 'unsignalized_4plus_lanes', 'school_within_150m',
              'stop_within_100m', 'unknown_speed', 'data_status', 'mapped_road_names']
    with (args.output / 'zones.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for feature in outputs['zones']['features']:
            row = {key: feature['properties'][key] for key in fields}
            row['mapped_road_names'] = '; '.join(row['mapped_road_names'])
            writer.writerow(row)
    print(json.dumps(outputs['geometry_report']['summary'], ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
