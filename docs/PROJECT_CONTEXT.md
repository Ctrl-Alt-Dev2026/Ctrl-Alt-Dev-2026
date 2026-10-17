# SafeIași — contextul proiectului

## Produs și client vizat

SafeIași este un nume de lucru pentru un instrument de sprijin pentru administrație: **„Ce locații ar trebui verificate prioritar pentru siguranță rutieră și pe ce dovezi ne bazăm?”** Obiectivul este un demo funcțional, credibil și convingător, cu potențial de continuare într-un pilot plătit.

Clientul principal vizat este **Primăria Iași**, cu utilizatori din mobilitate/siguranță rutieră. Nu există un contract, un parteneriat sau o validare de client confirmată. Pilotul de 60–90 de zile pentru 3–5 locații din plan este o propunere de validat.

## Ce există și ce este propus

**Starea curentă:** stack-ul funcțional este **FastAPI + Angular 21**, cu harta, dosarul și importul/review-ul conectate la API v0.7. Operatorul importă un articol, verifică și corectează candidații, decide evenimentul canonic, apoi publică separat o selecție verificată. Harta, dosarul și exportul folosesc aceeași versiune înghețată. Repetiția locală separată are șase evenimente sintetice din șapte articole, la trei locații fictive; serverul normal nu are încă un set de accidente observate publicat. Catalogul de măsuri rămâne neintegrat. [Pornire](LOCAL_DEVELOPMENT.md), [contract și comportament UI](FRONTEND_HANDOFF.md), [verificări și limite](FRONTEND_INTEGRATION.md).

La inspecția inițială din 17 octombrie 2026, ramura implicită `main`, la commitul `fc61ae58995f21a654b603af77134dcc8605ac89`, conținea doar [Planificare.md](../Planificare.md). Nu existau atunci cod de aplicație, dependențe, teste, seturi de date, README sau `AGENTS.md`; istoricul de mai jos descrie etapele ulterioare.

[HACKATHON_PLAN.md](HACKATHON_PLAN.md) reproduce integral atașamentul `Plan_SafeIasi_6_persoane_25h (1).md`. Observația sa despre un răspuns GitHub 404 aparține sesiunii anterioare: la adăugarea documentației, clonarea prin Git a reușit și autentificarea locală avea drept de push, deși conectorul GitHub răspundea cu 404. La acel moment, contractele, căile de fișiere, fixture-urile, backlog-ul și funcționalitățile descrise în ambele planuri erau propuneri, nu artefacte implementate sau date deja colectate.

Ulterior, la commitul `77b0a09`, echipa a adăugat `false_data/`: fixture-uri sintetice pe schema `2.0`, fără date reale verificate sau aplicație. Auditul și pașii pentru backend sunt în [BACKEND_WORK_PLAN.md](BACKEND_WORK_PLAN.md). Fixture-urile sunt păstrate în forma colegilor; neconcordanțele lor trebuie rezolvate înaintea integrării.

Sunt implementate pornirea FastAPI/Uvicorn cu `/health`/OpenAPI, [citirea unui snapshot sintetic validat](SNAPSHOT_READ_API.md), [extractorul AI al lui Emi](../ai/README.md) și [importul/corectarea/review-ul cu persistență locală](REVIEW_WORKFLOW.md), integrate în `api.main:app`. Extracția returnează candidați neverificați și funcționează independent de snapshot. `hybrid` cere Ollama/model disponibil; `rules` este extracție deterministă fără model și este etichetată astfel. Pe laptopul verificat lipsesc Ollama și `qwen2.5:1.5b`; integrarea nu le descarcă. Deciziile operatorului creează evenimente canonice locale și pot asocia mai multe articole aceluiași eveniment, fără publicare automată. [Instrucțiunile locale](LOCAL_DEVELOPMENT.md) explică instalarea și verificarea. Setul legacy `false_data/` este refuzat de cititorul său cu diagnostice; fluxul nou de publicații nu servește date parțiale și nu îl folosește ca fallback.

Python + Streamlit + pydeck era alternativa din planul atașat pentru pornirea de la zero. Stack-ul existent FastAPI + Angular are prioritate; integrarea păstrează frontend-ul echipei și calculul scorului în backend, fără rescriere pe alternativa din plan.

La baza `b6cecb9`, colegul a adăugat [context OSM pentru Iași](../context/CITY.md), exporturi observate de infrastructură și [pipeline offline de scor](../risk/IMPLEMENTATION.md). Au fost conectate ulterior prin publicarea explicită, cu asociere verificată și contexte de același mod; observațiile SafeCross rămân separate. Cele 1.210 treceri OSM ale contextului normal sunt infrastructură, nu accidente verificate. Nu sunt combinate automat cu fixture-urile sintetice.

La `0e8d1ae`, Emi a integrat [investigatorul de tipare — opțiunea 6](../ai/patterns/README.md). `/patterns` și rutele `/api/v1/ai/patterns/*` folosesc vectori MiniLM multilingvi pregătiți local pe fixture-urile existente; excluderea/restabilirea cazurilor recalculează grupurile fără să schimbe datele de review. Sunt 17 evenimente fictive, 4 articole pentru 3 evenimente și numai 2 evenimente cu fragmente explicative potrivite exact. Modul bazat exclusiv pe surse se abține. Nu este analiză validată de cauze și nu descoperă tipare din filmarea SafeCross. Datele sintetice ale opțiunii 6, observațiile video din Toronto și infrastructura OSM observată din Iași rămân explicit distincte; o legătură între ele cere date și asociere verificate.

## Scope-ul MVP propus

Actualizarea backend v0.6 a adăugat [publicare explicită și dosare](PUBLICATION_WORKFLOW.md): evenimente canonice aprobate → asociere la contextul de același mod → verificarea geometriei → formula de scor existentă → versiune locală înghețată → listă/GeoJSON/dosar/export JSON sau HTML imprimabil. Repetiția izolată conține șapte articole fictive pentru șase evenimente la trei locații fictive; nu modifică sursele comune. Modul observat este suportat, fără să pretindă că au fost colectate sau validate accidente reale. Ecranele principale sunt acum conectate; catalogul de măsuri cu surse și un set real verificat rămân necesare.

La `22cbb51`, colegul a adăugat [modulul de coordonate](../coordonate/README.md), bazat pe index OSM local. Backend v0.7 îl conectează prin [preview și aplicare în review](GEOCODING_WORKFLOW.md), înainte de aprobare, cu confirmarea operatorului și raport/proveniență în istoric. Punctele reprezentative pentru `strada` rămân în raport, fără pin precis pe candidat. Geocodarea sintetică este refuzată explicit, evenimentele aprobate nu sunt rescrise, iar nodurile cunoscute neverificate nu sunt folosite. Schimbarea textului locației invalidează vechile coordonate și dovezi, dacă nu se furnizează explicit un set nou coerent.

Fluxul principal: **surse despre accidente → extracție AI cu proveniență → verificare umană → localizare → hartă și prioritizare → măsuri candidate → fișă exportabilă**.

La `27510e9`, echipa a adăugat [prototipul Angular](../web/README.md) pentru hartă/dosar/import și o extensie de camere publice. Inițial folosea fixture-uri sintetice, reluări și contracte HTTP provizorii. Integrarea curentă folosește implicit API-ul real din aceeași origine, la `/ui/`; build-urile `mock`/Pages rămân variante statice explicite. [Handoff-ul](FRONTEND_HANDOFF.md) descrie contractele reconciliate. Nu sunt ocolite operatorul, versiunea sau verificarea localizării. UI-ul păstrează sursele originale, corecturile și necunoscutele; o locație cu un singur eveniment are dosar fără scor/rang, iar un catalog gol nu produce recomandări sau costuri inventate.

1. **Harta locațiilor prioritare:** filtre, perioada analizată și limitele eșantionului.
2. **Dosarul unei locații:** evenimente unice și surse, explicația priorității, precizia localizării, context și recomandări candidate.
3. **Import și verificare:** câmpuri extrase cu dovezi, corectare și aprobare înainte de publicare.

Ținta de lucru este de **20–40 de accidente distincte, verificate**, cu **trei dosare de locație** pregătite și cinci tipuri de măsuri documentate. Planul atașat propune un prag minim de zece evenimente reale pentru demo; dacă datele nu susțin agregări utile, se prezintă dosare individuale și limita eșantionului. Aceste cantități sunt obiective, nu date disponibile. Exportul sprijină verificarea administrației; nu constituie un audit rutier certificat.

**SafeCross** (observații din filmări de la treceri) și **TomTom** sunt extensii opționale. La cererea lui Mihnea din 17 octombrie, [SafeCross](SAFECROSS.md) are acum un prototip local separat: detecție YOLOX Nano, tracking, proximitate explicabilă în imagine, dovezi, review versionat și export. Demo-ul public folosește o filmare atribuită din Toronto, nu din Iași; nu demonstrează detectarea validată a conflictelor rutiere. Fluxul principal rămâne independent de extensii. TomTom, transportul public și parcările nu sunt implementate prin această etapă.

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
| Stack și directoare | Python pentru date, HTML + MapLibre GL + deck.gl, FastAPI `/extract`; directoare pe arii | Python + Streamlit + pydeck era alternativa de la zero; stack-ul funcțional este acum FastAPI (`api/`, `ai/`) + Angular 21 (`web/`), cu MapLibre/deck.gl și integrare HTTP |
| Contracte | `schema_version: "2.0"`; `articles.json`, `accidents.json`, `hotspots.json`, `crossings.geojson`, `measures.json` | Planul atașat propunea schema `1.0` și alte fișiere. Implementarea folosește articolul `2.0`, review versionat și snapshot `publication-1`; contractul curent este documentat în handoff, fără rescrierea planurilor |
| Unitatea clasamentului | Locație concretă; H3 pentru vizualizare; asociere la cel mai apropiat obiect în 50 m | Hotspot reprezentat ca poligon H3, recomandare legată de locație/segment; precizia și asocierea cer verificare, nu doar proximitate |
| Scor | Evenimente + gravitate + bonusuri de infrastructură cunoscută | Evenimente + gravitate + bonus pentru evenimente cu pietoni; ponderile diferă și trebuie fixate înainte de clasament |
| Volum și prezentare | 150+ articole, minimum 50 de evenimente la un checkpoint, Top 10, tur cinematic și animația „Aplică măsurile” | 20–40 de evenimente verificate, minimum zece pentru demo și trei dosare; nu se umple artificial un top și nu se sugerează o reducere măsurată a accidentelor prin animații |
| Roluri și calendar | Persoana 1: scraping și integrare; persoana 5: măsuri/export/pitch; persoana 6: UI; lucru batch noaptea; feature freeze duminică 14:30 | P1 dedicat coordonării, P4 măsuri/export, P5 UI, P6 produs/review/pitch; freeze H+12 și fereastră de odihnă; numerele rolurilor nu sunt interschimbabile |
| Geocodare | Nominatim ca serviciu propus implicit | Extract local și verificare manuală; Nominatim numai dacă este ales deliberat și utilizat conform politicii oficiale citate în plan |

Exemplele JSON și rezultatele numerice din `Planificare.md` sunt illustrative; la inspecția inițială nu existau fixture-uri sau surse în repository, iar fixture-urile adăugate ulterior sunt sintetice. Nu sunt date observate. Trimiterea sa la `PLAN.md` nu corespundea unui fișier rădăcină existent; documentele reale sunt cele legate aici și în README. Statisticile de accidente din pitch, afirmația despre lipsa competitorilor în România și accesul viitor la date oficiale/Waze din acel document nu sunt validate prin această sarcină și nu trebuie prezentate drept dovezi sau acces confirmat. Planul inițial rămâne disponibil pentru reconciliere, fără ștergeri sau modificări tacite.
