# Preview: frontend nemodificat + treceri OSM reale + accidente demo

Actualizare după 7c1a193: frontend-ul implicit este HTTP. Helper-ul compilează
explicit configurațiile development,mock în risk/output/frontend-app-mock/.
Copia veche frontend-app nu este reutilizată automat. Nu trimite acest set mixt
în fluxul de publicații backend, care separă strict observed și synthetic.
Vezi FRONTEND_HANDOFF.md pentru integrarea catalogului OSM prin noul API.

Setul separat este în `risk/output/frontend-scenario/data/`. Nu am copiat nimic
în data/, false_data/ sau web/public/data/ și nu am modificat surse frontend.

Include toate cele 1.210 treceri reale, cu aceleași geometrii și taguri de context.
Numele lipsă primesc numai etichete de afișare din numele reale ale drumurilor
conectate sau din ID-ul OSM, fără inventarea unei denumiri de loc.

Trei locații au scenarii explicite cu câte trei accidente demo:

| Trecere reală | Accidente demo | Context OSM | Total scenariu |
|---|---:|---:|---:|
| Aleea Grigore Ghica Vodă, osm-node-3372032447 | 9 | 4 | 13 |
| Bulevardul Dacia, osm-node-6910606104 | 7 | 4 | 11 |
| Strada Sfântul Lazăr, osm-node-6194970559 | 7 | 2 | 9 |

Nu există accidente reale documentate aici în acest set. Coordonatele originale
ale fixture-urilor nu sunt folosite: atribuirea este ipotetică și înregistrată
în scenario_provenance.json. ID-urile de evenimente au prefix scenario-.
Referințele la presă sunt eliminate, articolele și măsurile sunt liste goale;
nu implementăm recomandări sau costuri ale Persoanei 5. Cauzele originale ale
fixture-urilor nu sunt prezentate ca dovezi despre drumurile reale.

Manifestul folosește valoarea existentă synthetic (pentru compatibilitatea UI),
cu avertisment explicit „SCENARIU: OSM real + accidente sintetice”. Nu extindem
enum-ul comun și nu etichetăm setul observed. Datele de accidente, orele și
severitățile sunt demonstrative; toate evenimentele și locațiile sunt neverificate.
Numele locațiilor și explicațiile scorurilor încep cu SCENARIU.

## Pornire locală

Din rădăcina repository-ului:

```powershell
python -m risk.preview
```

Deschide http://127.0.0.1:4201/ . Click pe o locație SCENARIU pentru scor,
explicația detaliată, ore și infrastructura OSM reală. „Despre date” arată
avertismentul complet. Prima pornire compilează frontend-ul existent exclusiv în
`risk/output/frontend-app-mock/`. Serverul local servește aplicația compilată și
înlocuiește rutele /data/ cu setul separat de scenariu. Codul și datele originale
din web/ nu sunt suprascrise. Pornirile următoare reutilizează aplicația compilată.
Nu rulezi npm start, fiindcă acesta sincronizează alte fixture-uri.
Serverul original pe 4200 poate rămâne separat. Oprire: Ctrl+C în terminal.
Necesită node_modules deja instalat în web; npm ci se face separat dacă lipsește.
Copia compilată frontend-app este ignorată prin fișierul propriu risk/.gitignore;
nu trebuie inclusă în commit sau push.

După un update al frontend-ului, alegi un director nou pentru recompilare:

```powershell
python -m risk.preview --app-output risk/output/frontend-app-v2
```

Varianta cu proxy Angular a fost testată și abandonată: middleware-ul Angular
servește asset-urile existente înaintea proxy-ului, deci ar fi amestecat fixture-uri
vechi și noi. Nu este necesară nicio modificare de configurație Angular.

Verificare dintr-un al treilea terminal, rădăcina repository-ului:

```powershell
python -m risk.validate_frontend_preview
python -m unittest risk.test_frontend_scenario -v
```

Pentru regenerare într-un director nou:

```powershell
python -m risk.frontend_scenario --output risk/output/frontend-scenario-v2
```

La servire selectezi același director prin `python -m risk.preview --dataset
risk/output/frontend-scenario-v2`. Generatorul refuză suprascrierea unui director existent.

## Limitele frontend-ului actual

Harta desenează accidentele și hotspot-urile, nu toate crossing-urile încărcate.
Prin urmare vezi trei treceri reale marcate ca scenarii; celelalte 1.207 sunt
disponibile în crossings.geojson, dar nu sunt un strat separat pe hartă.
Pentru toate punctele OSM vizibile simultan, colegul trebuie să adauge acel strat;
nu inventăm accidente sau hotspot-uri cu scor zero ca să forțăm afișarea.

Coloanele actuale sunt HexagonLayer agregat de frontend, nu poligoanele H3 r9
din accidents_h3.geojson (fișierul este pregătit și în set). UI nu îl consumă încă.
Unele titluri fixe vorbesc despre presă, iar fișa de export are un text generic
despre date sintetice; marcajele SCENARIU din date clarifică situația, dar nu am
modificat textele colegului. Acest preview este pentru test local, nu publicare.
