# Citirea unui snapshot sintetic validat — API v0.3

Acesta este pasul backend 2b: citire fără scrieri, pe schema `2.0`, pentru dezvoltare. Aceste rute nu implementează aprobarea sau publicarea datelor reale. Extractorul AI este disponibil separat în același server, conform [instrucțiunilor locale](LOCAL_DEVELOPMENT.md#extracția-ai), și nu modifică snapshot-ul. Codul nu repară și nu completează datele colegilor.

## Rutele disponibile

| Rută | Răspuns |
|---|---|
| `GET /health` | HTTP 200 dacă serverul răspunde, indiferent de starea datelor |
| `GET /api/v1/manifest` | HTTP 200 cu manifestul și metadatele snapshot-ului, numai dacă întregul snapshot trece verificările |
| `GET /api/v1/events` | HTTP 200 cu evenimentele sintetice eligibile din același snapshot, fără calcul de scor sau clasament |
| `GET /docs` | Documentația operațiilor și a răspunsurilor |

Cele două răspunsuri de date includ:

| Câmp | Semnificație |
|---|---|
| `snapshot_id` | Identificator SHA-256 al fișierelor încărcate; același pentru manifest și evenimente |
| `data_mode` | Întotdeauna `synthetic` în această etapă |
| `warning` | Etichetă explicită „DATE SINTETICE”; nu sunt dovezi despre accidente reale |
| `eligible_event_count` | Numărul înregistrărilor care trec filtrul de eligibilitate |
| `manifest` sau `events` | Manifestul original, respectiv lista filtrată de evenimente |

Totalurile `nr_*` din `manifest` descriu setul sursă întreg, inclusiv înregistrările încă neverificate. `eligible_event_count` și lungimea listei `events` descriu numai subsetul eligibil. Aceste numere pot fi diferite și nu trebuie afișate ca aceeași măsură. Un snapshot coerent fără evenimente eligibile produce listă goală cu HTTP 200; un snapshot invalid produce 503, nu o listă goală care ascunde eroarea.

## Eligibilitatea înregistrărilor

Lista include numai evenimente cu `verificat: true`, `in_iasi: true`, dată a accidentului cunoscută în intervalul inclusiv din manifest, precizie `trecere`, `intersectie` sau `segment` și coordonate nenule valide ca limite globale. Nu folosește data publicării în locul datei accidentului. Ora și gravitatea necunoscute sunt păstrate; nu se inventează valori.

API-ul folosește marcajele de verificare/geografie din datele primite. Nu confirmă independent veridicitatea surselor, pinul sau limita municipiului; aceste verificări aparțin operatorului și modulului geo. Chiar și `verificat: true` în modul sintetic rămâne un fixture de dezvoltare.

Snapshot-ul trebuie să conțină evenimente canonice, cu ID-uri unice. Mai multe articole pot fi asociate aceluiași eveniment. Un rând cu `duplicate_of` nenul face snapshot-ul invalid: proprietarul trebuie să reconcilieze evenimentul și sursele înaintea publicării snapshot-ului, astfel încât API-ul să nu elimine în tăcere dovezile. Câmpurile de eveniment expuse sunt cele din contractul existent; câmpurile auxiliare necunoscute nu sunt returnate.

## Directorul și versiunea încărcată

Implicit se folosește `false_data/` din repository, independent de folderul curent al terminalului. Pentru un alt snapshot sintetic existent și coerent:

```powershell
$env:SAFEIASI_SNAPSHOT_DIR = 'C:\cale\catre\snapshot-sintetic-validat'
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Calea de mai sus este un exemplu și se înlocuiește cu directorul real. Nu este necesar un fișier `.env`; aplicația citește variabila din mediul procesului. Directorul trebuie să conțină `manifest.json`, `articles.json`, `accidents.json`, `crossings.geojson`, `hotspots.json` și `measure.json`.

Snapshot-ul este citit și validat o singură dată la pornire. Amprentele fișierelor sunt comparate înainte și după citire, iar schimbarea detectată blochează încărcarea. După pornire, toate cererile folosesc versiunea din memorie, chiar dacă fișierele sunt modificate. Pentru o versiune nouă: pregătește un director complet, păstrează-l nemodificat și repornește serverul cu acea cale. Nu există încă reload de date sau endpoint de upload.

## Erorile sunt explicite

HTTP 503 are forma `{"detail":{"code":"...","message":"...","issues":[...]}}`:

| Cod | Cauză |
|---|---|
| `snapshot_unavailable` | Director/fișiere lipsă sau imposibil de citit |
| `invalid_snapshot` | JSON invalid, chei JSON duplicate, NaN/Infinity, referințe/totaluri incoerente, perioadă/metadate invalide ori evenimente necanonice |
| `snapshot_changed` | Fișierele s-au schimbat în timpul încărcării |
| `unsupported_data_mode` | Manifestul declară `observed`; publicarea datelor reale nu este implementată în acest cititor |

Mesajele nu expun calea absolută a directorului. La eroare nu se încarcă o parte a datelor și nu se trece automat la alt set. `/health` rămâne disponibil. Pentru fixture-urile actuale, `invalid_snapshot` raportează cele 14 referințe de articole lipsă și manifestul cu 18 articole declarate față de patru existente.

Auditul CLI existent verifică consistența de bază a fixture-urilor. Cititorul API adaugă cerințe de JSON strict, perioadă de analiză, timestamp cu fus/offset, date de eveniment și evenimente canonice. Un audit de fixture-uri trecut nu certifică automat un snapshot pentru acest API sau date observate.

## Verificare

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Invoke-RestMethod http://127.0.0.1:8000/health
```

În [Swagger](http://127.0.0.1:8000/docs), `Try it out` pentru manifest/evenimente arată și eroarea setului curent. Testele folosesc snapshot-uri sintetice coerente în directoare temporare pentru a verifica și răspunsurile 200, filtrarea, păstrarea surselor/necunoscutelor, versiunea stabilă și lipsa scrierilor. Niciun set nou de accidente nu este adăugat în repository.
