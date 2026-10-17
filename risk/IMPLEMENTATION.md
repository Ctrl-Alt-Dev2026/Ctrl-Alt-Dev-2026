# Persoana 4 — starea implementării

Actualizare E4/E5: statisticile complete, agregarea H3 r9 și runnerul pentru
integrarea observată sunt implementate în `risk.run`. Vezi `risk/E4_E5.md`.
Comanda veche `risk.pipeline` rămâne compatibilă pentru analiza sintetică inițială;
runnerul nou produce și statistici separate, H3 și verificarea limitei municipale.

Contract: schema 2.0 din Planificare.md și false_data/. Instrucțiunea utilizatoarei
fixează rolul: context urban și scor, fără recomandări, API sau frontend.
Planul alternativ din docs/HACKATHON_PLAN.md are alte roluri, alte fișiere și
alt scor; nu este aplicat implicit. Nu există AGENTS.md în inventarul repository-ului.

## Rulare din rădăcina repository-ului

Necesită Python și `pyproj` (disponibil în mediul inspectat: 3.8.0).
Pe alt laptop: `python -m pip install pyproj==3.8.0`.
Fișierele comune de dependențe rămân nemodificate.

```powershell
python -m unittest risk.test_pipeline -v
python -m risk.pipeline --input false_data --output risk/output/synthetic
python -m context.export --downloaded 2026-10-17
```

Data exportului trebuie să fie data reală a descărcării, confirmată de operator;
fișierul original nu conține această proveniență. Comenzile refuză suprascrierea
output-urilor; pentru o rulare nouă folosește alt director/fișier.

`risk/output/synthetic/hotspots.json` păstrează câmpurile contractului.
Raportul separat `analysis_report.json` conține candidații, distanțele, cazurile
neeligibile, ambigue și distribuția zi/noapte/cauze. Nu schimbă schema comună.
`verificat` rămâne false: verificarea evenimentelor nu confirmă asocierea spațială.
`masuri=[]` așteaptă integrarea cu Persoana 5; `h3=null` este opțional.
Sunt exportate numai locațiile cu minimum două evenimente asociate provizoriu.

## Ce am verificat

17 evenimente sintetice, 7 obiecte de infrastructură, 5 hotspot-uri de referință.
Formula reproduce 13, 11, 6, 5, 5 pe grupările explicit furnizate în fixture.
Aceasta nu confirmă grupările: ev-004, ev-005, ev-009 sunt intersecții lângă
obiecte de tip trecere; ev-012 este trecere lângă obiect de tip intersecție.
Runnerul conservator nu le asociază automat. `segment` necesită de asemenea
verificare, deoarece proximitatea nu identifică locul accidentului.
Datele originale și hotspot-urile colegilor nu sunt corectate sau suprascrise.

27 noduri OSM reale există deja în crossings_test.geojson. Experimentul inițial
test.py folosea requests și endpoint-ul maps.mail.ru; a fost eliminat la curățarea
livrabilului, fiind înlocuit de modulele context. Cache-ul Nominatim experimental
pentru Palas a fost de asemenea eliminat; nu era folosit de pipeline.
Exportul offline păstrează null la informațiile lipsă. `crossing=uncontrolled`
este folosit drept dovadă explicită pentru semafor=false; marcajul singur nu este.
Geometria și tagurile brute rămân în fișierul original.

## Pașii următori, în ordinea implementării

Actualizare: pașii 1–4 pentru drumuri, școli și stații sunt implementați și rulați
pe pilotul Palas. Vezi `context/IMPLEMENTATION.md` pentru rezultate și reproducere.
Semafoarele și iluminatul nu au fost colectate separat în acest pas.
Ulterior, contextul a fost extins la municipiul Iași: 1.210 treceri și 141 de zone
descriptive, fără scor nou sau integrarea accidentelor sintetice cu OSM real.
Detalii în `context/CITY.md`; formula de risc rămâne neschimbată.

1. Context Palas: colector requests cu endpoint configurabil, timeout și cache
   pe hash-ul interogării; răspunsurile cu eroare nu se salvează ca date valide.
2. Interogări separate pentru drumuri cu noduri/geometrii, școli/grădinițe,
   stații, semafoare și iluminat. Extindere cu cel puțin 150 m în jurul ariei
   exportate, pentru a evita tăierea vecinătăților la margine.
3. Legarea drumului prin apartenența nodului la way și verificare geometrică;
   drumuri multiple cu taguri incompatibile rămân necunoscute. Nu însumăm benzi
   între carosabile și nu atribuim semaforul vecin unei treceri.
4. Vecinătăți în EPSG:32635 (UTM 35N), geometrie completă pentru poligoanele
   școlilor; absența obiectelor într-un răspuns OSM nu dovedește absența în teren.
5. Intersecții numai din topologie rutieră verificată, nu din suprapuneri 2D.
6. Runner observat separat, după primirea accidents.json geolocalizat și a
   manifestului coerent de la colegi; nu combinăm fixture-urile cu OSM real.
7. Validare de consum cu Persoana 6; frontend-ul nu există în checkout.

Input de la Persoana 3: accidents.json, schema 2.0, event_id canonic, coordonate,
precizie_loc și in_iasi. De la integrator: manifest și modul datelor. De la
Persoana 5: reguli/catelog pentru integrarea ulterioară, fără a implementa motorul.
Există `measure.json` la singular, diferit de `measures.json` din contract.
Auditul existent semnalează 18 articole declarate, numai 4 prezente și 14
referințe lipsă. Aceste probleme nu sunt mascate de pipeline-ul de scor.

Implementarea actuală finalizează baza offline, nu întregul pipeline observat.
Scorul este prioritizare în eșantionul documentat, nu probabilitate sau predicție.
