# UI plan — SafeIași (Person 6)

Angular front-end for the three screens + export described in `Planificare.md` §1 and §8 (Persoana 6).
**Update 2026-10-18: the UI is online only.** It reads the dataset the server collects every 30 minutes (`/api/v1/live/*`, `isu/` + `api/live_router.py`); there is no mock build, no static data and no observed/synthetic switch. The publication/review endpoints below still exist in the backend but the UI no longer calls them. The planning notes below retain the earlier design decisions; implementation updates are marked.

Sources of truth, in order: `Planificare.md` §4 (data contract) → §5 (score, *read-only for UI*) → §7 (measures) → §11 (pre-demo checks).
`Punct Negru Iași.html` is an early prototype, not a reference for look or content. Its claims ("−55% accidente",
"efect estimat", tag-based score, CSV upload, business section) are out of scope or forbidden by the plan.

**Scope decisions (with the user, 17 Oct):** all road accidents reported in the press, participants as a filter
(pedestrians are one); a real 3D map. Live cameras (decided 17 Oct, evening): public Iași webcams on the map through
their HLS stream, analysed by the Python backend (YOLO11s traffic, YOLO-World tram proposals, tracking and marked-crossing brightness),
as a proof of concept for city-hall CCTV. Fallback: the provider's embed player, no analysis. Product name is provisional (`APP_NAME` in `top-bar.ts`).

---

## 1. Stack

| Concern | Choice | Why |
|---|---|---|
| Framework | Angular 21, standalone components, signals, zoneless, `@if/@for` | Angular 22 needs Node ≥ 22.22; this machine has 22.15 |
| Map | `maplibre-gl` **5** + deck.gl 9.4 via `MapboxOverlay` (overlaid, not interleaved) | 3D buildings + columns; MapLibre 6 and interleaved mode both break deck 9.4 |
| Layers | `HexagonLayer` (`@deck.gl/aggregation-layers`), `ScatterplotLayer` (`@deck.gl/layers`) | H3 is null in fixtures → aggregate accident points client-side (visual only, allowed) |
| Basemap | OpenFreeMap `dark` (no key), recoloured, OSM buildings extruded, AWS terrarium DEM hillshade; fallback = plain dark background | 3D city look; must survive no-internet (§H4) |
| Charts | Hand-written SVG (24h bar chart) | One chart, no library needed |
| Styling | SCSS + tokens in `styles.scss` (night palette, Archivo, rem/clamp scale) | Projector legibility, fluid down to phone width |
| PDF / fișă | Print route `/fisa` + `@media print` until P5's generator exists | Zero dependency, works offline |
| Hosting | `ng build` → GitHub Pages, `withHashLocation()` | Static, no 404 rewrite needed |

No NgRx, no Material, no Tailwind — not worth the setup time in a 24h hackathon.

## 2. Folder layout

```
web/
  scripts/backend.py           starts the API with the 30-minute collector (SAFEIASI_LIVE=1)
  public/data/cameras.json     static public-webcam list (the only file left in public/data)
  src/environments/            environment.ts { api: { baseUrl } }
  src/app/
    core/models/               TS interfaces 1:1 with Planificare.md §4 (Romanian field names kept)
    core/api/                  endpoints.ts · data-api.ts (abstract) · mock-data-api.ts · http-data-api.ts
    core/state/                data.store.ts (signals: manifest, accidents, hotspots, measures, selectedId, filters)
    core/format/               labels.ts (gravitate, precizie, cauza → RO text), pipes (null → "necunoscut")
    shared/                    top-bar, synthetic-banner, kpi, chip, score-badge, null-value, hour-chart
    features/map/              map-page, map-view (MapLibre+deck), hotspot-list, filters, tour, apply-measures
    features/location/         location-dossier (drawer on map page + route /locatie/:id)
    features/import/           import-page: article text, extracted fields, highlighted evidence, approve/correct
    features/report/           fisa-page: printable verification sheet
```

## 3. API endpoints used by the UI

Paths are centralized in `core/api/endpoints.ts`; `DataApi` is the only class that calls `HttpClient` for data. Models keep the backend field names.

| Method | Path relative to `/api/v1` | Returns / use |
|---|---|---|
| GET | `/live/status` | `LiveStatus`: when the stored dataset was built, next collection, last run outcome. Polled every 2 min (20 s while the first collection runs) |
| GET | `/live/dataset` | `LiveDataset`: manifest, accidents, hotspots, crossings, measures, streets. Downloaded only when `construit_la` changes. 503 `dataset_not_ready` = first collection still running |
| POST | `/live/refresh` | Local only (`require_local`): start a collection now. Not called by the UI |
| GET | `data/cameras.json` (static UI asset) | Public camera metadata, separate from accident sources |
| GET | `/vision/status` | Local live detector readiness (no model load) |
| POST | `/vision/sessions` | Camera tracking session and normalized crossing polygons |
| POST | `/vision/sessions/:id/frames?sequence=…&media_time=…` | Raw JPEG → detections, lighting, unverified signals and frame timing |
| DELETE | `/vision/sessions/:id` | Release camera tracking state |

A refresh keeps filters and selections. If the server stops answering, the data already on screen stays and the top bar says so; an empty page shows an error with "Încearcă din nou".

Run `python scripts/backend.py` (API + collector on :8000) and `npm start` (proxy `/api` to `127.0.0.1:8000`, `changeOrigin: false`), or `npm run build:local` and open the API's `/ui/` route, or `docker compose up --build` at the repo root (nginx on :8080 proxies `/api`).

**Historical:** the v0.7 publication endpoints (`/publications/*`, `/locations/*`, `/candidates/*`, `/imports`) and the mock-first `/api/manifest`… table described earlier designs. The UI no longer uses them.

## 4. Contract mismatches to raise with Person 1

1. (Resolved 2026-10-18) The UI no longer reads files; it reads the server's collected dataset (`/api/v1/live/dataset`).
2. `false_data/measure.json` vs contract `measures.json`. → script renames on copy.
3. Two schemas in docs (`Planificare.md` v2 vs `docs/HACKATHON_PLAN.md` v1). Fixtures follow **v2**; UI follows v2.
4. The initial `/extract` and review proposals differed from the backend. → The current versioned API is documented in §3; imports, candidates and canonical working events remain separate from published releases.
5. `hotspots[].h3` is `null` → HexagonLayer aggregates from `accidents` lat/lon instead.

## 5. Screens (what each must show)

Layout: the 3D map fills the screen; everything else floats over it (title card top-left, nav top-right,
ranked list / dossier panel right, legend bottom-left, action dock bottom). Below 56rem it stacks.

**Top bar (G7)** — title "Accidente rutiere raportate în presă, {perioada}", counts from manifest
(articole, evenimente unice, localizate precis, verificate), red **Date sintetice** pill when
`data_mode === 'synthetic'`; nav: Hartă, Import cu AI, Fișa pentru primărie, Despre date (limits popover).

**Screen 1 – Harta priorităților (G1, G2)** — dark 3D city pitched ~58°, extruded buildings, hillshade;
hexagon columns; accident dots (hollow for `precizie_loc` strada/vag = "localizate aproximativ"); pulsing
rings + rank labels on ranked hotspots; participant filter chips; right-side ranked list (score badge,
name, first measure). Show as many as exist — no padded Top 10.

**Screen 2 – Fișa locației (G3)** — name, score + `componente_scor` breakdown bar, `explicatie`,
events (date, ora or "oră necunoscută", gravitate, links to every source), 24h chart from `pe_ore`,
infrastructure known/unknown (`null` rendered as "necunoscut", never "nu"), `date_lipsa` list,
measures (motiv, cost min–max with source or "cost nedocumentat", reducere_tipica *as literature info*,
de_verificat checklist).

**Screen 3 – Import și verificare (G5)** — paste text/URL → "Extrage" → left: article text with
evidence highlighted per field; right: editable fields; buttons Aprobă / Corectează / Respinge;
"REZULTAT SALVAT (reluare)" label for saved processing results; rules are labelled as rules rather than AI. Approval creates/updates the canonical working event; only a subsequent explicit publication makes it part of the published map.

**Tour (G4)** — `map.flyTo` through ranked hotspots, dossier slides in, Esc stops.

**Aplică măsurile (G6)** — hotspot columns animate down; counter
`Locații vizate: N · Accidente documentate acolo: M · Cost estimat: X–Y lei` (null costs excluded and
counted: "+ K măsuri fără cost documentat"). Never "accidente evitate" / "vieți salvate".

**Fișa (export)** — printable list of hotspots, evidence, measures, checks, data limits, "Nu e un audit certificat".

## 6. Build order

Historical status as of 17 Oct, afternoon: phases 0–4 done on synthetic data; phase 5 partly (fișă print page done). The local HTTP integration now replaces mock reads/writes in the default build; final build/browser validation is recorded with the delivery, not assumed by this plan.

| Phase | Deliverable | Status |
|---|---|---|
| 0 · Scaffold | `ng new`, deps, `sync-data`, models, `DataApi` + mock, store, design tokens | done |
| 1 · Static UI | Shell, top bar, list, dossier, 24h chart | done |
| 2 · 3D map | MapLibre 3D city, hexagon columns, dots, pulsing rings, click → select, offline fallback | done; offline fallback not yet tested with network off |
| 3 · Import | Import screen with replay fixture, highlights, editable fields, approve → store + map | done |
| 4 · Show | Tour, Aplică măsurile, counter | done |
| 5 · Ship | Local HTTP build (`npm run build:local`), explicit static mock build (`npm run build:pages`), projector checks | HTTP integration implemented; verify build/browser on delivery; real observed data and sourced measures still pending |

Matches the timetable: phases 0–2 Saturday by 20:00; 3–4 overnight / Sunday 09:30; freeze 14:30.

## 7. Commands (after scaffold)

```
cd web
npm run backend       # API + 30-minute collector on :8000
npm start             # ng serve, http://localhost:4200 (proxy /api)
npm run build:local   # production build served by FastAPI at /ui/
```
