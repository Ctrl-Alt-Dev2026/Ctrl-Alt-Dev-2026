"""Contract-compatible catalog and separate research provenance."""
from copy import deepcopy

VISIBILITY = 'https://highways.dot.gov/safety/proven-safety-countermeasures/crosswalk-visibility-enhancements'
REFUGE = 'https://highways.dot.gov/safety/proven-safety-countermeasures/medians-and-pedestrian-refuge-islands-urban-and-suburban-areas'
STEP = 'https://highways.dot.gov/safety/pedestrian-bicyclist/step'
CALMING = 'https://highways.dot.gov/safety/speed-management/traffic-calming-eprimer/module-3-part-3'

ROWS = [
    ('iluminat_trecere', 'Analiza iluminatului dedicat trecerii', 'Minimum două evenimente cu noapte=true la trecere',
     ['iluminatul existent și măsurători nocturne', 'poziția stâlpilor și vizibilitatea din ambele sensuri'], [VISIBILITY]),
    ('semafor_pietonal', 'Analiza semaforizării pietonale', 'Trecere cu semafor=false și minimum patru benzi',
     ['necesitatea semaforizării conform normelor locale', 'traficul și fluxul pietonal măsurate', 'coordonarea cu semafoarele apropiate'], [STEP]),
    ('insula_refugiu', 'Analiza unei insule de refugiu', 'Trecere cu semafor=false și minimum patru benzi',
     ['existența unei insule', 'lățimea disponibilă și accesibilitatea', 'traficul, vitezele și fluxul pietonal'], [REFUGE]),
    ('trecere_inaltata', 'Analiza unei treceri înălțate', 'Școală apropiată, evenimente la trecere, două benzi și compatibilitate confirmată',
     ['intrările școlii și fluxul real de elevi', 'traseele de autobuz și intervenție', 'drenajul și compatibilitatea tipului de drum'], [STEP]),
    ('limitator_viteza', 'Analiza calmării vitezei', 'Școală apropiată, evenimente la trecere, două benzi și compatibilitate confirmată',
     ['vitezele măsurate și soluția adecvată', 'traseele de autobuz și intervenție', 'accesibilitatea, zgomotul și drenajul'], [CALMING]),
    ('analiza_intersectie', 'Analiza vizibilității și organizării intersecției', 'Minimum două cauze raportate explicit ca neacordare de prioritate la intersecție',
     ['geometria și vizibilitatea', 'semnalizarea existentă', 'tipul conflictului; cauza relatată nu demonstrează cauza tehnică'], [VISIBILITY]),
    ('analiza_statie', 'Analiza traversărilor în apropierea stației', 'Stație la sub 100 m și minimum un eveniment la trecere',
     ['fluxurile reale între stație și trecere', 'vizibilitatea în jurul vehiculelor oprite', 'poziția stației și alternativele; mutarea nu este decisă automat'], [STEP]),
    ('observatie_teren', 'Observație în teren', 'Informații de infrastructură esențiale necunoscute',
     ['completarea câmpurilor de infrastructură necunoscute'], []),
]


def catalog():
    return [dict(id=i, nume=n, conditie=c, cost_lei_min=None, cost_lei_max=None,
                 sursa_cost=None, reducere_tipica=None, sursa_reducere=None,
                 de_verificat=deepcopy(checks)) for i, n, c, checks, _ in ROWS]


def provenance():
    return dict(rule_source='Planificare.md, secțiunea 7',
                thresholds='Convenții MVP ale echipei, nu praguri validate științific.',
                applicability='Surse internaționale orientative; proiectarea și normele românești necesită verificare.',
                numeric_status='Repere cercetate în research_evidence.json; fără cost sau efect transferabil automat locațiilor. Valorile din catalog rămân null.',
                research_file='research_evidence.json',
                sources={i: urls for i, _, _, _, urls in ROWS})
