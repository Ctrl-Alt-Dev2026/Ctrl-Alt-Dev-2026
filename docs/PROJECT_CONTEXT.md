# SafeIași — contextul proiectului

## Produs și client vizat

SafeIași este un nume de lucru pentru un instrument de sprijin pentru administrație: **„Ce locații ar trebui verificate prioritar pentru siguranță rutieră și pe ce dovezi ne bazăm?”** Obiectivul este un demo funcțional, credibil și convingător, cu potențial de continuare într-un pilot plătit.

Clientul principal vizat este **Primăria Iași**, cu utilizatori din mobilitate/siguranță rutieră. Nu există un contract, un parteneriat sau o validare de client confirmată. Pilotul de 60–90 de zile pentru 3–5 locații din plan este o propunere de validat.

## Ce există și ce este propus

La inspecția din 17 octombrie 2026, ramura implicită `main`, la commitul `fc61ae58995f21a654b603af77134dcc8605ac89`, conținea doar [Planificare.md](../Planificare.md). Nu existau cod de aplicație, dependențe, teste, seturi de date, README sau `AGENTS.md`; nu există un stack funcțional demonstrat.

[HACKATHON_PLAN.md](HACKATHON_PLAN.md) reproduce integral atașamentul `Plan_SafeIasi_6_persoane_25h (1).md`. Observația sa despre un răspuns GitHub 404 aparține sesiunii anterioare: la adăugarea documentației, clonarea prin Git a reușit și autentificarea locală avea drept de push, deși conectorul GitHub răspundea cu 404. La acel moment, contractele, căile de fișiere, fixture-urile, backlog-ul și funcționalitățile descrise în ambele planuri erau propuneri, nu artefacte implementate sau date deja colectate.

Ulterior, la commitul `77b0a09`, echipa a adăugat `false_data/`: fixture-uri sintetice pe schema `2.0`, fără date reale verificate sau aplicație. Auditul și pașii pentru backend sunt în [BACKEND_WORK_PLAN.md](BACKEND_WORK_PLAN.md). Fixture-urile sunt păstrate în forma colegilor; neconcordanțele lor trebuie rezolvate înaintea integrării.

Alegerea stack-ului și reconcilierea contractelor revin coordonatorului tehnic la începutul implementării. Propunerea existentă de stack trebuie evaluată; Python + Streamlit + pydeck este alternativa din planul atașat pentru pornirea de la zero. Orice stack funcțional găsit ulterior are prioritate față de o rescriere.

## Scope-ul MVP propus

Fluxul principal: **surse despre accidente → extracție AI cu proveniență → verificare umană → localizare → hartă și prioritizare → măsuri candidate → fișă exportabilă**.

1. **Harta locațiilor prioritare:** filtre, perioada analizată și limitele eșantionului.
2. **Dosarul unei locații:** evenimente unice și surse, explicația priorității, precizia localizării, context și recomandări candidate.
3. **Import și verificare:** câmpuri extrase cu dovezi, corectare și aprobare înainte de publicare.

Ținta de lucru este de **20–40 de accidente distincte, verificate**, cu **trei dosare de locație** pregătite și cinci tipuri de măsuri documentate. Planul atașat propune un prag minim de zece evenimente reale pentru demo; dacă datele nu susțin agregări utile, se prezintă dosare individuale și limita eșantionului. Aceste cantități sunt obiective, nu date disponibile. Exportul sprijină verificarea administrației; nu constituie un audit rutier certificat.

**SafeCross** (observații din filmări de la treceri) și **TomTom** sunt extensii opționale, după stabilizarea fluxului principal. Demo-ul trebuie să funcționeze integral fără ele. Transportul public și parcările rămân în afara scope-ului principal al acestui plan.

## Cele șase roluri propuse

| Rol | Responsabilitate |
|---|---|
| P1 — coordonator tehnic | Contracte, schelet, integrare, dependențe comune și rulare |
| P2 — surse și extracție AI | Import, informații structurate, dovezi și proveniență |
| P3 — geocodare și infrastructură | Localizare, delimitarea municipiului, context OSM și H3 |
| P4 — prioritizare și recomandări | Scor determinist, catalog de măsuri și export |
| P5 — frontend | Cele trei ecrane și experiența demo-ului |
| P6 — produs, verificare și pitch | Revizuirea datelor, scenarii, prezentare și rezervă |

Actualizare din 17 octombrie 2026, conform discuției cu Mihnea:

- **Mihnea — backend/API, alocare provizorie:** validarea intrărilor, API-ul pentru frontend, fluxul de verificare/aprobare și integrarea modulelor. Aceasta nu îl desemnează automat P1 și nu îi atribuie toate modulele de date.
- **Emi — extracție AI:** modulul care produce informațiile structurate și dovezile; backend-ul se integrează cu acesta, fără o implementare paralelă a extracției.
- Celelalte responsabilități și coordonatorul P1 rămân de nominalizat de echipă. Numerele P1–P6 din planul atașat nu se confundă cu „Persoana 1–6” din planificarea inițială.

P5 și P6 sunt responsabili diferiți. Integrarea începe devreme pe exemple sintetice conforme contractelor; P1 coordonează singur contractele și dependențele comune. Planul inițial rămâne nemodificat; alocările curente sunt consemnate aici. Backlog-ul rămâne documentat, fără publicare de issues sau atribuiri automate pe GitHub.

## Principii obligatorii

- Un articol nu este un accident: articolele despre același accident se asociază unui singur eveniment, cu sursele păstrate.
- Datele sintetice sunt separate de cele observate și etichetate explicit.
- Necunoscutul rămâne necunoscut (`null`); nu inventăm coordonate, cauze, viteze, costuri sau surse.
- Data publicării este separată de data accidentului; o oră necunoscută nu devine automat 00:00.
- GeoJSON folosește ordinea **[longitudine, latitudine]**; localizarea vagă nu devine automat un punct precis sau o intrare în clasament.
- Lipsa unui tag OSM nu demonstrează absența infrastructurii respective.
- Scorul prioritizează explicabil locațiile din eșantion; nu este o probabilitate validată de accident. Presa nu reprezintă un inventar complet, iar absența unui eveniment din set nu dovedește siguranța unei zone.
- `freeFlowSpeed` din TomTom nu dovedește depășirea actuală a limitei legale.
- Nu aplicăm factori CMF unui scor arbitrar și nu calculăm „accidente evitate anual” dintr-un eșantion selectiv de presă.
- Recomandările sunt măsuri candidate, cu surse, condiții de aplicabilitate și verificări necesare. Costurile și efectele nedocumentate rămân necunoscute.
- AI extrage și explică; scorul se calculează determinist și verificabil, într-un singur loc.
- Operatorul verifică informațiile înainte de publicare.
- Un răspuns AI salvat și redat ulterior este etichetat ca **reluare**, nu drept procesare live. Observațiile video rămân distincte de accidentele documentate.

## Calendar și criterii

Evenimentul are loc în **16–18 octombrie 2026**. [Programul organizatorilor](https://markaiintegrator.ro/hackathon-ai/), reverificat la 17 octombrie, indică predarea pe **18 octombrie, 16:30–17:00**, încheierea lucrului la 17:00 și un pitch de **3 minute + 1–3 minute întrebări**. Criteriile jurizării din 18 octombrie sunt: AI **30%**, impact **25%**, funcționalitatea demo-ului **25%**, prezentare **20%**. Orele de planificare sunt în **Europe/Bucharest (UTC+03:00 la aceste date)**.

Calendarul H0–H+25 este planul inițial, nu o afirmație că mai sunt exact 25 de ore. Exemplul din atașament pornește pe 17 octombrie la 13:30 și încheie pe 18 octombrie la 14:30, cu două ore rezervă până la începutul predării. La reperul inspecției, **17 octombrie, aproximativ 14:05**, rămâneau aproximativ **26 h 25 min** până la 18 octombrie, 16:30. Un ciclu nou de 25 de ore încă încăpea, dar lăsa numai **1 h 25 min** rezervă; pentru păstrarea rezervei inițiale trebuia comprimat cu cel puțin 35 de minute.

La pornirea efectivă se recalculează timpul rămas: după 17 octombrie, 15:30, un ciclu nou de 25 de ore nu mai încape până la începutul predării nici fără rezervă. Se reduc întâi extensiile și volumul de date, păstrând verificarea umană, integrarea timpurie, odihna, repetițiile și rezerva. Această actualizare de context nu rescrie calendarul din niciun plan.

## Neconcordanțe păstrate pentru decizia echipei

[Planificare.md](../Planificare.md) este păstrat integral. Cerințele SafeIași de mai sus descriu direcția cerută pentru această etapă; tabelul face vizibile diferențele fără să pretindă că echipa a reconciliat deja toate deciziile tehnice.

| Aspect | Planificare.md existent | Planul SafeIași atașat / contextul curent |
|---|---|---|
| Produs și arie | „Harta pietonului – Iași”; accidente cu pietoni | „SafeIași”; siguranță rutieră, cu participanții explicitați; limita exactă a colectării trebuie fixată |
| Stack și directoare | Python pentru date, HTML + MapLibre GL + deck.gl, FastAPI `/extract`; directoare pe arii | Python + Streamlit + pydeck dacă se pornește de la zero; `src/` pe module; nicio variantă nu este implementată |
| Contracte | `schema_version: "2.0"`; `articles.json`, `accidents.json`, `hotspots.json`, `crossings.geojson`, `measures.json` | `schema_version: "1.0"`; `articles.jsonl`, `accidents.geojson`, `hotspots.geojson`, `context.geojson`; necesită o singură schemă agreată înaintea implementării |
| Unitatea clasamentului | Locație concretă; H3 pentru vizualizare; asociere la cel mai apropiat obiect în 50 m | Hotspot reprezentat ca poligon H3, recomandare legată de locație/segment; precizia și asocierea cer verificare, nu doar proximitate |
| Scor | Evenimente + gravitate + bonusuri de infrastructură cunoscută | Evenimente + gravitate + bonus pentru evenimente cu pietoni; ponderile diferă și trebuie fixate înainte de clasament |
| Volum și prezentare | 150+ articole, minimum 50 de evenimente la un checkpoint, Top 10, tur cinematic și animația „Aplică măsurile” | 20–40 de evenimente verificate, minimum zece pentru demo și trei dosare; nu se umple artificial un top și nu se sugerează o reducere măsurată a accidentelor prin animații |
| Roluri și calendar | Persoana 1: scraping și integrare; persoana 5: măsuri/export/pitch; persoana 6: UI; lucru batch noaptea; feature freeze duminică 14:30 | P1 dedicat coordonării, P4 măsuri/export, P5 UI, P6 produs/review/pitch; freeze H+12 și fereastră de odihnă; numerele rolurilor nu sunt interschimbabile |
| Geocodare | Nominatim ca serviciu propus implicit | Extract local și verificare manuală; Nominatim numai dacă este ales deliberat și utilizat conform politicii oficiale citate în plan |

Exemplele JSON și rezultatele numerice din `Planificare.md` sunt illustrative, fără fixture-uri sau surse de evenimente disponibile în repository; nu sunt date observate. Trimiterea sa la `PLAN.md` nu corespunde unui fișier existent; documentele reale sunt cele legate aici și în README. Statisticile de accidente din pitch, afirmația despre lipsa competitorilor în România și accesul viitor la date oficiale/Waze din acel document nu sunt validate prin această sarcină și nu trebuie prezentate drept dovezi sau acces confirmat. Planul inițial rămâne disponibil pentru reconciliere, fără ștergeri sau modificări tacite.
