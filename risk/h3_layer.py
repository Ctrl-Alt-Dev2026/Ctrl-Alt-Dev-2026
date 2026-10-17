"""Resolution 9 visual aggregation of eligible event coordinates, no context score."""
from collections import defaultdict

import h3

from risk.pipeline import point
from risk.statistics import unique_events, event_statistics


def aggregate(events, data_mode):
    if data_mode not in ('synthetic', 'observed'):
        raise ValueError('Explicit synthetic or observed mode required')
    groups, excluded = defaultdict(list), []
    for e in unique_events(events):
        if e.get('in_iasi') is not True or e.get('precizie_loc') not in ('trecere', 'intersectie', 'segment'):
            excluded.append(e['event_id'])
            continue
        point(e.get('lon'), e.get('lat'))
        cell = h3.latlng_to_cell(e['lat'], e['lon'], 9)
        groups[cell].append(e)
    features = []
    for cell, group in sorted(groups.items()):
        ring = [[lon, lat] for lat, lon in h3.cell_to_boundary(cell)]
        ring.append(ring[0])
        lat, lon = h3.cell_to_latlng(cell)
        features.append(dict(type='Feature', geometry=dict(type='Polygon', coordinates=[ring]),
                             properties=dict(h3=cell, resolution=9, data_mode=data_mode,
                                 lat=lat, lon=lon, event_ids=[e['event_id'] for e in group],
                                 **event_statistics(group))))
    return dict(type='FeatureCollection', data_mode=data_mode, resolution=9,
                aggregation='unique_eligible_event_coordinates',
                excluded_event_ids=excluded, features=features)


def attach_hotspot_cells(hotspots):
    return [dict(h, h3=h3.latlng_to_cell(h['lat'], h['lon'], 9)) for h in hotspots]
