# SafeIași — interfața Angular

Angular 21, MapLibre 5 și deck.gl. Mediul implicit folosește API-ul real `/api/v1`; harta și dosarele citesc aceeași publicație imuabilă. Aprobarea și publicarea sunt acțiuni distincte ale operatorului.

Cu Node 24 verificat, din `web/`:

```sh
npm ci
npm run build:local
```

Pornește FastAPI din rădăcina repository-ului conform [ghidului local](../docs/LOCAL_DEVELOPMENT.md). Interfața este servită la [8000/ui/](http://127.0.0.1:8000/ui/), pe aceeași origine cu API-ul. Modul implicit este observat; fără publicație, harta explică starea goală și permite importul. Repetiția sintetică trebuie pregătită separat, conform ghidului.

Pentru dezvoltare, `npm start` pornește Angular pe portul 4200, cu proxy `/api` către 127.0.0.1:8000. Proxy-ul păstrează Host/Origin; nu adăuga CORS larg pentru a ocoli verificările locale.

| Comandă | Rezultat |
|---|---|
| `npm run build:local` | Build HTTP cu baza `/ui/`, servit de FastAPI |
| `npm run build:mock` | Prototip static sintetic, fără scrieri |
| `npm run build:pages` | Același prototip static, cu baza GitHub Pages |
| `npm run build` | Build HTTP cu baza implicită, pentru altă găzduire |

Build-urile statice nu sunt fallback pentru API și nu validează fixture-urile vechi. După un build static, reconstruiește `build:local` pentru `/ui/`. Helper-ul limitează paralelismul local; dependențele nu sunt schimbate.

Contracte și reguli: [PLAN.md](PLAN.md), [CLAUDE.md](CLAUDE.md), [handoff API](../docs/FRONTEND_HANDOFF.md). Rezultate și limite: [verificarea integrării](../docs/FRONTEND_INTEGRATION.md). Repository-ul nu configurează un runner Angular de teste; integrarea a fost verificată prin build și browser, plus testele Python ale backend-ului.
