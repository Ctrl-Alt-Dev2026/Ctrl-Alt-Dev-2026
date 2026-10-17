"""Event statistics shared by concrete locations and visual H3 cells."""
from collections import Counter
import re


def unique_events(events):
    result = {}
    for event in events:
        identifier = event.get('event_id')
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError('Missing event_id')
        if identifier in result and result[identifier] != event:
            raise ValueError(f'Conflicting duplicate event_id: {identifier}')
        result[identifier] = event
    return list(result.values())


def event_statistics(events):
    events = unique_events(events)
    hours, unknown_hours = [0] * 24, 0
    for event in events:
        hour = event.get('ora')
        if hour is None:
            unknown_hours += 1
        elif not isinstance(hour, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', hour):
            raise ValueError(f"Invalid ora for {event['event_id']}; expected HH:MM or null")
        else:
            hours[int(hour[:2])] += 1
        if event.get('noapte') is not None and type(event['noapte']) is not bool:
            raise ValueError(f"Invalid noapte for {event['event_id']}")
        if event.get('gravitate') not in ('deces', 'grav', 'usor', 'necunoscut'):
            raise ValueError(f"Invalid gravitate for {event['event_id']}")
        cause = event.get('cauza_raportata')
        if cause is not None and (not isinstance(cause, str) or not cause.strip()):
            raise ValueError(f"Invalid cauza_raportata for {event['event_id']}")
    return dict(nr_evenimente=len(events), pe_ore=hours, ora_necunoscuta=unknown_hours,
                noapte=sum(e.get('noapte') is True for e in events),
                zi=sum(e.get('noapte') is False for e in events),
                necunoscut=sum(e.get('noapte') is None for e in events),
                cauze=dict(sorted(Counter(e.get('cauza_raportata') or 'necunoscut' for e in events).items())),
                gravitati=dict(sorted(Counter(e['gravitate'] for e in events).items())))
