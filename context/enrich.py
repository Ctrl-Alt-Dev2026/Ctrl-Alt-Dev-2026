"""Join cached OSM geometry to existing crossing nodes; keep evidence separately."""
import argparse
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path

from shapely.geometry import Point, LineString, Polygon
from shapely.ops import polygonize, unary_union
from shapely.errors import GEOSException

from context.collect import fetch, queries
from context.export import convert
from risk.pipeline import point

ROADS = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
         'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified',
         'residential', 'living_street', 'service', 'road'}


def line(coords):
    if not coords or len(coords) < 2:
        raise ValueError('Missing line geometry')
    return LineString([point(c['lon'], c['lat']) for c in coords])


def geometry(element):
    kind = element['type']
    if kind == 'node':
        return Point(point(element['lon'], element['lat']))
    if kind == 'way':
        geom = line(element.get('geometry'))
        if element.get('nodes', [0, 1])[0] == element.get('nodes', [0, 1])[-1]:
            geom = Polygon(geom.coords)
        return geom
    if element.get('tags', {}).get('type') != 'multipolygon':
        raise ValueError('Unsupported relation; no center approximation')
    rings = {'outer': [], 'inner': []}
    for member in element.get('members', []):
        if member.get('role') in rings and member['type'] == 'way':
            rings[member['role']].append(line(member.get('geometry')))
    outer = list(polygonize(rings['outer']))
    if not outer:
        raise ValueError('Incomplete multipolygon')
    # Every member segment must participate in a closed ring.
    for role, segments in rings.items():
        if segments and not unary_union(segments).difference(unary_union(list(polygonize(segments))).boundary).is_empty:
            raise ValueError('Unclosed multipolygon member')
    return unary_union(outer).difference(unary_union(list(polygonize(rings['inner']))))


def poi_index(elements):
    valid, rejected = [], []
    for e in elements:
        try:
            g = geometry(e)
            if g.is_empty or not g.is_valid:
                raise ValueError('Invalid geometry')
            if e.get('tags', {}).get('amenity') in ('school', 'kindergarten') and g.geom_type in ('LineString', 'MultiLineString'):
                raise ValueError('Open school boundary; not approximated as a polygon')
            valid.append((e, g))
        except (ValueError, KeyError, TypeError, GEOSException) as exc:
            rejected.append(dict(type=e['type'], id=e['id'], reason=str(exc)))
    return valid, rejected


def nearby(location, objects, threshold):
    matches = []
    for e, geom in objects:
        distance = location.distance(geom)
        if distance < threshold:
            matches.append(dict(type=e['type'], id=e['id'], name=e.get('tags', {}).get('name'),
                                amenity=e.get('tags', {}).get('amenity'), distance_m=round(distance, 3)))
    return sorted(matches, key=lambda m: (m['distance_m'], m['type'], m['id']))


def enrich(source, payloads, crossing_downloaded):
    output = convert(source, crossing_downloaded)
    roads = payloads['roads']['response']['elements']
    roads_by_node = defaultdict(list)
    for road in roads:
        if road.get('tags', {}).get('highway') in ROADS:
            for node_id in set(road.get('nodes', [])):
                roads_by_node[node_id].append(road)
    # Kindergarten proximity is retained as evidence but is not a school-score bonus.
    school_elements = payloads['schools']['response']['elements']
    schools, school_rejected = poi_index([e for e in school_elements if e.get('tags', {}).get('amenity') == 'school'])
    kindergartens, kinder_rejected = poi_index([e for e in school_elements if e.get('tags', {}).get('amenity') == 'kindergarten'])
    stops, stops_rejected = poi_index(payloads['stops']['response']['elements'])
    report = dict(data_mode='observed', area='Palas pilot', crs='EPSG:32635',
                  crossing_downloaded=crossing_downloaded,
                  attribution='© OpenStreetMap contributors, ODbL 1.0; https://www.openstreetmap.org/copyright',
                  sources={k: {field: v[field] for field in ('endpoint', 'fetched_at', 'bbox')} |
                           {'timestamp_osm_base': v['response']['osm3s']['timestamp_osm_base']}
                           for k, v in payloads.items()},
                  rejected_pois=school_rejected + kinder_rejected + stops_rejected, crossings=[])
    for original, feature in zip(source['features'], output['features']):
        props = feature['properties']
        location = Point(point(*feature['geometry']['coordinates']))
        osm_id = original['properties']['osm_id']
        linked, rejected = [], []
        for road in roads_by_node[osm_id]:
            tags = road.get('tags', {})
            if tags.get('highway') not in ROADS or osm_id not in road.get('nodes', []):
                continue
            try:
                geom = line(road.get('geometry'))
                # Node identity AND node coordinate agreement, not just nearest line.
                positions = [i for i, n in enumerate(road['nodes']) if n == osm_id]
                if len(road['nodes']) != len(road['geometry']) or any(
                        location.distance(Point(point(road['geometry'][i]['lon'], road['geometry'][i]['lat']))) > 0.5
                        for i in positions) or location.distance(geom) > 0.5:
                    raise ValueError('Node coordinates disagree with original crossing (>0.5 m)')
                linked.append(dict(id=road['id'], tags=copy.deepcopy(tags), distance_m=round(location.distance(geom), 3)))
            except (ValueError, KeyError, IndexError) as exc:
                rejected.append(dict(id=road['id'], reason=str(exc)))
        def consensus(key, parse=lambda v: v):
            values = [parse(r['tags'].get(key)) for r in linked]
            return values[0] if not rejected and values and values[0] is not None and all(v == values[0] for v in values) else None
        props['benzi'] = consensus('lanes', lambda v: int(v) if isinstance(v, str) and v.isascii() and v.isdigit() and int(v) > 0 else None)
        # Preserve the actual OSM highway value; no guessed conversion to "bulevard".
        props['tip_strada'] = consensus('highway')
        school_matches = nearby(location, schools, 150)
        stop_matches = nearby(location, stops, 100)
        props['scoala_150m'] = True if school_matches else None
        props['statie_100m'] = True if stop_matches else None
        report['crossings'].append(dict(id=props['id'], road_status='linked' if linked else 'unresolved',
            crossing_tags=copy.deepcopy(original['properties']),
            roads=linked, rejected_roads=rejected, schools_150m=school_matches,
            kindergartens_150m=nearby(location, kindergartens, 150), stops_100m=stop_matches,
            road_lanes=props['benzi'], road_type=props['tip_strada'],
            note='Road tags describe mapped ways, not a verified full crossing width. Missing POIs remain unknown.'))
        # Road light tags are not proof of dedicated crossing illumination.
    report['summary'] = dict(crossings=len(output['features']),
        road_status=dict(Counter(c['road_status'] for c in report['crossings'])),
        with_lanes=sum(f['properties']['benzi'] is not None for f in output['features']),
        with_school=sum(f['properties']['scoala_150m'] is True for f in output['features']),
        with_stop=sum(f['properties']['statie_100m'] is True for f in output['features']))
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('crossings_test.geojson'))
    parser.add_argument('--crossing-downloaded', required=True)
    parser.add_argument('--cache', type=Path, default=Path('context/cache/palas'))
    parser.add_argument('--output', type=Path, default=Path('context/output/observed/palas'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory already exists; choose a new directory')
    payloads = {name: fetch(query, args.cache, offline=True)[0] for name, query in queries().items()}
    output, report = enrich(json.loads(args.input.read_text(encoding='utf-8-sig')), payloads, args.crossing_downloaded)
    args.output.mkdir(parents=True)
    for name, data in [('crossings.geojson', output), ('geometry_report.json', report)]:
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
