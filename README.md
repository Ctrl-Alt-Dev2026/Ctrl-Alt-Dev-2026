# SafeIași

SafeIași este numele de lucru al unui proiect pentru Hackathon AI Iași 2026 (16–18 octombrie), realizat de o echipă de șase persoane. Produsul propus ajută administrația să identifice locațiile de verificat prioritar pentru siguranță rutieră, pe baza unor evenimente documentate, extrase cu AI și verificate de operator.

Clientul vizat este Primăria Iași; nu există un contract sau un parteneriat confirmat. Ramura backend conține documentație, fixture-uri sintetice în `false_data/`, auditul lor și un server local FastAPI cu `/health` și citire de snapshot sintetic validat. Extracția, review-ul și publicarea datelor reale urmează separat.

- [Contextul proiectului, principiile și diferențele dintre planuri](docs/PROJECT_CONTEXT.md)
- [Responsabilitățile și planul de lucru pentru backend](docs/BACKEND_WORK_PLAN.md) — Mihnea: backend/API, provizoriu; Emi: extracție AI.
- [Pornire locală, verificări și depanare](docs/LOCAL_DEVELOPMENT.md)
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

Rutele [manifest](http://127.0.0.1:8000/api/v1/manifest) și [evenimente](http://127.0.0.1:8000/api/v1/events) citesc același snapshot, încărcat la pornire. Implicit folosesc `false_data/`; deoarece setul actual este incomplet, răspund **HTTP 503 `invalid_snapshot`**, cu diagnostice. Nu servesc date parțiale. Un director sintetic coerent se poate selecta prin `SAFEIASI_SNAPSHOT_DIR`, urmat de repornire. Datele observate nu sunt încă acceptate.

Teste și audit, într-un al doilea terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m api.validate_fixtures false_data
```

Auditul întoarce codul `1` pentru neconcordanțele fixture-urilor actuale, documentate în plan; nu împiedică pornirea serverului. Nu validează date observate. Calendarul se recalculează de la ora reală de pornire, raportat la [predarea din 18 octombrie, 16:30–17:00](https://markaiintegrator.ro/hackathon-ai/), în fusul Europe/Bucharest.
