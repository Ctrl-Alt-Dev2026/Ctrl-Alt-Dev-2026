# UI plan — SafeIași (Person 6)

Angular front-end for the three screens + export described in `Planificare.md` §1 and §8 (Persoana 6).
Local API v0.7 is now connected. The default build uses **HTTP** at `/api/v1`; published views share one frozen publication, and import/review uses the versioned operator API. Explicit mock builds preserve the original synthetic prototype for static hosting. The planning notes below retain the earlier design decisions; implementation updates are marked.

Sources of truth, in order: `Planificare.md` §4 (data contract) → §5 (score, *read-only for UI*) → §7 (measures) → §11 (pre-demo checks).
`Punct Negru Iași.html` is an early prototype, not a reference for look or content. Its claims ("−55% accidente",
"efect estimat", tag-based score, CSV upload, business section) are out of scope or forbidden by the plan.

**Scope decisions (with the user, 17 Oct):** all road accidents reported in the press, participants as a filter
(pedestrians are one); a real 3D map. Live cameras (decided 17 Oct, evening): public Iași webcams on the map through
their HLS stream, analysed live in the browser (COCO-SSD objects, brightness grid, rule-based signals for an operator),
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
  scripts/sync-data.mjs        copies ../false_data (later ../data) → public/data, normalises names
  public/data/                 manifest.json, accidents.json, hotspots.json, crossings.geojson, measures.json
  public/data/replay/          saved extractions for "mod reluare" (extract-001.json …)
  src/environments/            environment.ts { api: { mode: 'mock' | 'http', baseUrl } }
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

## 3. Current local API endpoints (v0.7)

Paths are centralized in `core/api/endpoints.ts`. `DataApi` provides publication reads; `ReviewApi` provides operator actions. Components never call `HttpClient` directly. Models preserve backend field names; the adapter in `core/models/publication.ts` maps the published contracts into the existing map view without recalculating scores.

| Method | Path relative to `/api/v1` | Returns / use |
|---|---|---|
| GET | `/publications/latest?data_mode=…` | One `PublicationSnapshot`, including canonical events, locations and provenance |
| GET | `/publications/:snapshot_id?data_mode=…` | Explicit immutable URL-pinned publication |
| GET | `/locations/:id?data_mode=…&snapshot_id=…` | Version-pinned location dossier; Angular normally derives it from the already loaded snapshot |
| GET | `/locations/:id/export?format=json\|html&data_mode=…&snapshot_id=…` | Version-pinned JSON or printable HTML |
| GET | `/candidates?data_mode=…` | Review candidates; distinct from published events |
| GET | `/candidates/:id?data_mode=…` | Current candidate and source article |
| POST | `/imports` | Persist article and extracted candidates, with request ID and explicit mode |
| GET | `/imports/:id?data_mode=…` | Archived article, extraction result and processing mode |
| PATCH | `/candidates/:id` | Version-checked corrections, operator and reason |
| POST | `/candidates/:id/geocoding/preview` | Geocoding suggestion and provenance; no approval |
| POST | `/candidates/:id/geocoding/apply` | Explicitly confirmed, version-checked suggestion application |
| POST | `/candidates/:id/review` | Approve, reject or link to a canonical event; requires operator checks |
| GET | `/reviewed-events?data_mode=…` | Canonical working events, not an automatic map publication |
| GET | `/publication-context?data_mode=…&q=…&offset=…&limit=…` | Paginated infrastructure for explicit location association |
| POST | `/publications/preview` | Eligibility diagnostics and deterministic scores without publishing |
| POST | `/publications` | Immutable release after explicit source, duplicate and association checks |
| GET | `data/cameras.json` (static UI asset) | Public camera metadata, separate from accident sources |

The first publication read feeds all headline counts and display layers. Event IDs are canonical; article counts use distinct source IDs. Backend ranks remain fixed when participant filters hide locations. Locations with null score/rank remain available as unranked dossiers. Empty or unavailable observed data never selects synthetic data automatically. URL query `data_mode=synthetic` is an explicit synthetic selection; omitting it selects observed. `snapshot_id` can pin an older publication.

A specific `publication_not_found` 404 is shown as an empty publication; a 503 remains a visible error. The router and import/review stay usable. Approval is not publication: the operator explicitly selects event versions and infrastructure associations, checks the preview, and publishes. Exports use the exact displayed snapshot ID.

Run `npm start` for the dev server with `/api` proxy to `127.0.0.1:8000` (`changeOrigin: false`), or `npm run build:local` and open the API's `/ui/` route. Relative API requests then preserve the same origin. `npm run build:mock` and `npm run build:pages` explicitly produce the static synthetic prototype; import/review is read-only in those builds.

**Historical proposals:** the former `/api/manifest`, `/api/accidents`, `/api/hotspots`, `/api/crossings`, `/api/measures`, `/api/extract`, `/api/events/:id/review` and `/api/report` table described the initial mock prototype. They are not the current backend contract. `ExtractionResult` remains a legacy mock shape; real imports preserve their source article, structured candidate fields and extraction mode separately. The original plan to approve directly onto the map is superseded by explicit publication. The sourced measure catalog remains pending; empty measures are not filled with mock recommendations.

## 4. Contract mismatches to raise with Person 1

1. Mock data lives in `false_data/`, plan says `data/`. → `sync-data.mjs` reads either.
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
npm run sync-data     # refresh public/data from ../false_data or ../data
npm start             # ng serve, http://localhost:4200
npm run build:local   # HTTP production build served by FastAPI at /ui/
npm run build:mock    # explicit static synthetic prototype, read-only import
npm run build:pages   # explicit mock build with base-href for GitHub Pages
```
