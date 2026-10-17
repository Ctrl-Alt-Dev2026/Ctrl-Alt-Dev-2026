"""Deterministic candidate rules, no prediction or score changes."""
from measures.catalog import catalog
from risk.statistics import event_statistics, unique_events

FIELDS = ('semafor', 'benzi', 'iluminat', 'tip_strada', 'scoala_150m', 'statie_100m')


def conjunction(*conditions):
    if any(c is False for c in conditions):
        return False
    return None if any(c is None for c in conditions) else True


def evaluate(feature, events, *, mode, checks=None):
    """Caller must supply events explicitly associated with this location.

    Observed input needs verified events. Simulation input is never evidence
    of actual accidents. Optional checks are field confirmations, not OSM guesses.
    """
    if mode not in ('observed', 'simulation_mixed_sources'):
        raise ValueError('Explicit observed or simulation_mixed_sources mode required')
    p = feature['properties']
    checks = checks or {}
    for key in ('no_bus_route', 'no_emergency_route', 'calming_road_compatible'):
        if checks.get(key) is not None and type(checks[key]) is not bool:
            raise ValueError('Field checks must be bool or null')
    for key in ('semafor', 'iluminat', 'scoala_150m', 'statie_100m'):
        if p.get(key) is not None and type(p[key]) is not bool:
            raise ValueError('Infrastructure must be bool or null')
    lanes = p.get('benzi')
    if lanes is not None and (type(lanes) is not int or lanes < 1):
        raise ValueError('Invalid lane count')
    if p.get('tip') not in ('trecere', 'intersectie'):
        raise ValueError('Unsupported location type')
    events = unique_events(events)
    lon, lat = feature['geometry']['coordinates']
    for e in events:
        if 'pieton' not in e.get('participanti', []):
            raise ValueError('Pedestrian evidence required for pedestrian measure rules')
        # Conservative initial adapter: exact location coordinates, no nearest join.
        if (e.get('in_iasi') is not True or e.get('precizie_loc') != p['tip']
                or [e.get('lon'), e.get('lat')] != [lon, lat]):
            raise ValueError('Events require an explicit matching location assignment')
        if mode == 'observed' and (e.get('verificat') is not True or e.get('data_mode') != 'observed' or p.get('sursa') != 'OSM'):
            raise ValueError('Observed events must be explicitly observed, verified and use OSM context')
    stats = event_statistics(events)
    crossing = p['tip'] == 'trecere'
    no_signal = None if p.get('semafor') is None else p['semafor'] is False
    multilane = None if lanes is None else lanes >= 4
    two_lanes = None if lanes is None else lanes == 2
    night = True if stats['noapte'] >= 2 else None if stats['noapte'] + stats['necunoscut'] >= 2 else False
    priority = sum(e.get('cauza_raportata') == 'neacordare_prioritate' for e in events)
    speed_ids = [e['event_id'] for e in events if e.get('cauza_raportata') == 'viteza']
    speed_condition = True if speed_ids else None if any(e.get('cauza_raportata') is None for e in events) else False
    unknown_causes = sum(e.get('cauza_raportata') is None for e in events)
    repeated = True if priority >= 2 else None if priority + unknown_causes >= 2 else False
    missing = [k for k in FIELDS if p.get(k) is None]
    school = conjunction(crossing, bool(events), True if speed_ids else p.get('scoala_150m'), two_lanes,
                         checks.get('no_bus_route'), checks.get('no_emergency_route'),
                         checks.get('calming_road_compatible'))
    conditions = {
        'analiza_viteza': (speed_condition, f'{len(speed_ids)} evenimente cu viteza raportată explicit; event_ids={speed_ids}. Se analizează limita adecvată, controlul vitezei/radarul și calmarea traficului; nu se deduce viteza măsurată sau vinovăția.'),
        'iluminat_trecere': (conjunction(crossing, night), f"{stats['noapte']} evenimente nocturne explicite; {stats['necunoscut']} necunoscute. Iluminatul existent trebuie evaluat."),
        'semafor_pietonal': (conjunction(crossing, no_signal, multilane), f"Semafor={p.get('semafor')}; benzi={lanes}. Necesitatea semaforizării nu este stabilită automat."),
        'insula_refugiu': (conjunction(crossing, no_signal, multilane), f"Semafor={p.get('semafor')}; benzi={lanes}. Existența și fezabilitatea insulei trebuie verificate."),
        'trecere_inaltata': (school, f"Școală={p.get('scoala_150m')}; evenimente cu viteza={len(speed_ids)}; evenimente={len(events)}; benzi={lanes} (necesar 2); confirmări de compatibilitate={checks}."),
        'limitator_viteza': (school, f"Școală={p.get('scoala_150m')}; evenimente cu viteza={len(speed_ids)}; evenimente={len(events)}; benzi={lanes} (necesar 2); confirmări de compatibilitate={checks}. Vitezele măsurate rămân de verificat."),
        'analiza_intersectie': (conjunction(p['tip'] == 'intersectie', repeated), f'{priority} evenimente cu cauza explicită neacordare_prioritate.'),
        'analiza_statie': (conjunction(crossing, bool(events), p.get('statie_100m')), 'Stație apropiată și evenimente asociate; legătura cu deplasările la stație trebuie verificată.'),
        'observatie_teren': (bool(missing), 'Câmpuri necunoscute: ' + ', '.join(missing)),
    }
    audit, matched = [], []
    for row in catalog():
        state, reason = conditions[row['id']]
        audit.append(dict(measure_id=row['id'], status='matched' if state is True else 'insufficient_data' if state is None else 'not_matched', motiv=reason))
        if state is True:
            matched.append(dict(measure_id=row['id'], motiv=('SCENARIU: ' if mode != 'observed' else '') + reason,
                                de_verificat=row['de_verificat'] + (missing if row['id'] == 'observatie_teren' else [])))
    # Make the explicit reported speed cause visible; not an efficacy rank.
    matched.sort(key=lambda row: {'observatie_teren': 0, 'analiza_viteza': 1}.get(row['measure_id'], 2))
    return dict(location_id=p['id'], data_mode=mode, event_ids=[e['event_id'] for e in events],
                statistics=stats, candidates=matched, suggested=matched[:3],
                selection_policy='Maximum trei afișate: observație în teren, analiza vitezei dacă este raportată, apoi ordinea catalogului; fără clasament de eficacitate.',
                rules=audit, missing_fields=missing)
