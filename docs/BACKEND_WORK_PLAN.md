# SafeIași — plan de lucru pentru backend

Actualizat la 17 octombrie 2026. Responsabil propus: **Mihnea**, conform intenției exprimate de el; alocarea rămâne provizorie. **Emi se ocupă de extracția AI**, conform aceleiași discuții. Ceilalți colegi nu sunt nominalizați prin acest document.

## Aria noastră

Backend-ul conectează modulele și frontend-ul: validează rezultatele extracției, păstrează candidații separat de evenimentele aprobate, expune operațiile de corectare/aprobare și livrează datele pentru hartă și dosare. Extracția AI aparține lui Emi; geocodarea, scorul, recomandările, frontend-ul și pitch-ul rămân responsabilități distincte. Mihnea nu este desemnat automat coordonator P1.

Interfața de discutat cu Emi este `extract_article(article) -> candidates`: câmpuri posibil necunoscute, referințe la surse și pasaje-dovadă, identificarea rulării/modelului/promptului, plus erori explicite. Backend-ul validează răspunsul și îl pune în așteptarea operatorului; extracția nu aprobă automat un accident. Aceasta este o propunere de integrare, nu un contract deja acceptat de Emi.

## Baza de lucru verificată

- Bază Git: `origin/main`, commit `77b0a09`; nu exista aplicație sau fișier de dependențe.
- Echipa a adăugat `false_data/`, cu manifest `schema_version: "2.0"`, `data_mode: "synthetic"`.
- Fișierele existente sunt `articles.json`, `accidents.json`, `crossings.geojson`, `hotspots.json`, **`measure.json`**. Ultimul are numele la singular; nu îl redenumim în locul colegului.
- Continuăm întâi compatibilitatea cu aceste fixture-uri. Schema `1.0` GeoJSON din [planul atașat](HACKATHON_PLAN.md) rămâne o propunere alternativă; nu migrăm în tăcere contractele comune.
- Python + FastAPI pentru API este propunerea deja prezentă în [Planificare.md](../Planificare.md). Nu instalăm un framework și nu declarăm stack-ul implementat prin acest prim pas.

Auditul inițial a găsit **4 articole, 17 evenimente, 7 obiecte de infrastructură, 5 locații și 6 măsuri**. Manifestul declară **18 articole**, iar evenimentele referă **14 ID-uri de articole lipsă** (`syn-005`–`syn-018`). Nu completăm aceste articole prin invenție. Cele patru evenimente cu `verificat: true` sunt tot sintetice, nu accidente reale confirmate.

Fixture-urile includ costuri și reduceri sintetice, iar unele locații agregă evenimente încă neverificate. Ele nu devin automat un snapshot publicabil. Auditul actual verifică structura și consistența de bază, fără validare factuală, geocodare, calcul de scor sau aprobarea recomandărilor.

## Pașii pe care îi urmăm

Estimările sunt ore de lucru activ, nu un nou calendar de 25 de ore. Dependențele de colegi se tratează separat. Ordinea etapelor rămâne aceeași chiar dacă reducem scope-ul.

| Pas | Livrabil și criteriu de terminare | Estimare | Stare |
|---|---|---|---|
| 0. Delimitarea responsabilităților | Mihnea: backend/API, provizoriu; Emi: extracție; modulele colegilor nu sunt duplicate | 15 min | Documentat |
| 1. Auditul contractului existent | Comandă repetabilă, erori explicite pentru referințe/totaluri/mod de date; fixture-urile originale rămân nemodificate | 30–45 min | Implementat; auditul semnalează problemele de mai sus |
| 2. Scheletul API | Aplicație Python/FastAPI, `/health`, instrucțiuni de pornire și citire dintr-un snapshot validat; fără chei sau servicii necesare pentru pornire | 45–60 min | De făcut |
| 3. Contractul cu Emi și importul | Format agreat cu P1/Emi, adaptor către extracție, tratare timeout/JSON invalid; niciun candidat publicat automat; răspunsurile salvate sunt etichetate reluare | 60–90 min | De făcut; depinde de contractul și modulul lui Emi |
| 4. Corectare și aprobare | Operatorul vede dovezile, corectează și aprobă/respinge; actualizări atomice, istoric de verificare și versiune pentru evitarea suprascrierilor; duplicatele păstrează un ID canonic | 90 min | De făcut |
| 5. Integrarea cu frontend-ul | Listă și dosar de locație, citite din exportul modulului de prioritizare; GeoJSON în ordinea lon/lat; filtrele și totalurile coincid | 45–60 min | De făcut; depinde de frontend și P3/P4 |
| 6. Repetiția și rezerva | Fluxul import → verificare → date publicabile funcționează pe laptopul demo; testele de consistență trec; reluare locală explicită dacă AI nu răspunde | 45–60 min | De făcut |

**Următorul pas este 2**, după ce echipa corectează sau înlocuiește fixture-urile incomplete pentru integrare. Scheletul și `/health` pot fi construite între timp fără date, iar testele pot folosi seturi sintetice minimale izolate. Auditul trebuie să rămână strict; nu transformăm erorile în succes pentru a încărca un snapshot incomplet.

## API propus, încă neimplementat

Prefix de lucru pentru operațiile aplicației: `/api/v1`. `POST /extract` din planificarea existentă rămâne un punct de integrare de reconciliat, nu un al doilea extractor.

| Operație | Comportament așteptat |
|---|---|
| `GET /health` | Confirmă că serverul rulează; nu pretinde că AI sau setul de date sunt disponibile |
| `GET /api/v1/manifest` | Modul datelor, versiune, perioadă și totaluri validate |
| `POST /api/v1/imports` | Primește textul și identificarea sursei; apelează modulul lui Emi și produce candidați pentru review |
| `PATCH /api/v1/candidates/{id}` | Corectează câmpurile, cu proveniență și verificarea versiunii |
| `POST /api/v1/candidates/{id}/review` | Aprobă/respinge sau asociază unui eveniment canonic, cu operator și moment |
| `GET /api/v1/events` | Evenimente publicabile din modul de date selectat, fără amestec sintetic/observat |
| `GET /api/v1/locations/{id}` | Dosar: evenimente unice, surse, context, scor și recomandări furnizate de modulele colegilor |

Pentru MVP: fișiere JSON locale, fără bază de date, cloud nou sau integrare video. Scrierile se proiectează pentru un singur proces local, cu blocare și înlocuire atomică; procesele multiple necesită alt mecanism de persistență. Nu expunem operațiile de scriere public fără un control de acces proiectat separat. Nu implementăm încă o formulă de scor; alegerea între cele două planuri aparține echipei înainte de clasament.

## Verificarea primului pas

Din rădăcina repository-ului, cu Python 3.12 disponibil în mediul inspectat:

```powershell
python -m api.validate_fixtures false_data
python -m unittest discover -s tests -v
```

Prima comandă doar citește și emite un raport JSON: cod `0` pentru fixture-uri coerente, `1` pentru neconcordanțe. Acceptă numai fixture-uri **sintetice**, pe schema `2.0`; nu este validator pentru publicarea datelor observate. Testele verifică situații cu date lipsă, dubluri, referințe rupte și coordonate invalide, folosind fișiere temporare sintetice.

Nu există în acest pas API, extracție reală, stocare de review sau conexiune cu frontend-ul. Finalizarea auditului nu înseamnă finalizarea backend-ului.

## Timp și reguli de lucru

Conform [programului consultat pe 17 octombrie](https://markaiintegrator.ro/hackathon-ai/), predarea începe pe 18 octombrie la 16:30, Europe/Bucharest. Țintim pachetul pregătit la **14:30**, pentru două ore rezervă. Un nou ciclu complet de 25 de ore pornit după 17 octombrie, 13:30, consumă din acea rezervă; planul inițial trebuie comprimat la ora efectivă de start. Păstrăm odihna și repetițiile, reducem extensiile și volumul înaintea verificărilor.

Lucrăm pe ramuri `codex/`, cu schimbări mici, teste pentru riscurile reale și integrare devreme. Fiecare pas se închide cu livrabil, verificări și limitări consemnate. P1 rămâne singurul coordonator al schemelor/dependențelor comune; propunerile de mai sus se reconciliază înainte de implementarea etapelor care le folosesc. Nu facem merge automat și nu publicăm issues sau mesaje către colegi prin această sarcină.
