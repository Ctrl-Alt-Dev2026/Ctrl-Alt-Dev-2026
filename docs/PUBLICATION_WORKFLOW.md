# Publicare locală și dosare de locație

Flux implementat: **import → extracție → corectare/review → eveniment canonic → asociere verificată la locație → preview → publicare explicită → listă/hartă GeoJSON → dosar → export JSON/HTML**.

Backend v0.7 adaugă [preview și aplicare asistată a geocodării](GEOCODING_WORKFLOW.md) pentru candidații observați încă pending. Nu înlocuiește confirmarea operatorului sau asocierea explicită la publicare.

Publicarea înseamnă o versiune locală pentru consumul frontend-ului. Nu publică date pe internet și nu înlocuiește verificarea administrației. Cele trei ecrane Angular sunt [conectate la acest flux](FRONTEND_INTEGRATION.md); datele reale ale unui pilot trebuie pregătite și verificate separat.

## Instalare și configurare

Din rădăcina repository-ului, cu Python 3.12 și mediul din [ghidul local](LOCAL_DEVELOPMENT.md):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-publication.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Dependențele geometrice sunt importate la utilizarea publicării/contextului. Pornirea API-ului, extracția, review-ul și vizualizarea tiparelor rămân independente de ele. Modelul video nu este necesar publicării. Nicio comandă de pornire nu colectează date sau descarcă modele.

| Configurare | Implicit |
|---|---|
| `SAFEIASI_REVIEW_DIR` | `runtime/review` — date de lucru și decizii |
| `SAFEIASI_PUBLICATION_DIR` | `runtime/publications` — versiuni și index separat pe mod |
| `SAFEIASI_PUBLICATION_CONTEXT_DIR` | `context/output/observed/iasi` — exportul OSM al colegului |

Un context observat se folosește numai cu evenimente `observed`. Contextul sintetic trebuie configurat explicit într-un director separat. Lipsa unei publicații într-un mod produce **404 `publication_not_found`**; nu se înlocuiește cu date din celălalt mod. Rutele noi sunt accesibile numai local, din aceeași origine, ca review-ul.

## Repetiție sintetică completă

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m api.demo_publication --directory runtime/publication-demo
```

Comanda creează **șapte articole fictive, șase evenimente canonice și trei locații fictive**, folosind rutele reale ale aplicației prin clientul local de test. Un al doilea articol este legat aceluiași eveniment, păstrând ambele surse. Extracția folosește `rules`, fără model sau Ollama; nu este o demonstrație de inferență AI nouă. Coordonatele sunt introduse ca o corectură explicită de operator, nu sunt geocodate automat. Cauza necunoscută rămâne necunoscută.

Sursele, limita, coordonatele și infrastructura sunt etichetate **SINTETIC**. Limita de demo nu este limita administrativă reală a Iașului. Datele de publicare a articolelor sunt separate de datele evenimentelor. Directorul conține review-ul, contextul, versiunea publicată, cele trei fișe JSON/HTML și `proof.json` cu rezultate și hash-uri. Un director existent este refuzat; folosește alt nume pentru o nouă repetiție. `false_data/`, corpusul de tipare și datele observate nu sunt modificate.

Pentru vizualizare într-un server de demo separat, într-un **al doilea terminal**:

```powershell
$env:SAFEIASI_REVIEW_DIR = (Resolve-Path 'runtime/publication-demo/review').Path
$env:SAFEIASI_PUBLICATION_DIR = (Resolve-Path 'runtime/publication-demo/publications').Path
$env:SAFEIASI_PUBLICATION_CONTEXT_DIR = (Resolve-Path 'runtime/publication-demo/context').Path
$env:SAFEIASI_SAFECROSS_DIR = Join-Path (Resolve-Path 'runtime/publication-demo').Path 'safecross'
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

[UI conectată, după `npm run build:local` în `web/`](http://127.0.0.1:8001/ui/?data_mode=synthetic), [Swagger demo](http://127.0.0.1:8001/docs), [lista locațiilor](http://127.0.0.1:8001/api/v1/locations?data_mode=synthetic), [GeoJSON](http://127.0.0.1:8001/api/v1/locations.geojson?data_mode=synthetic), [fișa imprimabilă Alfa](http://127.0.0.1:8001/api/v1/locations/demo-crossing-01/export?data_mode=synthetic&format=html). HTML-ul se poate tipări/salva PDF din browser; serverul nu generează PDF. Închide terminalul de demo pentru a elimina configurarea sa de mediu. Directorul video separat protejează analizele SafeCross ale serverului normal.

## Asociere și eligibilitate

1. Importă și verifică articolul conform [fluxului de review](REVIEW_WORKFLOW.md); aprobă sau asociază la un eveniment canonic. Nu aproba din nou același accident pentru fiecare articol.
2. Verifică manual coordonatele, precizia și apartenența la municipiu, consemnând `location_evidence`. Aprobarea localizării cere `location_checked=true`.
3. Consultă `GET /api/v1/publication-context?data_mode=observed&q=...` și selectează explicit locația. API-ul nu alege cel mai apropiat obiect în locul operatorului.
4. Trimite versiunea curentă a evenimentului, justificarea asocierii și confirmarea verificării diferențelor dintre surse. Preview-ul arată eligibilitatea și scorul; nu scrie publicații și nu schimbă review-ul.
5. Publică numai o selecție fără excluderi. Corectează sau scoate explicit din selecție cazurile neeligibile.

Exemplu de corp pentru ambele operații POST; ID-urile și versiunile sunt ilustrative și trebuie înlocuite cu cele returnate de API:

```json
{
  "request_id": "publication-2026-10-17-01",
  "data_mode": "observed",
  "operator": "operator-local",
  "note": "Selecție verificată pentru dosare, nu inventar complet.",
  "period_start": "2025-01-01",
  "period_end": "2026-10-17",
  "source_conflicts_checked": true,
  "selections": [{
    "event_id": "evt_ID_RETURNAT_DE_REVIEW",
    "expected_version": 1,
    "location_id": "osm-node-ID_DIN_CONTEXT",
    "association_checked": true,
    "association_note": "Sursa și geometria au fost confruntate; asociere verificată manual."
  }]
}
```

Este necesară o dată a evenimentului în perioada inclusivă, coordonate precise în limita geometrică, `in_iasi=true`, dovezi de localizare și decizii de verificare. Precizia trebuie să coincidă cu tipul infrastructurii. Contextul observat actual conține treceri, nu un inventar de intersecții sau segmente. Un segment/o localizare vagă nu este promovat(ă) la o trecere prin proximitate.

Distanța maximă de **50 m** este o verificare suplimentară pentru asocierea deja aleasă și confirmată, nu dovada asocierii. Verificarea observată folosește limita OSM a municipiului și EPSG:32635; inclusiv inversarea lon/lat este respinsă dacă mută punctul în afara limitei. Tagurile necunoscute rămân `null`; existența infrastructurii OSM nu dovedește existența unui accident.

[Modulul de coordonate](../coordonate/README.md), adăugat în `main` la `22cbb51`, poate produce propuneri offline din `loc_text`, dar nu este apelat automat de acest flux. Propunerile trebuie verificate înainte de aprobarea candidatului. Un rezultat `strada` are coordonate reprezentative în contractul acelui modul, dar nu este acceptat ca punct precis de `CandidateFields`; se păstrează separat până la un contract agreat pentru afișarea aproximativă. Preciziile `segment`/`intersectie` nu se asociază unei treceri doar pentru că sunt în apropiere. Repetiția de aici folosește în mod deliberat coordonate fictive într-un context integral sintetic.

## Contract pentru frontend

| Rută | Răspuns / utilizare |
|---|---|
| `GET /api/v1/publication-context` | Metadate, atribuire și infrastructură selectabilă; `data_mode`, `q`, `limit`, `offset` |
| `POST /api/v1/publications/preview` | Eligibile/excluse, motive, dosare și scoruri propuse; `persisted=false` |
| `POST /api/v1/publications` | `{snapshot, reused}`; 201 la prima publicare, 200 la repetarea identică |
| `GET /api/v1/publications` | Lista versiunilor comise în modul ales |
| `GET /api/v1/publications/latest` | Ultima versiune comisă, cu surse și proveniență |
| `GET /api/v1/publications/{snapshot_id}` | O versiune explicită, înghețată |
| `GET /api/v1/publications/{snapshot_id}/events` | Evenimentele canonice ale aceleiași versiuni |
| `GET /api/v1/locations` | Listă ordonată și paginată; `q`, `ranked_only`, `limit`, `offset` |
| `GET /api/v1/locations.geojson` | Aceleași locații, scoruri și ID-uri pentru hartă; coordonate **[lon, lat]** |
| `GET /api/v1/locations/{location_id}` | Dosar: evenimente, surse, context, scor, necunoscute și audit |
| `GET /api/v1/locations/{location_id}/export` | JSON; `format=html` pentru fișa imprimabilă |

Citirile publicațiilor/locațiilor folosesc `data_mode=synthetic` implicit; frontend-ul trebuie să îl trimită explicit. Locațiile și exportul acceptă opțional `snapshot_id`. Frontend-ul fixează aceeași versiune pentru listă, hartă și dosar, ca o publicare concurentă să nu schimbe totalurile între cereri.

Metadatele comune includ perioada, avertismentele, `snapshot_id`, hash-ul, atribuirea contextului și hash-ul formulei. `location_count`/`eligible_event_count` descriu versiunea completă; `filtered_location_count`/`filtered_event_count` descriu filtrul; `returned_location_count` descrie pagina. Filtrele de afișare nu recalculează scorurile/rangurile. Altă perioadă de analiză cere o nouă publicare explicită.

## Scor, dovezi și limite

Adaptorul apelează **`risk.pipeline.score_location` existent**, cu aceeași formulă. Numără evenimente canonice, nu articole. Datele necunoscute și componentele scorului sunt vizibile. Sunt clasate numai locațiile cu minimum două evenimente eligibile; un singur eveniment poate avea dosar, cu `score=null` și `rank=null`. Pragul este o regulă a prototipului, nu o validare statistică. La egalitate se folosește ID-ul locației pentru o ordine stabilă.

Corpul dosarului păstrează câmpurile curente, pasajele originale, corecturile, deciziile operatorului, toate articolele și justificarea asocierii. `publicat_la` nu devine data accidentului. `candidate_measures=[]` indică lipsa unui catalog integrat cu surse și aplicabilitate; nu sunt inventate costuri sau efecte. Integrarea măsurilor rămâne un pas separat.

Publicarea suportă și modul `observed`, dar **această livrare nu colectează și nu certifică evenimente reale**. Datele observate necesită surse și verificare umană efectivă. Scorul descrie eșantionul selectiv, fără probabilitate de accident, expunere sau reducere estimată. Nu combină evenimentele sintetice cu contextul OSM real. `/patterns` rămâne un corpus pregătit separat; SafeCross nu creează automat evenimente de accident.

Rutele vechi `/api/v1/events` și `/api/v1/manifest` păstrează cititorul sintetic anterior și răspunsul 503 pentru fixture-urile incomplete. Frontend-ul nou consumă rutele de publicații/locații, nu interpretează acel 503 ca publicație goală. Starea `not_published` din review rămâne starea documentului de lucru; apartenența la o versiune publicată se citește din publicații, fără rescrierea istoricului review.

## Persistență și erori

Versiunile sunt fișiere imuabile, cu hash verificat la citire. Un index atomic este punctul de comitere: o eroare la salvare păstrează ultima versiune, iar un fișier rămas neindexat nu este accesibil ca publicație. Repetarea aceluiași `request_id` și corp returnează versiunea deja comisă; reutilizarea cu alt corp produce 409. O versiune de eveniment depășită produce 409. Selecțiile cu excluderi produc 422 și motivele, fără publicare parțială. Lipsa dependențelor/contextului sau fișierele corupte produc 503.

Proveniența păstrează hash-ul review-ului, contextului, sursei formulei și funcției efectiv încărcate. Dacă formula din fișier diferă de cea încărcată, calculul este refuzat cu `scorer_changed_restart_required`; verifică schimbarea și repornește serverul. Modificarea datelor de review după publicare nu schimbă retroactiv versiunea înghețată. Rularea suportată este un singur proces local, fără autentificare multiutilizator sau expunere publică.

Verificări:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/patterns/tests -v
.\.venv\Scripts\python.exe -m unittest context.test_city context.test_context risk.test_pipeline risk.test_scenario risk.test_inspect -v
```

Testele includ dubluri, versiuni concurente, date necunoscute, geometrie și moduri incompatibile, fișiere corupte, eșec de scriere, repornire, concordanță hartă/listă/dosar, escaparea HTML și protejarea corpusului comun. Ele verifică mecanica aplicației; nu sunt o evaluare factuală a unui set de accidente reale.

Verificarea din 17 octombrie 2026: **225 teste trecute** — 139 backend/video/publicare, 42 extracție, 21 tipare și 23 context/scor. `pip check` nu a găsit conflicte. Repetiția reală prin API a produs cele trei fișe sintetice, iar verificarea în browser a confirmat totalurile, absența erorilor JavaScript și afișarea mobilă fără depășire orizontală. Serverul normal citește cele 1.210 treceri OSM, fără să preia automat publicația sintetică a serverului de demo. Analiza SafeCross și review-ul salvat au rămas intacte.

Separat, `python -m coordonate autotest` trece 43 de verificări offline. Integrarea v0.7 în review este documentată în [fluxul geocodării](GEOCODING_WORKFLOW.md); punctele aproximative rămân în raport, iar aprobarea și publicarea rămân explicite.
