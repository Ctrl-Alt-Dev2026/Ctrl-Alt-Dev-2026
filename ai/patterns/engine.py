"""Deterministic overlapping neighborhoods over genuinely computed semantic vectors.

Cosine is similarity, never confidence, risk or evidence of a causal mechanism.
"""
from __future__ import annotations

import math
from collections import Counter

DEFAULT_THRESHOLD = 0.35
MIN_MEMBERS = 3
MIN_SOURCE_EVENTS = 5  # Explicit demo guardrail, NOT a statistical adequacy threshold.


def cosine(a, b):
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0


def eligible(event):
    return event['in_iasi'] and (any(f.startswith('cause:') for f in event['facets']) or len(event['facets']) >= 2)


def discover(bundle, excluded=(), threshold=DEFAULT_THRESHOLD, scope='fixtures'):
    if scope not in ('fixtures', 'sources'):
        raise ValueError('scope must be fixtures or sources')
    if not 0.10 <= threshold <= 0.95:
        raise ValueError('threshold must be between 0.10 and 0.95')
    known_ids = {e['id'] for e in bundle['events']}
    if set(excluded) - known_ids:
        raise ValueError('Unknown excluded event ID')
    events = [e for e in bundle['events'] if e['id'] not in excluded and e['in_iasi']]
    if scope == 'sources':
        events = [dict(e, facets=e['source_facets']) for e in events if e['articles'] and e['source_profile']]
    else:
        events = [e for e in events if eligible(e)]
    base = {'scope': scope, 'threshold': threshold, 'excluded': sorted(set(excluded)),
            'eligible_ids': [e['id'] for e in events], 'patterns': [], 'unassigned_ids': [],
            'note': None, 'engine': bundle['model']['method']}
    minimum = MIN_SOURCE_EVENTS if scope == 'sources' else MIN_MEMBERS
    if len(events) < minimum:
        base['note'] = ('Insufficient source evidence: fewer than five events have matched source excerpts. '
                        'The five-event guardrail is a demo policy, not statistical validation.'
                        if scope == 'sources' else 'Fewer than three sufficiently described eligible events remain.')
        base['unassigned_ids'] = base['eligible_ids']
        return base
    vectors = bundle['source_vectors'] if scope == 'sources' else bundle['vectors']
    sims = {(a['id'], b['id']): cosine(vectors[a['id']], vectors[b['id']]) for a in events for b in events}
    candidates = []
    for anchor in events:
        ranked = sorted((e for e in events if e['id'] != anchor['id']),
                        key=lambda e: (-sims[anchor['id'], e['id']], e['id']))
        members = [anchor]
        # Complete-link guard: a vague bridge case cannot connect unrelated groups.
        for event in ranked:
            if len(members) >= 6:
                break
            if all(sims[event['id'], m['id']] + 1e-9 >= threshold for m in members):
                members.append(event)
        if len(members) < MIN_MEMBERS:
            continue
        sites = {m['site_id'] or m['location'] for m in members}
        if len(sites) < 2:
            continue
        counts = Counter(f for e in members for f in e['facets'])
        population = Counter(f for e in events for f in e['facets'])
        # The labels summarize recorded fields; they do not introduce LLM-generated explanations.
        common = [f for f, n in counts.items() if n >= math.ceil(.66*len(members))]
        distinctive = sorted(common, key=lambda f: (-(counts[f]/len(members) - population[f]/len(events)),
                                                    -counts[f], f))
        if not distinctive:
            continue
        pairs = [sims[a['id'], b['id']] for i, a in enumerate(members) for b in members[i+1:]]
        ids = sorted(m['id'] for m in members)
        facets = [{'key': f, 'label': bundle['facet_labels'][f], 'count': counts[f], 'total': len(members),
                   'other_count': population[f]-counts[f], 'other_total': len(events)-len(members)}
                  for f in distinctive]
        differences = []
        for e in members:
            differences.append({'id': e['id'], 'shared': [f for f in distinctive if f in e['facets']],
                                'not_recorded': [f for f in distinctive if f not in e['facets']],
                                'mean_similarity': round(sum(sims[e['id'], m['id']] for m in members
                                                             if m != e)/(len(members)-1), 6)})
        outsiders = [e for e in events if e['id'] not in ids]
        outsiders.sort(key=lambda e: (-sum(sims[e['id'], m['id']] for m in members)/len(members), e['id']))
        candidates.append({'id': 'p-' + '-'.join(ids),
                           'title': ' · '.join(bundle['facet_labels'][f] for f in distinctive[:2]),
                           'member_ids': ids, 'site_count': len(sites), 'facets': facets,
                           'members': differences, 'comparison_ids': [e['id'] for e in outsiders[:2]],
                           'article_event_count': sum(bool(e['articles']) for e in members),
                           'article_count': len({a['id'] for e in members for a in e['articles']}),
                           'mean_similarity': round(sum(pairs)/len(pairs), 6),
                           'min_similarity': round(min(pairs), 6)})
    candidates.sort(key=lambda p: (-len(p['member_ids']), -p['mean_similarity'], p['id']))
    kept = []
    for candidate in candidates:
        ids = set(candidate['member_ids'])
        if any(len(ids & set(p['member_ids'])) / len(ids | set(p['member_ids'])) >= .60 for p in kept):
            continue
        kept.append(candidate)
        if len(kept) == 4:
            break
    base['patterns'] = kept
    covered = {i for p in kept for i in p['member_ids']}
    base['unassigned_ids'] = [e['id'] for e in events if e['id'] not in covered]
    if not kept:
        base['note'] = 'No cross-location group passes the current similarity and support rules. No pattern is forced.'
    return base
