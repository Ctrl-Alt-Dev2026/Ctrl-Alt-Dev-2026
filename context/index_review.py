"""Audit P3's read-only index; prepare junction candidates without changing published context."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import Point, shape

from context.collect import ENDPOINT, fetch
from context.city import BOUNDARY_QUERY, boundary_from, collection_jobs, merge_payloads
from context.enrich import ROADS, poi_index, nearby
from context.export import crossing_signal
from risk.pipeline import point

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def extra_query(extras):
    ids = ','.join(str(int(e['osm'].split('/')[1])) for e in sorted(extras, key=lambda e: e['osm']))
    if not ids:
        raise ValueError('No additional nodes to verify')
    return f'[out:json][timeout:30];node(id:{ids})->.n;(.n;way(bn.n)["highway"];);out geom;'


def blank_properties(identifier, kind, name, downloaded):
    return dict(id=identifier, tip=kind, nume=name, semafor=None, benzi=None,
                iluminat=None, tip_strada=None, scoala_150m=None, statie_100m=None,
                sursa='OSM', descarcat_la=downloaded)


def road_nodes(roads):
    result = defaultdict(list)
    for r in roads:
        if r.get('tags', {}).get('highway') in ROADS and r.get('tags', {}).get('area') != 'yes':
            for identifier in set(r.get('nodes', [])):
                result[identifier].append(r)
    return result


def geometry_evidence(identifier, lon, lat, roads):
    linked, rejected = [], []
    location = point(lon, lat)
    for road in roads:
        nodes, coords = road.get('nodes', []), road.get('geometry', [])
        if identifier not in nodes:
            continue
        try:
            if len(nodes) < 2 or len(nodes) != len(coords):
                raise ValueError('Incomplete way geometry')
            positions = [i for i, n in enumerate(nodes) if n == identifier]
            if any(math.dist(location, point(coords[i]['lon'], coords[i]['lat'])) > 0.5 for i in positions):
                raise ValueError('Node/geometry coordinate conflict >0.5m')
            neighbors = {nodes[j] for i in positions for j in (i-1, i+1) if 0 <= j < len(nodes) and nodes[j] != identifier}
            linked.append(dict(id=road['id'], tags=road.get('tags', {}), neighbors=sorted(neighbors)))
        except (ValueError, KeyError) as exc:
            rejected.append(dict(id=road['id'], reason=str(exc)))
    return linked, rejected


def audit_extras(extras, raw, boundary):
    nodes = {e['id']: e for e in raw['response']['elements'] if e['type'] == 'node'}
    road_index = road_nodes([e for e in raw['response']['elements'] if e['type'] == 'way'])
    rows, candidates, accepted = [], [], []
    for e in extras:
        identifier = int(e['osm'].split('/')[1])
        node = nodes.get(identifier)
        row = dict(osm=e['osm'], index_observation=e, url=f'https://www.openstreetmap.org/node/{identifier}')
        if node is None:
            row['status'] = 'missing_in_verification_response'
            rows.append(row)
            continue
        tags = node.get('tags', {})
        row.update(raw_tags=tags, coordinates=[node['lon'], node['lat']])
        distance = math.dist(point(e['lon'], e['lat']), point(node['lon'], node['lat']))
        row['index_coordinate_difference_m'] = distance
        linked, rejected = geometry_evidence(identifier, node['lon'], node['lat'], road_index[identifier])
        row.update(roads=linked, rejected_roads=rejected)
        if not boundary.covers(Point(node['lon'], node['lat'])):
            status = 'outside_municipality'
        elif tags.get('crossing') == 'no':
            status = 'excluded_explicit_crossing_no'
        elif tags.get('crossing') == 'informal':
            status = 'excluded_informal_not_formal_crossing'
        elif distance > 0.5 or rejected:
            status = 'coordinate_or_way_conflict_review_required'
        elif tags.get('highway') == 'crossing' and linked:
            status = 'confirmed_highway_crossing'
            accepted.append(dict(type='Feature', geometry=dict(type='Point', coordinates=[node['lon'], node['lat']]),
                properties=dict(osm_id=identifier, **tags)))
        elif (tags.get('crossing') == 'traffic_signals' and tags.get('crossing:markings') in ('yes', 'zebra')
                and crossing_signal(tags) is True and linked):
            status = 'confirmed_legacy_signalized_crossing'
            accepted.append(dict(type='Feature', geometry=dict(type='Point', coordinates=[node['lon'], node['lat']]),
                properties=dict(osm_id=identifier, **tags)))
        elif tags.get('crossing') in ('traffic_signals', 'marked', 'uncontrolled', 'unmarked'):
            status = 'alternative_tagging_review_required'
            candidates.append(dict(type='Feature', geometry=dict(type='Point', coordinates=[node['lon'], node['lat']]),
                properties=blank_properties(f'osm-node-{identifier}', 'trecere',
                    f'CANDIDAT DE VERIFICAT — node/{identifier}', raw['fetched_at'][:10])))
        else:
            status = 'not_confirmed_as_crossing'
        row['status'] = status
        rows.append(row)
    return dict(type='FeatureCollection', features=candidates), rows, accepted


def normalize_additions(accepted, rows, school_elements, stop_elements, downloaded):
    schools, rejected_schools = poi_index([e for e in school_elements if e.get('tags', {}).get('amenity') == 'school'])
    stops, rejected_stops = poi_index(stop_elements)
    evidence = {r['osm']: r for r in rows}
    features = []
    for source in accepted:
        tags = source['properties']
        identifier = tags['osm_id']
        row = evidence[f'node/{identifier}']
        roads = row['roads']
        names = sorted({r['tags']['name'] for r in roads if r['tags'].get('name')})
        props = blank_properties(f'osm-node-{identifier}', 'trecere', ' / '.join(names) or None, downloaded)
        props['semafor'] = crossing_signal(tags)
        props['iluminat'] = {'yes': True, 'no': False}.get(tags.get('lit'))
        def consensus(key):
            values = [r['tags'].get(key) for r in roads]
            return values[0] if values and values[0] is not None and len(set(values)) == 1 else None
        lanes = consensus('lanes')
        props['benzi'] = int(lanes) if isinstance(lanes, str) and lanes.isascii() and lanes.isdigit() and int(lanes) > 0 else None
        props['tip_strada'] = consensus('highway')
        location = Point(point(*source['geometry']['coordinates']))
        row['schools_150m'] = nearby(location, schools, 150)
        row['stops_100m'] = nearby(location, stops, 100)
        props['scoala_150m'] = True if row['schools_150m'] else None
        props['statie_100m'] = True if row['stops_100m'] else None
        features.append(dict(type='Feature', geometry=source['geometry'], properties=props))
    return dict(type='FeatureCollection', features=features), rejected_schools + rejected_stops


def junctions(index, boundary, roads, existing_crossing_ids):
    refs, neighbors = defaultdict(dict), defaultdict(set)
    for key, components in index['strazi'].items():
        for number, c in enumerate(components):
            if not set(c.get('highway', [])).intersection(ROADS):
                continue
            for u, v in c['segmente']:
                if u == v:
                    continue
                for n, other in ((int(u), int(v)), (int(v), int(u))):
                    if str(n) not in index['noduri'] or str(other) not in index['noduri']:
                        raise ValueError('Index segment references missing coordinates')
                    neighbors[n].add(other)
                    refs[n][(key, number)] = dict(street_key=key, name=c['nume'], way_ids=c['way_ids'])
    by_node = road_nodes(roads)
    features, evidence, counts = [], [], Counter()
    for identifier, components in sorted(refs.items()):
        street_keys = {k[0] for k in components}
        if len(street_keys) < 2 or len(neighbors[identifier]) < 3:
            continue
        lat, lon = index['noduri'][str(identifier)]
        point(lon, lat)
        if not boundary.covers(Point(lon, lat)):
            continue
        linked, rejected = geometry_evidence(identifier, lon, lat, by_node[identifier])
        linked_ids = {r['id'] for r in linked}
        matched_streets = {c['street_key'] for c in components.values() if linked_ids.intersection(c['way_ids'])}
        linked_neighbors = {n for r in linked for n in r['neighbors']}
        layer_values = {r['tags'].get('layer', '0') for r in linked}
        status = ('shared_node_geometry_verified' if len(matched_streets) >= 2 and len(linked_neighbors) >= 3
                  and not rejected and len(layer_values) == 1 else 'index_only_or_conflicting_geometry')
        counts[status] += 1
        crossing_id = f'osm-node-{identifier}'
        coincident = crossing_id if crossing_id in existing_crossing_ids else None
        names = sorted({c['name'] for c in components.values()})
        props = blank_properties(f'osm-junction-node-{identifier}', 'intersectie', ' × '.join(names),
                                 index['meta']['descarcat_la'][:10])
        if status == 'shared_node_geometry_verified' and coincident is None:
            features.append(dict(type='Feature', geometry=dict(type='Point', coordinates=[lon, lat]), properties=props))
        evidence.append(dict(id=props['id'], osm_node_id=identifier, coordinates=[lon, lat],
            status=status, manual_review_required=True, coincident_crossing_id=coincident,
            index_degree=len(neighbors[identifier]), verified_degree=len(linked_neighbors),
            streets=[dict(key=k, name=c['name']) for (k, _), c in components.items()],
            roads=linked, rejected_roads=rejected, layer_values=sorted(layer_values),
            url=f'https://www.openstreetmap.org/node/{identifier}'))
    return dict(type='FeatureCollection', features=features), evidence, dict(counts)


def prepare(index_path, city, cache, verification_cache, endpoint=ENDPOINT, online=False):
    index = json.loads(gzip.decompress(Path(index_path).read_bytes()))
    if index['meta']['versiune_index'] != 1:
        raise ValueError('Unsupported P3 index version')
    original = read(Path(city) / 'crossings.geojson')
    boundary = shape(read(Path(city) / 'boundary.geojson')['geometry'])
    original_ids = {f['properties']['id'] for f in original['features']}
    extras = [e for e in index['treceri'] if 'osm-' + e['osm'].replace('/', '-') not in original_ids
              and boundary.covers(Point(e['lon'], e['lat']))]
    raw, hit = fetch(extra_query(extras), verification_cache, endpoint, offline=not online, bbox=None)
    candidates, extra_rows, accepted = audit_extras(extras, raw, boundary)
    boundary_cache, _ = fetch(BOUNDARY_QUERY, cache, offline=True)
    _, projected = boundary_from(boundary_cache)
    jobs = collection_jobs(projected)
    road_payloads = [fetch(j['query'], cache, offline=True)[0] for j in jobs if j['layer'] == 'roads']
    roads = merge_payloads(road_payloads)
    poi_payloads = {j['layer']: fetch(j['query'], cache, offline=True)[0] for j in jobs if j['layer'] in ('schools', 'stops')}
    additions, rejected_pois = normalize_additions(accepted, extra_rows, poi_payloads['schools']['response']['elements'],
                                                  poi_payloads['stops']['response']['elements'], raw['fetched_at'][:10])
    all_crossing_ids = original_ids | {f['properties']['id'] for f in additions['features']}
    intersection_geojson, intersection_rows, counts = junctions(index, boundary, roads, all_crossing_ids)
    paths = [Path(index_path), Path(city) / 'boundary.geojson', Path(city) / 'crossings.geojson']
    report = dict(data_mode='observed', scope='review_candidates_not_published',
        original_crossing_count=len(original['features']), index_crossings=len(index['treceri']),
        extra_crossings=extra_rows, extra_status_counts=dict(Counter(r['status'] for r in extra_rows)),
        confirmed_extra_crossings=len(accepted), intersection_status_counts=counts,
        extended_crossing_count_if_integrated=len(all_crossing_ids), rejected_pois=rejected_pois,
        exported_intersection_candidates=len(intersection_geojson['features']),
        coincident_crossing_candidates=sum(r['coincident_crossing_id'] is not None for r in intersection_rows),
        intersections=intersection_rows, raw_verification_source={k: raw[k] for k in ('endpoint', 'query', 'fetched_at')},
        verification_snapshot=raw['response']['osm3s']['timestamp_osm_base'],
        road_cache_sources=[dict(endpoint=p['endpoint'], fetched_at=p['fetched_at'],
            query_sha256=hashlib.sha256(p['query'].encode()).hexdigest(),
            timestamp_osm_base=p['response']['osm3s']['timestamp_osm_base']) for p in road_payloads],
        policy='Shared OSM node + degree>=3 + two named streets + compatible cached geometry; human review still required. No centroid clustering.',
        attribution='© OpenStreetMap contributors, ODbL 1.0',
        sources=[dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
    return {'review_report.json': report, 'intersection_candidates.geojson': intersection_geojson,
            'additional_crossings.geojson': additions,
            'crossing_candidates.geojson': candidates,
            'confirmed_additional_crossings_raw.geojson': dict(type='FeatureCollection', features=accepted)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=ROOT / 'coordonate/date_referinta/osm/index_osm.json.gz')
    parser.add_argument('--city', type=Path, default=ROOT / 'context/output/observed/iasi')
    parser.add_argument('--cache', type=Path, default=ROOT / 'context/cache/iasi')
    parser.add_argument('--verification-cache', type=Path, default=ROOT / 'context/cache/index-review')
    parser.add_argument('--output', type=Path, default=ROOT / 'context/output/observed/index-review-complete')
    parser.add_argument('--endpoint', default=ENDPOINT)
    parser.add_argument('--online', action='store_true', help='Allow only the three extra-node verification query when not cached')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; choose a new directory')
    result = prepare(args.index, args.city, args.cache, args.verification_cache, args.endpoint, args.online)
    args.output.mkdir(parents=True)
    for name, data in result.items():
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    report = result['review_report.json']
    fields = ['id', 'osm_node_id', 'status', 'manual_review_required', 'coincident_crossing_id', 'url']
    with (args.output / 'intersection_review.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in report['intersections'])
    print(json.dumps({k: report[k] for k in ('extra_status_counts', 'confirmed_extra_crossings',
                     'intersection_status_counts', 'exported_intersection_candidates', 'coincident_crossing_candidates')}, indent=2))


if __name__ == '__main__':
    main()
