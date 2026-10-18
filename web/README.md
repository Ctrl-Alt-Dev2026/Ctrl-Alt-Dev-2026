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
| `npm run backend` | FastAPI pe :8000 cu colectarea automată pornită (`SAFEIASI_LIVE=1`); creează `.venv` la prima rulare |
| `npm start` | Angular pe :4200, cu proxy `/api` către 127.0.0.1:8000 |
| `npm run build:local` | Build cu baza `/ui/`, servit de FastAPI |
| `npm run build` | Build cu baza implicită (folosit de imaginea nginx) |
| `docker compose up --build` (din rădăcină) | api + web (nginx) pe http://localhost:8080, datele într-un volum |

După `git clone` sau `git pull`, serverul pornește din datele reale salvate în `isu/seed/` (fără descărcări), apoi colectează doar ce e nou. Ca să-ți partajezi datele colegilor: `npm run backend:share` (sau `python -m isu --seed`) și fă commit la `isu/seed/`.

Camerele live folosesc backend-ul Python pentru detecție YOLO11/YOLO-World, tracking și semnale de verificat. Instalare separată din rădăcină: `.venv\Scripts\python.exe -m pip install -r requirements-vision.txt`, apoi `.venv\Scripts\python.exe -m safecross.live_setup`. În cameră, marchează conturul trecerii pentru verificarea luminii în zona ei. [Configurare și limite](../docs/LIVE_VISION.md).

Contracte și reguli: [PLAN.md](PLAN.md), [CLAUDE.md](CLAUDE.md), [handoff API](../docs/FRONTEND_HANDOFF.md). Rezultate și limite: [verificarea integrării](../docs/FRONTEND_INTEGRATION.md). Repository-ul nu configurează un runner Angular de teste; integrarea a fost verificată prin build și browser, plus testele Python ale backend-ului.
