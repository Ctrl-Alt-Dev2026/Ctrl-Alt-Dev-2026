# SafeIași — plan de lucru pentru backend

Actualizat la 17 octombrie 2026. Responsabil propus: **Mihnea**, conform intenției exprimate de el; alocarea rămâne provizorie. **Emi se ocupă de extracția AI**, conform aceleiași discuții. Ceilalți colegi nu sunt nominalizați prin acest document.

## Aria noastră

Backend-ul conectează modulele și frontend-ul: validează rezultatele extracției, păstrează candidații separat de evenimentele aprobate, expune operațiile de corectare/aprobare și livrează datele pentru hartă și dosare. Extracția AI aparține lui Emi; geocodarea, scorul, recomandările, frontend-ul și pitch-ul rămân responsabilități distincte. Mihnea nu este desemnat automat coordonator P1.

Emi a livrat `extract_article(article) -> candidates` în commitul `7765748`, cu câmpuri posibil necunoscute, referințe la surse și pasaje-dovadă, identificarea rulării/modelului/promptului și erori explicite. `ExtractionService` și routerul său sunt integrate în pornirea standard `api.main:app`. Extracția returnează candidați `pending` și nu aprobă automat un accident. Backend-ul poate acum salva articolul și extracția originală, înregistra corecturi versionate și decizia operatorului, conform [fluxului de review](REVIEW_WORKFLOW.md). Publicarea pe hartă rămâne separată.

Actualizare de scope cerută de Mihnea: opțiunea AI 4 este implementată ca [SafeCross](SAFECROSS.md), un modul video local separat, cu interfață, review și export. Observațiile nu sunt convertite în accidente sau scoruri. Această extensie nu înlocuiește pașii 5–6 ai fluxului principal și nu dublează extracția textului de către Emi.

Actualizare din `main`, commit `b6cecb9`: există acum modulele colegului pentru [context OSM](../context/CITY.md) și [scor offline](../risk/IMPLEMENTATION.md). Integrarea lor cu API-ul rămâne pasul 5; formulările de mai jos despre scorul de implementat se referă la backend și la reconcilierea contractelor comune.

Emi a livrat și [investigatorul de tipare, opțiunea 6](../ai/patterns/README.md), integrat în `main` la `0e8d1ae`. Backend-ul comun înregistrează atât `/patterns`, cât și `/safecross`, alături de extracție și review. Nu construim alt motor de grupare. Pregătirea vectorilor folosește sursele fixate din `false_data/`; importurile și evenimentele aprobate ulterior nu intră automat în acest corpus. Până la un contract pentru un corpus observat și regenerare explicită, opțiunea 6 rămâne explorare sintetică separată de publicare și de video.

Verificarea comună după integrarea opțiunilor 4 și 6: **95 teste backend/video, 42 extracție și 21 tipare trecute**, plus **684 comparații Python/JavaScript**. În browser au fost verificate dovezile, excluderea unui caz (suport 4 → 3), abținerea în modul surse, resetarea și exportul. Rezultatul video și review-ul salvat au rămas neschimbate. Vizualizarea opțiunii 6 regrupează vectori pregătiți; nu prezentăm acest pas drept inferență nouă a modelului.

Prioritatea următoare rămâne fluxul comun: surse observate și evenimente canonice verificate, un contract de publicare către context/scor, apoi harta și dosarele. Pentru un corpus observat al opțiunii 6 trebuie păstrate proveniența pe câmp, deduplicarea și regenerarea explicită. Nu legăm clipul din Toronto de o locație din Iași și nu folosim similaritatea semantică drept scor rutier. Demo-urile separate sunt disponibile pentru pregătirea prezentării, fără să ascundă aceste dependențe.

## Baza de lucru verificată

- Bază Git: `origin/main`, commit `77b0a09`; nu exista aplicație sau fișier de dependențe.
- Echipa a adăugat `false_data/`, cu manifest `schema_version: "2.0"`, `data_mode: "synthetic"`.
- Fișierele existente sunt `articles.json`, `accidents.json`, `crossings.geojson`, `hotspots.json`, **`measure.json`**. Ultimul are numele la singular; nu îl redenumim în locul colegului.
- Continuăm întâi compatibilitatea cu aceste fixture-uri. Schema `1.0` GeoJSON din [planul atașat](HACKATHON_PLAN.md) rămâne o propunere alternativă; nu migrăm în tăcere contractele comune.
- Python + FastAPI pentru API este direcția deja propusă în [Planificare.md](../Planificare.md). Primul pas a fost auditul fără framework; etapa de pornire adaugă acum FastAPI/Uvicorn, `/health` și instrucțiunile din [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md), în ramura backend. Acesta este scheletul serverului, nu fluxul produsului implementat.

Auditul inițial a găsit **4 articole, 17 evenimente, 7 obiecte de infrastructură, 5 locații și 6 măsuri**. Manifestul declară **18 articole**, iar evenimentele referă **14 ID-uri de articole lipsă** (`syn-005`–`syn-018`). Nu completăm aceste articole prin invenție. Cele patru evenimente cu `verificat: true` sunt tot sintetice, nu accidente reale confirmate.

Fixture-urile includ costuri și reduceri sintetice, iar unele locații agregă evenimente încă neverificate. Ele nu devin automat un snapshot publicabil. Auditul actual verifică structura și consistența de bază, fără validare factuală, geocodare, calcul de scor sau aprobarea recomandărilor.

## Pașii pe care îi urmăm

Estimările sunt ore de lucru activ, nu un nou calendar de 25 de ore. Dependențele de colegi se tratează separat. Ordinea etapelor rămâne aceeași chiar dacă reducem scope-ul.

| Pas | Livrabil și criteriu de terminare | Estimare | Stare |
|---|---|---|---|
| 0. Delimitarea responsabilităților | Mihnea: backend/API, provizoriu; Emi: extracție; modulele colegilor nu sunt duplicate | 15 min | Documentat |
| 1. Auditul contractului existent | Comandă repetabilă, erori explicite pentru referințe/totaluri/mod de date; fixture-urile originale rămân nemodificate | 30–45 min | Implementat; auditul semnalează problemele de mai sus |
| 2a. Pornirea locală | Mediu `.venv`, FastAPI/Uvicorn, `/health`, OpenAPI și instrucțiuni; fără chei sau date necesare pentru pornire | 30 min | Implementat și verificat în ramura backend |
| 2b. Citirea datelor | Snapshot sintetic `2.0` validat la pornire, manifest/evenimente, identificator comun și erori explicite | 30 min | Implementat; setul actual este refuzat corect; datele observate nu sunt încă suportate |
| 3a. Integrarea extracției lui Emi | Router AI în pornirea standard, contract `2.0`, erori explicite, reluări etichetate, compatibilitate cu snapshot-ul | 30 min | Implementat; nu persistă și nu aprobă candidații |
| 3b. Importul cu salvare | Validează rezultatele și salvează candidații/proveniența separat de evenimentele aprobate; tratare repetări și erori | 60–90 min | Implementat; JSON local, moduri separate, idempotență și dovezi verificate în text |
| 4. Corectare și aprobare | Operatorul vede dovezile, corectează și aprobă/respinge; actualizări atomice, istoric de verificare și versiune pentru evitarea suprascrierilor; duplicatele păstrează un ID canonic | 90 min | API implementat; asociere explicită a surselor; ecranul de review urmează la frontend |
| 5. Integrarea cu frontend-ul | Listă și dosar de locație, citite din exportul modulului de prioritizare; GeoJSON în ordinea lon/lat; filtrele și totalurile coincid | 45–60 min | De făcut; depinde de frontend și P3/P4 |
| 6. Repetiția și rezerva | Fluxul import → verificare → date publicabile funcționează pe laptopul demo; testele de consistență trec; reluare locală explicită dacă AI nu răspunde | 45–60 min | De făcut |

**Pașii 2a–4 sunt implementați la nivel de API local. Următorul pas este 5:** conectarea frontend-ului și reconcilierea datelor pentru hartă cu modulele colegilor. Importul și review-ul funcționează independent de snapshot-ul incomplet, fără a ascunde erorile acestuia. Încărcarea unui set pentru hartă așteaptă corectarea sau înlocuirea fixture-urilor incomplete și o etapă explicită de publicare. Cititorul sintetic nu publică date observate. Detalii în [contractul citirii](SNAPSHOT_READ_API.md).

## API implementat și operații propuse

Sunt implementate `GET /health`, `/docs`/OpenAPI, citirea sintetică prin manifest/evenimente, extracția AI și importul/review-ul de mai jos. Dosarul locației rămâne o propunere. `POST /extract` este aliasul compatibil al aceluiași handler AI, fără un al doilea extractor.

| Operație | Comportament așteptat |
|---|---|
| `GET /health` | Confirmă că serverul rulează; nu pretinde că AI sau setul de date sunt disponibile |
| `GET /api/v1/manifest` | Implementat pentru snapshot sintetic: manifest, versiune SHA-256 și număr eligibil; 503 pentru set invalid |
| `POST /api/v1/ai/extract` | Implementat: articol `2.0` → candidați `pending`, dovezi/proveniență, mod de procesare și erori; fără salvare |
| `GET /api/v1/ai/replays/{article_id}` | Implementat: reluare sintetică salvată, explicit etichetată și neverificată |
| `POST /api/v1/imports` | Implementat: articol, mod explicit și cheie idempotentă; validează extracția și salvează candidați neverificați |
| `GET /api/v1/candidates/{id}` | Implementat: articol, extracție originală, valori curente, istoric și versiune; există și listă filtrabilă |
| `PATCH /api/v1/candidates/{id}` | Implementat: corectează numai câmpurile editabile, cu motiv și versiune; păstrează dovezile originale |
| `POST /api/v1/candidates/{id}/review` | Implementat: aprobă/respinge sau asociază unui eveniment canonic, cu operator, moment și verificări explicite |
| `GET /api/v1/reviewed-events` | Implementat: evenimente canonice locale cu toate sursele; nu sunt publicate automat în snapshot |
| `GET /api/v1/events` | Implementat pentru evenimente sintetice eligibile; etichetă permanentă și filtrare după review/municipiu/perioadă/precizie |
| `GET /api/v1/locations/{id}` | Dosar: evenimente unice, surse, context, scor și recomandări furnizate de modulele colegilor |

Pentru MVP: fișiere JSON locale, fără bază de date sau cloud nou; extensia video se instalează separat și nu este o dependență a importului de articole. Scrierile se proiectează pentru un singur proces local, cu blocare și înlocuire atomică; procesele multiple necesită alt mecanism de persistență. Nu expunem operațiile de scriere public fără un control de acces proiectat separat. Nu implementăm încă o formulă de scor; alegerea între cele două planuri aparține echipei înainte de clasament.

## Verificarea etapelor implementate

Din rădăcina repository-ului, cu Python 3.12 disponibil în mediul inspectat:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m api.validate_fixtures false_data
```

Auditul doar citește și emite un raport JSON: cod `0` pentru fixture-uri coerente, `1` pentru neconcordanțe. Acceptă numai fixture-uri **sintetice**, pe schema `2.0`; nu este validator pentru publicarea datelor observate. Testele verifică date lipsă, dubluri, referințe rupte și coordonate invalide pe fișiere temporare sintetice, plus răspunsurile HTTP și pornirea fără chei sau fișiere de date.

Există serverul local, citirea de snapshot sintetic validat, integrarea extractorului lui Emi și importul/review-ul cu persistență locală. Inferența live necesită Ollama/model disponibil; regulile și reluările sintetice pot fi verificate fără el. Publicarea datelor observate și conexiunea cu frontend-ul nu sunt încă implementate. Deciziile finalizate nu pot fi redeschise/editate în acest MVP; operatorul declarat nu este autentificat. Această etapă nu înseamnă finalizarea backend-ului.

## Timp și reguli de lucru

Conform [programului consultat pe 17 octombrie](https://markaiintegrator.ro/hackathon-ai/), predarea începe pe 18 octombrie la 16:30, Europe/Bucharest. Țintim pachetul pregătit la **14:30**, pentru două ore rezervă. Un nou ciclu complet de 25 de ore pornit după 17 octombrie, 13:30, consumă din acea rezervă; planul inițial trebuie comprimat la ora efectivă de start. Păstrăm odihna și repetițiile, reducem extensiile și volumul înaintea verificărilor.

Lucrăm pe ramuri `codex/`, cu schimbări mici, teste pentru riscurile reale și integrare devreme. Fiecare pas se închide cu livrabil, verificări și limitări consemnate. P1 rămâne singurul coordonator al schemelor/dependențelor comune; propunerile de mai sus se reconciliază înainte de implementarea etapelor care le folosesc. Nu facem merge automat și nu publicăm issues sau mesaje către colegi prin această sarcină.
