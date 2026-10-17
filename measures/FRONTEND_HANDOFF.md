# Măsuri și costuri orientative pentru cele trei scenarii

Fișierul de încărcat: `measures/output/three-scenarios/frontend_measures.json`.
Este un fișier separat, opțional, pentru datasetul static mixed-source existent
din `risk/output/frontend-scenario/data/`. Nu înlocuiește measures.json comun,
nu modifică schema comună și nu este o publicație observed din backend.

## Integrare pentru colegul de frontend

1. Copiază/servește acest fișier ca asset separat și încarcă-l în modul demo.
   Loaderul actual nu îl consumă automat. Nu îl folosi ca fallback pentru HTTP.
2. Verifică data_mode=simulation_mixed_sources. Asociază locations[].crossing_id
   cu crossing.properties.id sau hotspot.crossing_id; hotspot_id corespunde
   hotspot.id din datasetul de scenariu. source_dataset_sha256 permite verificarea
   versiunii fișierelor de intrare; nu amesteca cu alt set de accidente.
3. În fișa locației, afișează cele maximum trei measures cu
   selected_for_display=true: nume, motiv, de_verificat și cost_display.
   Celelalte sunt alternative disponibile, nu lucrări de adăugat obligatoriu.
4. Dacă indicative_cost există, oferă link spre source_url și afișează publisher,
   year, vat și limitations. Label-ul cost_display este deja pregătit în română.
   Calculation și arithmetic_average_ron permit explicarea mediei; numărul rotunjit
   indicative_rounded_ron este estimarea de afișat, nu un interval min/max.
5. Dacă indicative_cost=null, arată „Cost necunoscut”, fără 0. Nu calcula totaluri:
   total_cost_ron este null pentru că există costuri lipsă, baze TVA diferite și
   potențiale suprapuneri între lucrări. applicable_reduction=null nu devine 0%.
6. Păstrează vizibile warning și cost_warning. Propunem analiza unor lucrări;
   sumele sunt repere de implementare, nu tarife pentru analiza tehnică.

## Rezultatul așteptat pentru fiecare dintre cele trei locații

- Observație în teren: cost necunoscut.
- Analiza iluminatului: lucrare posibilă ~140.000 lei/trecere, reper de proiect
  început în 2024, TVA neprecizat. Calcul: 26.312.475,50 / 188.
- Analiza semaforizării: lucrare posibilă ~294.000 lei/trecere fără TVA,
  reper 2020. Calcul: 881.010,27 / 3.

Scorurile scenariilor rămân 13/11/9; datele de accidente sunt sintetice.
Sursele detaliate și celelalte măsuri sunt documentate în RESEARCH.md.

## Reproducere

```powershell
python -m measures.run --inspect
python -m unittest measures.test_rules measures.test_research measures.test_frontend -v
python -m measures.run --output measures/output/new-preview
```

Prima comandă afișează propunerile, costurile și sursele fără scrieri.
Ultima cere un director nou; fișierul de referință livrat este în three-scenarios/.
