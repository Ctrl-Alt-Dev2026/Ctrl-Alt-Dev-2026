# Municipiul Iași: profiluri de infrastructură fără scor nou

## Rezultat verificat la 17 octombrie 2026

Exportul complet este în `context/output/observed/iasi/`. Regenerarea offline
reproduce identic fișierele. Cele 18 teste din context și risk trec.

| Indicator | Număr |
|---|---:|
| Treceri în municipiu | 1.210 |
| Noduri din afara municipiului eliminate | 75 |
| Treceri cu drumuri conectate și geometrie compatibilă | 1.204 |
| Treceri cu legături rutiere neclarificate | 6 |
| Treceri cu număr de benzi cunoscut | 803 |
| Treceri cu limită numerică explicită și coerentă | 195 |
| Treceri cu școală la sub 150 m | 325 |
| Treceri cu obiect de transport public la sub 100 m | 601 |
| Treceri explicit nesemaforizate pe drumuri cu 4+ benzi | 22 |
| Zone de analiză | 141 |
| Zone fără treceri cartografiate | 86 |

86 de zone fără treceri cartografiate nu înseamnă 86 de zone sigure sau fără
traversări reale. Sunt păstrate cu starea de date insuficiente. Cele 22 de
configurații nesemaforizate pe 4+ benzi sunt semnale de verificat în teren,
nu un clasament nou. Toate geometriile POI descărcate au trecut validarea.
Observațiile provin din intervalul 13:25–13:41 UTC (16:25–16:41 Europe/Bucharest);
timestamp-urile OSM și endpoint-urile efective sunt păstrate în raport.

## Rulare

Din rădăcina repository-ului, cu aceleași dependențe ca pilotul Palas:

```powershell
python -m context.city --endpoint https://overpass-api.de/api/interpreter
python -m context.city --offline --output context/output/observed/iasi-replay
python -m context.validate_city
python -m unittest context.test_city context.test_context risk.test_pipeline -v
```

Cache implicit: `context/cache/iasi/`. Output implicit: `context/output/observed/iasi/`.
Comanda refuză un director de output existent. Un cache nou (`--cache alt-director`)
declanșează o actualizare deliberată. La o eroare API, reluarea comenzii reutilizează
interogările deja salvate. Nu se publică un export municipal parțial ca și cum
ar fi complet. Limita administrativă este cache-uită și verificată separat.
Folosește `--boundary-only` pentru verificarea limitei, fără colectarea straturilor.

## Delimitare și acoperire

Relația OSM 1207838 este verificată prin taguri: Iași, boundary=administrative,
admin_level=8. Geometria trebuie să fie validă și să includă Palas. Este limita
din OSM, nu o nouă delimitare oficială certificată. Snapshot-ul verificat are
aproximativ 91,856 km². Nu include întreaga zonă metropolitană.

Geometriile drumurilor se împart în 13 dale de 5 km în EPSG:32635. Straturile
mai mici (treceri, școli/grădinițe, stații) au fiecare o cerere pe anvelopa
municipiului: 16 cereri în total, fără a număra limita administrativă. Astfel
evităm 52 de cereri mici cu duplicate. Fiecare dală/anvelopă are un buffer de
200 m; drumurile și poligoanele POI au geometrie completă, ne-tăiată.
Trecerile sunt apoi filtrate strict la poligonul municipiului. POI-urile de
lângă limita municipiului sunt păstrate pentru vecinătățile de 100/150 m.
La suprapunerea dalelor se deduplică după (tip OSM, ID); observații contradictorii
ale aceluiași obiect opresc exportul, în loc să aleagă arbitrar una dintre ele.

Trecerile, drumurile, școlile/grădinițele și stațiile au interogări separate.
Răspunsurile valide sunt salvate după hash-ul interogării; endpoint-ul, bbox-ul,
data descărcării și timestamp_osm_base sunt păstrate. Endpoint-urile pot avea
502/500/504; nu există presupunerea că un anumit server este disponibil permanent.
Runnerul municipal face cel mult două reîncercări pentru erori temporare, cu
pauze de 5 și 10 secunde, apoi se oprește fără a publica un rezultat incomplet.

## Livrabile proprii

- `boundary.geojson`: limita folosită, cu identitatea OSM.
- `crossings.geojson`: proprietățile contractului 2.0, fără câmpuri noi.
- `geometry_report.json`: dovezi geometrice, taguri, limite de viteză, erori POI,
  proveniență și rezumat de acoperire.
- `zones.geojson`: celule de 1 km tăiate la limita municipiului, în WGS84 pentru
  consum GIS. Sunt zone de analiză, nu cartiere administrative.
- `zones.csv`: aceleași identificatoare de zone și câțiva indicatori pentru
  inspectarea rapidă de către echipă, fără interfață nouă.

Fiecare zonă păstrează crossing_ids, număr de treceri cartografiate, indicatori
de completitudine și numele reale ale drumurilor conectate trecerilor, pentru
identificarea zonei în CSV. Aceste nume nu sunt denumiri de cartiere.
Printre numărători se află câte treceri au
semafor explicit, câte sunt explicit nesemaforizate pe 4+ benzi, vecinătăți de
școli/stații și numărul de valori necunoscute pentru fiecare câmp. O zonă fără
treceri OSM rămâne prezentă, cu starea „nu există treceri cartografiate; aceasta
nu este dovadă de siguranță”. Indicatorii sunt numărători, fără ponderi, scor
nou sau clasificări „sigur/periculos/evită”. Numerele de școli/stații din zone
reprezintă treceri cu vecinătăți, nu instituții sau stații unice.

## Viteza

Limita este preluată numai din drumuri legate topologic și geometric de trecere.
`maxspeed_kmh` este numeric numai dacă toate drumurile conectate au aceeași
valoare numerică explicită și nu există excepții direcționale/condiționale.
`RO:urban`, valori contradictorii, lipsuri și restricții condiționale rămân
necunoscute numeric; tagurile originale sunt păstrate ca dovezi. Nu deducem
50 km/h din faptul că drumul se află în oraș. Nu estimăm viteza reală de circulație.
Nu există bonus de viteză în formula comună.

## Formula comună, neschimbată

Pentru fiecare eveniment unic eligibil: 1 punct, plus 4 dacă este deces sau
plus 2 dacă este grav. Pe locație, o singură dată: +2 pentru trecere confirmată
fără semafor pe 4+ benzi, +1 pentru școală la sub 150 m, +1 pentru stație la
sub 100 m. Valorile null nu adaugă puncte și nu confirmă absența infrastructurii.
Exemple: un accident ușor = 1, grav = 3, deces = 5, înainte de bonusurile locației.
Scorul de accidente nu este calculat în acest export de context.

## Limite și integrare

OSM nu este un inventar complet. Nu numărăm intersecțiile drept treceri.
Semaforizarea folosește crossing:signals=yes/no sau tagurile explicite legacy;
tagurile contradictorii produc null. Marcajele singure nu dovedesc semaforizarea.
Iluminatul drumului nu este automat iluminat dedicat al trecerii. Benzile mai
multor carosabile nu se însumează. Nu generăm rute sau recomandări de evitare.
Nu amestecăm accidente sintetice cu infrastructură observată într-un hotspot real.
Persoana 6 poate citi zones.geojson și raportul separat; conectarea la UI rămâne
în scope-ul colegului. Următoarea integrare a Persoanei 4 este cu accidentele reale
geolocalizate ale Persoanei 3 și cu verificarea asocierilor.

Referințe pentru interpretare:
https://wiki.openstreetmap.org/wiki/Relation:boundary
https://wiki.openstreetmap.org/wiki/Key:maxspeed
https://wiki.openstreetmap.org/wiki/Key:lanes
https://wiki.openstreetmap.org/wiki/Key:crossing:signals
