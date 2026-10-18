"""Street studies from reported causes. Never authorise or count physical works."""
from measures.research import evidence
from risk.statistics import unique_events

# A candidate describes what to investigate along the street, not where to install it.
CAUSE_MEASURES = {
    'viteza': [('limitator_viteza', 'Studiați calmarea traficului și regimul de viteză')],
    'neacordare_prioritate': [('semafor_pietonal', 'Studiați acordarea priorității și organizarea traversărilor')],
    'traversare_neregulamentara': [('trecere_inaltata', 'Studiați traseele pietonale și accesul la traversări')],
    'vizibilitate': [('iluminat_trecere', 'Auditați vizibilitatea și iluminatul pe stradă')],
}


def recommend(events):
    events = unique_events(events)
    estimates = {r['measure_id']: r for r in evidence()['indicative_unit_estimates']}
    result = []
    for cause, candidates in CAUSE_MEASURES.items():
        basis = [e['event_id'] for e in events if e.get('cauza_raportata') == cause]
        if not basis:
            continue
        for identifier, title in candidates:
            result.append(dict(measure_id=identifier, titlu=title, cauza=cause, event_ids=basis,
                status='studiu_la_nivel_de_strada', amplasament_verificat=False,
                cerinte=['Verificați manual locul exact și cauza relatată.',
                         'Pentru modificarea unei treceri: confirmați trecerea și infrastructura existentă.',
                         'Pentru limitatoare: verificați amplasamentul, traficul, rutele de urgență și transportul public.'],
                cost_unitar=estimates.get(identifier), numar_interventii=None, cost_total=None))
    return result
