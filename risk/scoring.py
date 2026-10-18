"""The event terms of Planificare §5, shared by point and street analysis."""
from risk.statistics import unique_events


def event_components(events):
    events = unique_events(events)
    return dict(evenimente=len(events),
                deces=4 * sum(e['gravitate'] == 'deces' for e in events),
                grav=2 * sum(e['gravitate'] == 'grav' for e in events), context=0)
