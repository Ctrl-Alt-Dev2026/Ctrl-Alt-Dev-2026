# SafeIași

SafeIași este numele de lucru al unui proiect pentru Hackathon AI Iași 2026 (16–18 octombrie), realizat de o echipă de șase persoane. Produsul propus ajută administrația să identifice locațiile de verificat prioritar pentru siguranță rutieră, pe baza unor evenimente documentate, extrase cu AI și verificate de operator.

Clientul vizat este Primăria Iași; nu există un contract sau un parteneriat confirmat. Repository-ul conține documentație, fixture-uri sintetice în `false_data/`, auditul lor și un server local FastAPI cu `/health`, citire de snapshot sintetic validat și extracția AI a lui Emi. Backend-ul poate importa, salva și corecta candidați, apoi înregistra aprobarea/respingerea sau asocierea la un eveniment canonic. Publicarea datelor reale și ecranele produsului urmează separat.

- [Contextul proiectului, principiile și diferențele dintre planuri](docs/PROJECT_CONTEXT.md)
- [Responsabilitățile și planul de lucru pentru backend](docs/BACKEND_WORK_PLAN.md) — Mihnea: backend/API, provizoriu; Emi: extracție AI.
- [Pornire locală, verificări și depanare](docs/LOCAL_DEVELOPMENT.md)
- [Modulul AI: contract, Ollama, teste și limite](ai/README.md)
- [Investigatorul de tipare: demo interactiv, dovezi și contestarea ipotezelor](ai/patterns/README.md)
- [Import, corectare și review: contract și exemplu complet](docs/REVIEW_WORKFLOW.md)
- [Contractul API pentru citirea snapshot-ului](docs/SNAPSHOT_READ_API.md)
- [Planul inițial pentru șase persoane și aproximativ 25 de ore](docs/HACKATHON_PLAN.md) — atașamentul păstrat integral; observația despre accesul GitHub din introducere este istorică.
- [Planificarea existentă: „Harta pietonului – Iași · Plan v2”](Planificare.md) — păstrată integral; conține propuneri care diferă de planul SafeIași.

Pornire locală din rădăcina repository-ului, în PowerShell, cu Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Deschide [verificarea serverului](http://127.0.0.1:8000/health) sau [documentația API](http://127.0.0.1:8000/docs). `/health` confirmă numai că serverul rulează; nu are nevoie de chei AI sau de date. Oprire: **Ctrl+C** în terminalul serverului. Pentru repornire este suficientă ultima comandă.

Aceeași pornire include `POST /api/v1/ai/extract` și `GET /api/v1/ai/replays/{article_id}`. Procesarea implicită `hybrid` necesită Ollama local cu `qwen2.5:1.5b`; modul `rules` și reluările sintetice etichetate funcționează fără model. Endpoint-ul de extracție nu salvează sau aprobă candidați. Pentru salvare folosește `/api/v1/imports`, apoi rutele locale de review; fiecare decizie cere operator și versiune, fără publicare automată pe hartă. Exemplele sunt în [instrucțiunile locale](docs/LOCAL_DEVELOPMENT.md#extracția-ai) și [fluxul de review](docs/REVIEW_WORKFLOW.md).

Deschide [investigatorul de tipare](http://127.0.0.1:8000/patterns) pentru grupare semantică între locuri, inspecția dovezilor și eliminarea temporară a cazurilor cu recalcularea ipotezelor. Demo-ul folosește vectori multilingvi calculați local și fixture-uri fictive; funcționează fără model sau conexiune externă la vizualizare. Pentru varianta fără server, deschide `ai/patterns/static/index.html`. Cele 17 evenimente au numai 4 texte pentru 3 cazuri; modul bazat exclusiv pe fragmente din articole se abține. Explorarea nu modifică datele de review sau snapshot-ul și nu demonstrează cauze ori riscuri reale.

Rutele [manifest](http://127.0.0.1:8000/api/v1/manifest) și [evenimente](http://127.0.0.1:8000/api/v1/events) citesc același snapshot, încărcat la pornire. Implicit folosesc `false_data/`; deoarece setul actual este incomplet, răspund **HTTP 503 `invalid_snapshot`**, cu diagnostice. Nu servesc date parțiale. Un director sintetic coerent se poate selecta prin `SAFEIASI_SNAPSHOT_DIR`, urmat de repornire. Datele observate nu sunt încă acceptate.

Teste și audit, într-un al doilea terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/patterns/tests -v
.\.venv\Scripts\python.exe -m api.validate_fixtures false_data
```

Auditul întoarce codul `1` pentru neconcordanțele fixture-urilor actuale, documentate în plan; nu împiedică pornirea serverului. Nu validează date observate. Calendarul se recalculează de la ora reală de pornire, raportat la [predarea din 18 octombrie, 16:30–17:00](https://markaiintegrator.ro/hackathon-ai/), în fusul Europe/Bucharest.
