# UI plan — SafeIași (Person 6)

Angular front-end for the three screens + export described in `Planificare.md` §1 and §8 (Persoana 6).
Backend does not exist yet: every call goes through one API layer that today serves **mock data**
(copies of `false_data/`) and later switches to HTTP with a single config flag.

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

## 3. Placeholder endpoints

All paths live in `core/api/endpoints.ts`. Components never call `HttpClient` directly; they use `DataApi`.

| Method | Path | Returns | Mock implementation | Real owner |
|---|---|---|---|---|
| GET | `/api/manifest` | `Manifest` | `data/manifest.json` | P1 (H) |
| GET | `/api/accidents` | `Accident[]` | `data/accidents.json` | P2+P3 |
| GET | `/api/hotspots` | `Hotspot[]` | `data/hotspots.json` | P4 |
| GET | `/api/crossings` | GeoJSON `FeatureCollection<Crossing>` | `data/crossings.geojson` | P4 |
| GET | `/api/measures` | `Measure[]` | `data/measures.json` | P5 |
| GET | `/api/cameras` | `Camera[]` (`core/models/camera.ts`, TBD with P1) | `data/cameras.json` (2 real public webcams, webcamromania.ro embed + HLS stream) | TBD: city-hall CCTV list once there is an agreement |
| POST | `/api/extract` `{ text?, url? }` | `ExtractionResult` | next file from `data/replay/`, 1.5 s delay, `mode: 'replay'` | P2 (B5) |
| POST | `/api/events/:id/review` `{ decision, corrections }` | `Accident` | in-memory: updates the store signal | **TBD with P1/P2** (plan has no DB) |
| GET | `/api/report?ids=h-1,h-2` | PDF | navigates to `/fisa?ids=…` (print) | P5 (F5) |

Static deployment note: in the plan, GitHub Pages reads the JSON files directly — so the "mock" GET
implementation *is* the production implementation for the public link. Only `/extract` and `/review`
need a live server, and on the public link they run in replay mode (plan §3).

Proposed `ExtractionResult` (not in the contract yet — agree with Person 2):

```ts
interface ExtractionResult {
  mode: 'live' | 'replay';            // replay must be labelled in the UI
  model: string | null; prompt_version: string | null;
  article: { url: string | null; titlu: string | null; text: string };
  campuri: Partial<Accident>;         // same field names as accidents.json, null = unknown
  dovezi: Record<string, string>;     // field → verbatim quote; UI highlights it with indexOf
  avertismente: string[];             // e.g. "data publicării ≠ data evenimentului"
  // From the geocoding step (Person 3), never from the LLM. null = could not locate → no pin, not ranked.
  localizare_propusa: { lat: number; lon: number; precizie_loc: PrecizieLoc; metoda: string } | null;
}
```

On approve the UI posts the corrected event to `/api/events/:id/review`, adds it to the store and flies
the map to it. It never recomputes scores: the location score updates on the next pipeline run (Person 4).

## 4. Contract mismatches to raise with Person 1

1. Mock data lives in `false_data/`, plan says `data/`. → `sync-data.mjs` reads either.
2. `false_data/measure.json` vs contract `measures.json`. → script renames on copy.
3. Two schemas in docs (`Planificare.md` v2 vs `docs/HACKATHON_PLAN.md` v1). Fixtures follow **v2**; UI follows v2.
4. `/extract` response and the review/approve call are undefined (see §3).
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
"REZULTAT SALVAT (reluare)" label when `mode === 'replay'`; on approve the point appears on the map.

**Tour (G4)** — `map.flyTo` through ranked hotspots, dossier slides in, Esc stops.

**Aplică măsurile (G6)** — hotspot columns animate down; counter
`Locații vizate: N · Accidente documentate acolo: M · Cost estimat: X–Y lei` (null costs excluded and
counted: "+ K măsuri fără cost documentat"). Never "accidente evitate" / "vieți salvate".

**Fișa (export)** — printable list of hotspots, evidence, measures, checks, data limits, "Nu e un audit certificat".

## 6. Build order

Status as of 17 Oct, afternoon: phases 0–4 done on synthetic data; phase 5 partly (fișă print page done).

| Phase | Deliverable | Status |
|---|---|---|
| 0 · Scaffold | `ng new`, deps, `sync-data`, models, `DataApi` + mock, store, design tokens | done |
| 1 · Static UI | Shell, top bar, list, dossier, 24h chart | done |
| 2 · 3D map | MapLibre 3D city, hexagon columns, dots, pulsing rings, click → select, offline fallback | done; offline fallback not yet tested with network off |
| 3 · Import | Import screen with replay fixture, highlights, editable fields, approve → store + map | done |
| 4 · Show | Tour, Aplică măsurile, counter | done |
| 5 · Ship | Projector polish, GitHub Pages build (`npm run build:pages`), switch `mode: 'http'` when BE exists | todo; then run `/ui-honesty-check` |

Matches the timetable: phases 0–2 Saturday by 20:00; 3–4 overnight / Sunday 09:30; freeze 14:30.

## 7. Commands (after scaffold)

```
cd web
npm run sync-data     # refresh public/data from ../false_data or ../data
npm start             # ng serve, http://localhost:4200
npm run build         # production build into web/dist
npm run build:pages   # build with base-href for GitHub Pages
```
