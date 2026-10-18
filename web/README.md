# SafeIași — interfața Angular

Angular 21, MapLibre 5 și deck.gl. Mediul implicit folosește API-ul real `/api/v1`; harta și dosarele citesc aceeași publicație imuabilă. Aprobarea și publicarea sunt acțiuni distincte ale operatorului.

Cu Node 24 verificat, din `web/`:

```sh
npm ci
npm run build:local
```

Interfața are o singură variantă, online: citește setul de date pe care serverul îl colectează la fiecare 30 de minute (comunicate ISU Iași, presă, PMUD) și îl păstrează în SQLite (`runtime/safeiasi.sqlite3`). Toți cei care deschid pagina văd aceleași date. Nu mai există build mock, fixture-uri în `public/data` sau comutator observat/sintetic.

| Comandă | Rezultat |
|---|---|
| `npm run backend` | FastAPI în Docker pe 127.0.0.1:8000, cu colectarea automată pornită și toate dependențele (inclusiv modelele pentru camere) deja în imagine. Cere doar Docker Desktop pornit; primul build durează câteva minute. `-- --no-vision` dă o imagine mică, fără analiza camerelor |
| `npm run backend:share` | La fel, și rescrie `isu/seed/` în repo după fiecare colectare |
| `npm run ai` | Pasul AI prin Claude Code, pe contul tău claude.ai (fără cheie API, nu în Docker): filtrează și extrage articolele de presă, propune pe fiecare stradă ce merită studiat (doar din catalogul de măsuri), reconstruiește datele și rescrie `isu/seed/`. Fă commit ca să ajungă la colegi |
| `npm run backend:local` | Fără Docker: Python din `.venv` (îl creează și instalează requirements la prima rulare) |
| `npm start` | Angular pe :4200, cu proxy `/api` către 127.0.0.1:8000 |
| `npm run build:local` | Build cu baza `/ui/`, servit de FastAPI |
| `npm run build` | Build cu baza implicită (folosit de imaginea nginx) |
| Imagine pentru GCP (Artifact Registry + Cloud Run) | O singură imagine publică: API + interfața la `/ui/` + YOLO + datele din `isu/seed/`. Comenzi și limite: [deploy/README.md](../deploy/README.md) |
| `docker compose up --build` (din rădăcină) | **Toată aplicația, fără Node/Python instalate**: api + interfața Angular (construită în imagine, servită de nginx) pe http://localhost:4280, datele într-un volum. Pentru colegii care doar folosesc aplicația. Alt port: `SAFEIASI_WEB_PORT=…` |

După `git clone` sau `git pull`, serverul pornește din datele reale salvate în `isu/seed/` (fără descărcări), apoi colectează doar ce e nou. În Docker, baza stă în volumul `data` (`docker compose down -v` o șterge și o reface din seed). Ca să-ți partajezi datele colegilor: `npm run backend:share` (sau `python -m isu --seed`) și fă commit la `isu/seed/`.

Camerele live folosesc backend-ul Python pentru detecție YOLO11/YOLO-World, tracking și semnale de verificat. Cu `npm run backend` sunt deja instalate în imagine (CPU, fără CUDA). Pentru `backend:local`, din rădăcină: `.venv\Scripts\python.exe -m pip install -r requirements-vision.txt`, apoi `.venv\Scripts\python.exe -m safecross.live_setup`. În cameră, marchează conturul trecerii pentru verificarea luminii în zona ei. [Configurare și limite](../docs/LIVE_VISION.md).

Contracte și reguli: [PLAN.md](PLAN.md), [CLAUDE.md](CLAUDE.md), [handoff API](../docs/FRONTEND_HANDOFF.md). Rezultate și limite: [verificarea integrării](../docs/FRONTEND_INTEGRATION.md). Repository-ul nu configurează un runner Angular de teste; integrarea a fost verificată prin build și browser, plus testele Python ale backend-ului.
