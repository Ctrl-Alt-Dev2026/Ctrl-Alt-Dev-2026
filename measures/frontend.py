"""Optional frontend sidecar; shared Measure/Hotspot contracts remain unchanged."""
from copy import deepcopy

VAT_LABELS = {'excluded': 'fără TVA', 'not_explicit_on_page': 'TVA neprecizat în sursă'}


def attach_costs(result, catalog_rows, research):
    catalog = {r['id']: r for r in catalog_rows}
    estimates = {r['measure_id']: r for r in research['indicative_unit_estimates']}
    references = {r['id']: r for r in research['cost_references']}
    selected = {r['measure_id'] for r in result['suggested']}
    details = []
    for candidate in result['candidates']:
        identifier = candidate['measure_id']
        estimate = deepcopy(estimates.get(identifier))
        if estimate:
            estimate['publisher'] = references[estimate['source_id']]['publisher']
            amount = f"{estimate['indicative_rounded_ron']:,}".replace(',', '.')
            estimate['display_label'] = (f"~{amount} lei/trecere, {VAT_LABELS[estimate['vat']]} "
                                         f"— reper {estimate['year']}")
            estimate['applies_to'] = 'possible_implementation_not_analysis_service'
            label = estimate['display_label']
        else:
            label = 'Cost necunoscut — necesită evaluare/ofertă'
        details.append(dict(**deepcopy(candidate), nume=catalog[identifier]['nume'],
                            selected_for_display=identifier in selected,
                            indicative_cost=estimate, cost_display=label,
                            applicable_reduction=None,
                            note='Măsură candidată de analizat. Estimarea, dacă există, privește lucrarea ulterioară, nu serviciul de analiză.'))
    return details


def frontend_payload(locations, warning, source_hashes):
    return dict(schema_version='measures-preview-1', data_mode='simulation_mixed_sources',
                warning=warning,
                cost_warning='Medii istorice de proiect, nu oferte sau prețuri actualizate. Nu însumați automat: TVA și acoperirea diferă; unele costuri lipsesc.',
                source_dataset_sha256=deepcopy(source_hashes),
                locations=[dict(location_id=r['location_id'], crossing_id=r['location_id'],
                                hotspot_id=r['hotspot_id'], nume=r['nume'],
                                scenario_score=r['scenario_score_unchanged'],
                                measures=deepcopy(r['measure_details']),
                                total_cost_ron=None) for r in locations])
