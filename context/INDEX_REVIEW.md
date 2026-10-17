# Verificarea indexului Persoanei 3 și pregătirea intersecțiilor

## Rezultate

Indexul din coordonate/ a fost citit fără modificări. Toate cele 1.210 treceri
din exportul nostru se regăsesc în index. Cele trei diferențe sunt:

| Nod OSM | Taguri verificate | Decizie |
|---|---|---|
| 602300462 | highway=traffic_signals, crossing=no | Nu este adăugat ca trecere: absență explicită a trecerii la acel nod |
| 10074505625 | crossing=informal | Păstrat în audit, separat de trecerile formale |
| 3682801813 | crossing=traffic_signals, crossing:markings=yes, kerb=lowered | Supliment de o trecere semaforizată, tagare alternativă fără highway=crossing |

Tagurile complete și drumurile conectate au fost descărcate printr-o singură
interogare Overpass și păstrate în context/cache/index-review/. Coordonatele
celor trei noduri coincid cu indexul (diferență 0 m). Nu am adăugat artificial
tagul highway=crossing nodului 3682801813. Semaforizarea sa este true, dar benzile
rămân null: drumurile conectate au valori diferite (1/6/6). Nu le însumăm.
Iluminatul drumului nu devine automat iluminat al trecerii.

Exportul municipal original rămâne cu 1.210 treceri. Suplimentul separat ar
aduce totalul la 1.211 dacă este integrat ulterior. Nu am modificat snapshot-ul,
profilurile pe zone, scorurile sau preview-ul frontend pentru a-l introduce tacit.

Definițiile OSM folosite:
https://wiki.openstreetmap.org/wiki/Tag:crossing=no
https://wiki.openstreetmap.org/wiki/Tag:crossing=informal
https://wiki.openstreetmap.org/wiki/Key:crossing

## Intersecții

- 1.582 noduri în municipiu au minimum două nume de străzi și trei vecini în index.
- 1.573 au și geometrie compatibilă în cache-ul nostru de drumuri: același nod
  OSM, minimum trei ramuri și participarea la way-urile ambelor străzi.
- 9 rămân de verificat: dovezi geometrice insuficiente sau niveluri layer diferite.
- Din cele 1.573, patru coincid cu treceri existente și nu sunt duplicate în
  fișierul de candidați. Rezultă **1.569 intersecții candidate exportate**.
- În total, cinci noduri candidate coincid cu treceri; unul dintre ele este și
  în grupul celor nouă neclarificate.

O schimbare de nume pe o stradă cu numai două ramuri nu produce intersecție.
Suprapunerea în plan a două străzi fără nod OSM comun nu produce intersecție.
Nivelurile incompatibile și coordonatele neconcordante sunt semnalate separat.
Se verifică numai clasele de drum carosabil acceptate, nu aleile pietonale doar
pentru că au un nume. Acoperirea este conservatoare: străzile fără nume și
ramificațiile cu același nume pot lipsi. Nu este un inventar complet de intersecții.

Fiecare punct este un nod real, fără coordonate inventate sau centre medii.
Mai multe noduri apropiate pot reprezenta aceeași intersecție fizică cu
carosabile separate. Nu le unim automat doar pe criteriul distanței.
Toate rămân manual_review_required=true în raport: verificarea topologică
automată nu este o verificare umană și nu justifică un scor nou.

## Fișiere

Director: context/output/observed/index-review-complete/

- additional_crossings.geojson: suplimentul de o trecere, proprietăți conform contractului.
- confirmed_additional_crossings_raw.geojson: tagurile sursă, fără taguri fabricate.
- intersection_candidates.geojson: cele 1.569 puncte, tip=intersectie; infrastructura
  necunoscută rămâne null, fără moștenirea arbitrară a benzilor unei străzi.
- intersection_review.csv: noduri, stări și link-uri OSM pentru verificare.
- review_report.json: toate dovezile, cele nouă cazuri neclarificate, conflictele
  de nivel, sursele și hash-urile intrărilor.
- crossing_candidates.geojson: alternative insuficient documentate; gol în acest snapshot.

Fișierele sunt pregătite pentru review separat. Nu au fost alipite la
crossings.geojson și nu sunt consumate automat de frontend sau de motorul de risc.

## Reproducere offline

```powershell
python -m context.index_review --output context/output/observed/index-review-rerun
python -m unittest context.test_index_review -v
```

Necesită indexul colegului și cache-urile locale deja existente. Nu necesită
Osmnx la rulare; utilizăm gzip/json, pyproj și shapely deja instalate.
Output-ul trebuie să fie un director nou. --online permite cererea pentru cele
trei noduri numai dacă lipsește cache-ul; endpoint-ul se poate selecta explicit.
Niciun fișier al colegului nu este scris. Datele sintetice nu sunt folosite aici.
