"""Enrich the EXISTING matched street layer; never geocode or match accidents here.

OSM road names already present in the municipal context report describe street
infrastructure only. They are never used to attach an accident to a crossing.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from measures.streets import recommend
from risk.scoring import event_components
from risk.statistics import event_statistics, unique_events

REVISION = 'street-analysis-v1'
PRECISE = {'trecere', 'intersectie', 'segment'}
CONTEXT = Path(__file__).resolve().parents[1] / 'context/output/observed/iasi'


@lru_cache(maxsize=1)
def load_context():
    # Missing context is explicit; never make an absent OSM extract mean zero infrastructure.
    if not (CONTEXT / 'geometry_report.json').exists() or not (CONTEXT / 'crossings.geojson').exists():
        return None
    report = json.loads((CONTEXT / 'geometry_report.json').read_text(encoding='utf-8'))
    crossings = json.loads((CONTEXT / 'crossings.geojson').read_text(encoding='utf-8'))
    return report, crossings


def street_context(names, context):
    if context is None:
        return dict(status='indisponibil', crossing_ids=[], treceri_cartografiate=None,
                    descarcat_la=[], atribute={}, event_ids=[])
    report, crossings = context
    # Exact OSM names from the existing street feature, not another street matcher.
    ids = {c['id'] for c in report['crossings']
           if any(r.get('tags', {}).get('name') in names for r in c['roads'])}
    props = [f['properties'] for f in crossings['features'] if f['properties']['id'] in ids]
    attributes = {}
    for key in ('semafor', 'iluminat', 'scoala_150m', 'statie_100m'):
        attributes[key] = dict(da=sum(p.get(key) is True for p in props),
                               nu=sum(p.get(key) is False for p in props),
                               necunoscut=sum(p.get(key) is None for p in props))
    return dict(status='context_strada_fara_asociere_la_accidente', crossing_ids=sorted(ids),
                treceri_cartografiate=len(props), atribute=attributes,
                descarcat_la=sorted({p['descarcat_la'] for p in props}),
                sursa='OpenStreetMap', event_ids=[])


def analyze_source(events):
    events = unique_events(events)
    stats = event_statistics(events)
    components = event_components(events)
    dates = sorted(e['data_eveniment'] for e in events if e.get('data_eveniment'))
    return dict(**stats, event_ids=[e['event_id'] for e in events],
                scor=sum(components.values()), componente_scor=components,
                perioada=[dates[0], dates[-1]] if dates else [None, None],
                data_necunoscuta=sum(e.get('data_eveniment') is None for e in events),
                neverificate=sum(e.get('verificat') is not True for e in events),
                masuri=recommend(events))


def enrich_dataset(dataset, context=None):
    """Return a copy. Membership, source counts, names and paths come from the existing map layer."""
    from risk.h3_layer import aggregate

    result = deepcopy(dataset)
    events = unique_events(result['accidents'])
    by_id = {e['event_id']: e for e in events}
    context = load_context() if context is None else context
    assigned = set()
    for f in result['streets']['features']:
        p = f['properties']
        analysis = {}
        for source in ('isu', 'presa'):
            group = []
            for identifier in dict.fromkeys(p.get(source + '_event_ids', [])):
                e = by_id[identifier]
                if e.get('in_iasi') is not True or e.get('sursa_tip') != source:
                    raise ValueError(f'Invalid street source membership: {identifier}')
                if identifier in assigned:
                    raise ValueError(f'Event assigned to multiple streets: {identifier}')
                assigned.add(identifier)
                group.append(e)
            analysis[source] = analyze_source(group)
        p['analiza'] = analysis
        p['context_osm'] = street_context(set(p['nume_osm']), context)
    # A geocoder's representative street/city point is not an accident location.
    for e in events:
        if e.get('precizie_loc') not in PRECISE:
            e['lat'] = e['lon'] = None
    result['accidents'] = events
    result['accidents_h3'] = aggregate(events, result['manifest']['data_mode'])
    result['street_analysis'] = dict(revision=REVISION,
        score_formula='N + 4*deces + 2*grav + context', street_context_score=0,
        policy='Surse separate; context OSM descriptiv; niciun amplasament sau număr de lucrări presupus.',
        source_built_at=result.get('built_at'),
        precise_h3_event_count=sum(f['properties']['nr_evenimente'] for f in result['accidents_h3']['features']),
        street_level_event_ids=sorted(e['event_id'] for e in events
            if e.get('in_iasi') is True and e.get('precizie_loc') == 'strada'),
        street_event_ids=sorted(assigned),
        unmatched_street_event_ids=sorted(e['event_id'] for e in events
            if e.get('in_iasi') is True and e.get('precizie_loc') == 'strada' and e['event_id'] not in assigned))
    return result


@lru_cache(maxsize=2)
def enrich_payload(payload):
    """One cached analysis per stored dataset, also upgrades pre-analysis SQLite snapshots."""
    return json.dumps(enrich_dataset(json.loads(payload)), ensure_ascii=False, separators=(',', ':'))
