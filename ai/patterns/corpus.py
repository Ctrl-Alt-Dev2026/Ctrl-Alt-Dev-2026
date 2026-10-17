"""Build event-level profiles with explicit provenance; never invent absent articles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = 1
FILES = ('accidents.json', 'articles.json', 'crossings.geojson', 'hotspots.json')
CAUSES = {
    'viteza': 'Viteză raportată',
    'neacordare_prioritate': 'Neacordare de prioritate raportată',
    'traversare_neregulamentara': 'Traversare neregulamentară raportată',
    'vizibilitate': 'Dificultăți de vizibilitate raportate',
}
FACETS = {
    'night': 'Eveniment noaptea', 'day': 'Eveniment ziua',
    'unsignalized': 'Fără semafor în fixture', 'signalized': 'Cu semafor în fixture',
    'four_lanes': 'Patru benzi în fixture', 'two_lanes': 'Două benzi în fixture',
    'unlit': 'Iluminat absent în fixture', 'lit': 'Iluminat prezent în fixture',
    'school': 'Școală la <150 m în fixture', 'transit': 'Stație la <100 m în fixture',
    **{f'cause:{key}': label for key, label in CAUSES.items()},
}


def digest(directory: Path) -> str:
    result = hashlib.sha256()
    for name in FILES:
        result.update(name.encode())
        result.update((directory / name).read_bytes())
    return result.hexdigest()


def build_corpus(directory: Path) -> dict:
    raw = {name: json.loads((directory / name).read_text(encoding='utf-8-sig')) for name in FILES}
    if any(a.get('sursa') != 'SINTETIC' for a in raw['articles.json']) or any(
        f['properties'].get('sursa') != 'SINTETIC' for f in raw['crossings.geojson']['features']
    ):
        raise ValueError('This demo accepts explicitly labelled SINTETIC fixtures only')
    articles = {a['article_id']: a for a in raw['articles.json']}
    crossings = {f['properties']['id']: f['properties'] for f in raw['crossings.geojson']['features']}
    association = {}
    for hotspot in raw['hotspots.json']:
        for event_id in hotspot['event_ids']:
            if event_id in association and association[event_id] != hotspot['crossing_id']:
                raise ValueError(f'Ambiguous explicit crossing association: {event_id}')
            association[event_id] = hotspot['crossing_id']
    events = []
    seen = set()
    for item in sorted(raw['accidents.json'], key=lambda e: e['event_id']):
        event_id = item['event_id']
        if event_id in seen:
            raise ValueError(f'Duplicate canonical event: {event_id}')
        seen.add(event_id)
        attached = [articles[a] for a in dict.fromkeys(item['article_ids']) if a in articles]
        crossing_id = association.get(event_id)
        crossing = crossings.get(crossing_id, {})
        facts, facets, source_facets, profile = [], [], [], []

        def fact(field, value, label, phrase=None, facet=None, file='accidents.json', pointer=None):
            # All values originate in synthetic files, including their "verified" flags.
            quote = item.get('dovezi', {}).get(field) if file == 'accidents.json' else None
            matches = [a['article_id'] for a in attached if quote and quote in a['text']]
            facts.append({'field': field, 'value': value, 'label': label,
                          'file': file, 'pointer': pointer or f'{event_id}/{field}',
                          'excerpt': quote, 'matched_article_ids': matches,
                          'provenance': 'article_excerpt' if matches else 'synthetic_fixture'})
            if value is not None and phrase:
                profile.append(phrase)
            if value is not None and facet:
                facets.append(facet)
                if matches:
                    source_facets.append(facet)

        cause = item.get('cauza_raportata')
        fact('cauza_raportata', cause, CAUSES.get(cause, 'Cauză raportată necunoscută'),
             CAUSES.get(cause), f'cause:{cause}' if cause in CAUSES else None)
        night = item.get('noapte')
        fact('noapte', night, 'Moment: necunoscut' if night is None else 'Noaptea' if night else 'Ziua',
             None if night is None else 'Incidentul a avut loc noaptea.' if night else 'Incidentul a avut loc ziua.',
             None if night is None else 'night' if night else 'day')
        for field, yes, no, yes_facet, no_facet in (
            ('semafor', 'Traversare cu semafor.', 'Traversare fără semafor.', 'signalized', 'unsignalized'),
            ('iluminat', 'Traversare iluminată.', 'Traversare fără iluminat.', 'lit', 'unlit'),
            ('scoala_150m', 'Școală în apropierea traversării.', None, 'school', None),
            ('statie_100m', 'Stație de transport în apropierea traversării.', None, 'transit', None),
        ):
            value = crossing.get(field)
            phrase = yes if value is True else no if value is False else None
            facet = yes_facet if value is True else no_facet if value is False else None
            fact(field, value, phrase or f'{field}: necunoscut' if value is None else phrase or f'{field}: nu',
                 phrase, facet, 'crossings.geojson', f'{crossing_id or "unassociated"}/{field}')
        lanes = crossing.get('benzi')
        fact('benzi', lanes, f'{lanes} benzi' if lanes else 'Benzi necunoscute',
             f'Traversare pe {lanes} benzi.' if lanes else None,
             'four_lanes' if lanes == 4 else 'two_lanes' if lanes == 2 else None,
             'crossings.geojson', f'{crossing_id or "unassociated"}/benzi')
        # Neither geography, severity, outcomes nor identifiers enter the semantic profile.
        # Unknowns add no semantic content. Source text is displayed, never silently invented.
        source_spans = sorted({f['excerpt'] for f in facts if f['matched_article_ids']})
        events.append({
            'id': event_id, 'location': item['loc_text'], 'site_id': crossing_id,
            'site_name': crossing.get('nume', item['loc_text']),
            'date': item.get('data_eveniment'), 'severity': item.get('gravitate'),
            'lat': item.get('lat'), 'lon': item.get('lon'), 'precision': item.get('precizie_loc'),
            'in_iasi': item.get('in_iasi') is True, 'facts': facts, 'facets': facets,
            'source_facets': source_facets,
            'profile': ' '.join(profile), 'source_profile': ' '.join(source_spans),
            'article_ids': list(dict.fromkeys(item['article_ids'])),
            'articles': [{'id': a['article_id'], 'title': a['titlu'], 'text': a['text'],
                          'url': a['url']} for a in attached],
            'missing_article_ids': [a for a in dict.fromkeys(item['article_ids']) if a not in articles],
        })
    return {'schema': SCHEMA, 'input_sha256': digest(directory), 'synthetic': True,
            'facet_labels': FACETS, 'events': events,
            'coverage': {'events': len(events), 'articles': len(articles),
                         'events_with_article_text': sum(bool(e['articles']) for e in events),
                         'fixture_only_events': sum(not e['articles'] for e in events),
                         'missing_article_ids': sorted({a for e in events for a in e['missing_article_ids']})}}
