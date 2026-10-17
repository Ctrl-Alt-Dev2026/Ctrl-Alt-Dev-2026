# Contract de integrare frontend — API v0.7

Acesta este contractul pentru construirea celor trei ecrane principale; nu declară că interfața produsului este implementată. Detalii: [review](REVIEW_WORKFLOW.md), [geocodare](GEOCODING_WORKFLOW.md), [publicare](PUBLICATION_WORKFLOW.md). Schemele exacte sunt în `/openapi.json` și `/docs`.

## Ecrane și date disponibile

1. **Hartă și priorități:** locații publicate, perioadă, filtre, numărul evenimentelor distincte și explicația scorului.
2. **Dosarul locației:** evenimente canonice, toate articolele, dovezi originale, corecturi, audit, context, necunoscute și export.
3. **Import și verificare:** sursa integrală, extracția originală lângă câmpurile curente, corecturi, geocodare opțională și decizia operatorului.

| Server local | Stare la verificarea din 17 octombrie 2026 |
|---|---|
| `http://127.0.0.1:8000` | API normal; fără publicație și fără set de accidente observate pregătit. Infrastructura OSM nu este un set de accidente. |
| `http://127.0.0.1:8001` | Repetiție separată, integral **SINTETICĂ**: șapte articole fictive, șase evenimente, trei locații. [Lista](http://127.0.0.1:8001/api/v1/locations?data_mode=synthetic), [fișa Alfa](http://127.0.0.1:8001/api/v1/locations/demo-crossing-01/export?data_mode=synthetic&format=html). |

Datele runtime nu sunt livrate prin Git și disponibilitatea serverelor depinde de pornirea lor locală; comenzile sunt în ghidul de publicare. Ollama și `qwen2.5:1.5b` lipsesc momentan pe laptopul verificat. Alege explicit `pipeline=rules` pentru extracție deterministă fără model. Reluările `/api/v1/ai/replays/{article_id}` sunt sintetice, salvate și etichetate **reluare**, fără import/aprobare automată. `cache` și extracțiile istorice nu se prezintă ca procesare live.

Toate rutele de lucru/publicare sunt locale și cer aceeași origine. Servește frontend-ul din originea API-ului; alt port este altă origine și primește 403. `operator` este declarat pentru istoric, fără autentificare. Trimite `data_mode=synthetic|observed` explicit în fiecare cerere relevantă și nu combina modurile, serverele sau contextele. Un import sintetic cere `article.sursa=SINTETIC`; eticheta `observed` nu certifică autenticitatea sursei.

## Ordinea operațiilor

| Pas | Rută și contract minim |
|---|---|
| Import | `POST /api/v1/imports`: `{request_id, data_mode, operator, pipeline, article}`; articolul are `article_id, sursa, url, titlu, text, publicat_la, colectat_la`. 201 nou / 200 reutilizat. |
| Citire | `GET /api/v1/candidates?data_mode=...&status=pending`, apoi `GET /api/v1/candidates/{id}?data_mode=...`; păstrează `candidate.version`, articolul și extracția originală. |
| Corectare | `PATCH /api/v1/candidates/{id}`: `{data_mode, expected_version, operator, reason, changes}`; folosește versiunea returnată în continuare. |
| Localizare opțională | Preview/aplicare separate, descrise mai jos; numai `observed` și candidat `pending`. |
| Decizie | `POST /api/v1/candidates/{id}/review`: `{data_mode, expected_version, operator, note, action}` plus verificările efectuate. |
| Evenimente | `GET /api/v1/reviewed-events?data_mode=...`; evenimente canonice și versiunile lor pentru selecția de publicare. |
| Context | `GET /api/v1/publication-context?data_mode=...&q=...&limit=50&offset=0`; alegere explicită a infrastructurii. |
| Publicare | `POST /api/v1/publications/preview`, apoi separat `POST /api/v1/publications`, cu selecția verificată; aprobare fără publicare automată. |

`approve` și `link` cer `source_checked=true` și `duplicate_checked=true`; localizarea cunoscută cere `location_checked=true`, iar un pin și `location_evidence`. Pentru alt articol despre același accident folosește `link`, cu `canonical_event_id` și `expected_event_version`, nu o nouă aprobare. Deciziile sunt finale în acest MVP. `reject` nu creează un eveniment. Importul poate avea zero candidați; nu inventa un caz.

Geocodarea are două operații: `POST /api/v1/candidates/{id}/geocoding/preview` cu `{data_mode, expected_version}` returnează `proposal`; afișează `current_location`, `proposed_changes`, raportul, referințele OSM, avertismentele și proveniența. După verificare, `POST .../geocoding/apply` primește `{data_mode, expected_version, suggestion_id, operator, reason, location_checked:true}`. Clientul nu trimite coordonate sau raport în această operație; serverul recalculează sugestia. Nu bifa confirmarea automat. Aplicarea lasă candidatul `pending`; review-ul folosește noua versiune.

`strada` păstrează punctul reprezentativ în raport, cu `lat/lon=null` pe candidat; `vag` nu primește pin precis. Geocodarea sintetică este refuzată. Schimbarea `loc_text` invalidează localizarea veche; recitește candidatul și cere alt preview. Contextul publicării observate conține treceri: o intersecție sau un segment nu devine trecere prin proximitate.

Corpul de publicare are `{request_id, data_mode, operator, note, period_start, period_end, source_conflicts_checked:true, selections}`. Fiecare selecție are `{event_id, expected_version, location_id, association_checked:true, association_note}`. Perioada folosește data accidentului, inclusiv capetele. Preview-ul arată `diagnostics`, eligibile/excluse și `persisted=false`; publică numai după rezolvarea excluderilor. Publicarea returnează `{snapshot, reused}`: 201 prima dată / 200 repetarea identică. Păstrează același `request_id` pentru retry identic; alt corp cu aceeași cheie produce 409.

## Citire coerentă pentru hartă, dosar și export

1. Citește `GET /api/v1/publications/latest?data_mode=...` o dată și fixează `snapshot_id`; selectorul de versiuni poate folosi `GET /api/v1/publications?data_mode=...`.
2. Folosește **același `data_mode` și `snapshot_id`** pe toate citirile de mai jos, inclusiv exportul; astfel o publicare concurentă nu schimbă totalurile în timpul navigării.

| Rută GET | Conținut / parametri suplimentari |
|---|---|
| `/api/v1/locations` | Listă; `q`, `ranked_only`, `limit`, `offset`. |
| `/api/v1/locations.geojson` | Hartă; aceleași filtre `q`, `ranked_only`, fără paginare; coordonate **[longitudine, latitudine]**. |
| `/api/v1/locations/{location_id}` | `location`, `events`, surse, audit și proveniență pentru versiunea fixată. |
| `/api/v1/locations/{location_id}/export` | JSON implicit; `format=html` pentru fișa imprimabilă, salvabilă PDF din browser. |
| `/api/v1/publications/{snapshot_id}/events` | Toate evenimentele canonice din versiunea aleasă; trimite și `data_mode`. |

`eligible_event_count` și `location_count` sunt totalurile versiunii; `filtered_event_count`/`filtered_location_count` descriu filtrul, iar `returned_location_count` pagina. Numără accidente canonice, separat de articole. Filtrarea nu recalculează scorul sau rangul; altă perioadă cere publicare nouă. Pentru un singur eveniment eligibil, locația poate avea dosar cu `score=null` și `rank=null`.

Afișează perioada, eticheta modului, `warnings`, `context_attribution` și necunoscutele (`unknowns`, `score_details.date_lipsa`, câmpuri `null`). Scorul este o prioritate explicabilă în eșantionul selectiv, nu o probabilitate de accident. Absența unui tag OSM nu dovedește absența infrastructurii. Păstrează distincte `publicat_la` și `data_eveniment`. Sursele și textele se redau ca text, nu HTML injectat. `candidate_measures=[]` înseamnă catalog neintegrat; nu genera măsuri, costuri sau efecte din acest gol. `/patterns` și SafeCross rămân module separate, fără alimentare automată a acestui flux.

## Stări și erori

| HTTP | Reacție în interfață |
|---|---|
| 403 | Explică accesul local/din aceeași origine; nu încerca ocolirea restricției. |
| 404 | Pentru `publication_not_found`, arată „Nicio versiune publicată în acest mod”; pentru alte ID-uri, element inexistent. |
| 409 | Versiune/identitate/propunere schimbată sau candidat finalizat: recitește starea; nu relua mutația orbește. |
| 422 | Afișează validarea și motivele excluderii; păstrează formularul pentru corectare explicită. |
| 502 / 503 | Extracție invalidă / AI, context sau stocare indisponibilă: arată eșecul, fără succes fictiv sau fallback ascuns. |

Folosește `detail.code`, `detail.message`, `detail.issues` când există; validarea FastAPI poate avea `detail` listă. La import AI indisponibil se întoarce și `persisted=false`. Nu transforma un 503 în listă goală sau date sintetice. Rutele legacy `/api/v1/events` și `/api/v1/manifest` pot da 503 pentru fixture-uri incomplete; ecranele noi consumă publicațiile/locațiile. `publication_status=not_published` din review rămâne starea documentului de lucru; publicarea se verifică în snapshot.

## Acceptanță smoke pentru integrarea viitoare

1. Pe demo 8001, modul sintetic este vizibil; lista, GeoJSON și dosarele au același `snapshot_id`, trei locații și șase evenimente din șapte articole.
2. Dosarul Alfa păstrează două evenimente și trei articole; articolul duplicat nu crește numărul accidentelor.
3. Filtrele/paginarea separă totalurile de pagina afișată, păstrând rangurile; coordonatele hărții sunt `[lon,lat]`.
4. Importul `rules` este etichetat; extracția originală, corectura și data publicării se disting. O reluare salvată nu apare ca AI live.
5. Pe un candidat de test `observed/pending`, preview-ul geografic nu scrie; aplicarea cere confirmare, iar o versiune veche primește 409.
6. Un rezultat `strada/vag` nu produce pin precis sau asociere automată; aplicarea geocodării nu aprobă candidatul.
7. Aprobarea/link-ul și publicarea sunt acțiuni separate; excluderile/422 blochează publicarea, iar 404/503 nu încarcă alt mod de date.
8. Exportul JSON/HTML folosește versiunea fixată, păstrează sursele, atribuirea și necunoscutele; interfața mobilă rămâne lizibilă, fără erori JavaScript.
