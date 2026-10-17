"""Inspect curated cost and effect references offline; never apply them as estimates."""
import json
from pathlib import Path
import sys


def evidence():
    data = json.loads(Path(__file__).with_name('research.json').read_text(encoding='utf-8'))
    data['policy']['unit_costs_derived_from_project_totals'] = True
    data['policy']['approximation_policy'] = 'Medii orientative autorizate de utilizator; cost al lucrării, nu al analizei; fără actualizare la prețurile curente.'
    data['indicative_unit_estimates'] = []
    for row in data['cost_references']:
        if row['id'] not in ('cost-cluj-lighting-188', 'cost-cluj-signal-2020'):
            continue
        average = row['amount_ron'] / row['quantity']
        data['indicative_unit_estimates'].append(dict(
            measure_id=row['measure_id'], source_id=row['id'], source_url=row['url'],
            calculation=f"{row['amount_ron']} / {row['quantity']}",
            arithmetic_average_ron=round(average, 2),
            indicative_rounded_ron=round(average / 1000) * 1000,
            unit='RON pe trecere, medie de proiect', year=row['year'], vat=row['vat'],
            estimate_type='historical_project_average_not_quote',
            uncertainty_range_ron=None,
            limitations='Include cota medie a componentelor proiectului; diferențele între amplasamente nu sunt cuantificate. ' + row['limitations']))
    return data


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    data = evidence()
    print('REPERE DIN SURSE — nu prețuri sau reduceri promise pentru Iași')
    for row in data['cost_references']:
        print(f"{row['measure_id']}: {row['amount_ron']:,.2f} RON | {row['value_kind']} | {row['unit']} | TVA: {row['vat']}")
        print('  Limită:', row['limitations'])
    for row in data['effect_references']:
        print(f"{row['measure_id']}: {row['id']}, CMF={row['cmf']}, CRF={row['crf_fraction']:.0%} în studiu")
        print('  Condiții:', row['conditions'])
        print('  Decizie:', row['decision'], '|', row['reason'])
    print('NECUNOSCUTE:')
    for row in data['coverage']:
        print(' ', row['measure_id'], ':', row['remaining'])
    print('APROXIMĂRI ORIENTATIVE PE TRECERE:')
    for row in data['indicative_unit_estimates']:
        print(f"  {row['measure_id']}: {row['calculation']} = {row['arithmetic_average_ron']:,.2f} RON; orientativ ~{row['indicative_rounded_ron']:,} RON | an {row['year']} | TVA {row['vat']}")
    print('Catalog: costuri ferme și reduceri încă null; aproximările sunt separate. Fără modificarea scorurilor sau a datelor comune.')


if __name__ == '__main__':
    main()
