# web/ — Angular UI (Person 6)

Plan, screens, endpoint table and build order: `web/PLAN.md`. Read it before starting a feature.
`../Punct Negru Iași.html` is an early prototype: **not** a visual or content reference. Do not copy its look or its claims
("−55%", "efect estimat", its tag-based score, CSV upload, business section).

Scope (decided with the user): all road accidents reported in the press, with participants as a filter (pedestrians are one of them).
Live cameras: public webcams (host allow-list in `camera-viewer.ts`). Their HLS stream is analysed in the browser
(`features/map/camera-stage/`): COCO-SSD boxes on 3×2 tiles, image brightness grid, rule-based "semnale de verificat".
The rules are untuned and unvalidated: keep them labelled as signals for an operator, never as detected accidents.
If the stream can't be read, the viewer falls back to the provider's embed iframe, without analysis.

## Commands
- `npm run sync-data` — copy `../false_data` (or `../data` when it exists) into `public/data`. Run after teammates push data.
- `npm start` — dev server on http://localhost:4200
- `npm run build` — must pass with zero errors before committing
- Windows: run `npx` through `cmd /c` in MCP configs.
- Angular 21 (Node 22.15 here; Angular 22 needs Node ≥ 22.22). `.npmrc` sets `legacy-peer-deps` to dodge an npm 11.3 resolver crash.
- No tests: hackathon scope. Verify by building and looking at the page.

## Angular conventions
- Standalone components only, `ChangeDetectionStrategy.OnPush`, zoneless.
- Signals for state: `signal`, `computed`, `input()`, `output()`, `model()`. No `@Input` decorators, no NgRx.
- `inject()` instead of constructor injection. Built-in control flow `@if/@for/@switch`, never `*ngIf`.
- One component per folder: `name.ts|html|scss` (Angular 21 naming, class `Name` without a Component suffix). Small components use inline templates. Feature code in `src/app/features/<feature>/`, reusable bits in `shared/`.
- Shared state lives in `core/state/data.store.ts`; components read signals from it, they do not re-fetch.
- MapLibre/deck.gl objects are created in `afterNextRender` and destroyed in `DestroyRef.onDestroy`. Never put the map instance in a signal.

## 3D map (features/map/city-map) — read before touching it
- MapLibre **5** (pinned `^5`): deck.gl 9.4 does not support MapLibre 6 yet.
- Basemap: OpenFreeMap `dark` style, recoloured; OSM buildings extruded (`building-3d`); DEM hillshade only (true terrain would bury deck columns).
- deck.gl runs **overlaid** (`interleaved: false`): interleaved mode wipes the MapLibre 5 canvas.
- Never call `overlay.setProps` every frame: it makes deck redraw on its own. Per-frame animation (pulse) uses MapLibre paint properties; deck is rebuilt only on data change or during the "Aplică măsurile" transition.
- Above zoom 15 (or with a location selected) columns hide and events show as dots coloured by severity.
- In dev the map is on `window.safeMap` for console debugging. Headless screenshots sometimes catch a blank WebGL frame: take a second one before debugging.
- No internet → after 10 s it switches to a plain background style and shows a notice; data layers still render.

## API layer (backend does not exist yet)
- Components never use `HttpClient`. They call `DataApi` (`core/api/data-api.ts`).
- Every path is in `core/api/endpoints.ts`. `environment.api.mode` picks `MockDataApi` (reads `public/data/*.json`, `public/data/replay/*`) or `HttpDataApi`.
- A new endpoint = model type + `DataApi` method + mock impl + http impl + row in `web/PLAN.md` §3. Use the `/ui-endpoint` skill.
- Mock POSTs simulate latency (~1.5 s) and can fail on demand, so loading and error states get built.

## Data in the UI (non-negotiable, see Planificare.md §4, §11)
- Models in `core/models/` mirror the contract field names exactly (Romanian: `gravitate`, `precizie_loc`, …). Don't rename.
- The UI never computes or reweights the score. It displays `scor` and `componente_scor` as given.
- `null` renders as "necunoscut" / "oră necunoscută" / "cost nedocumentat" — never as "nu", "0" or blank.
- `precizie_loc` `strada`/`vag` → drawn as "localizat aproximativ", excluded from the ranking.
- `data_mode === 'synthetic'` → permanent red "DATE SINTETICE" banner.
- Extraction `mode === 'replay'` → visible "rezultat salvat (reluare)" label.
- Measure reduction (`reducere_tipica`) is literature info with its source, not a prediction.
- Show as many ranked locations as the data has; never pad a Top 10.
- All UI text in Romanian with diacritics (ș, ț, ă, î, â).

## Design
- Night cartography: the map is the page, UI floats on `.glass` panels. Tokens in `src/styles.scss`.
- Warm `--heat-1..4` is for data only (columns, severity); ice-blue `--accent` is for interaction only (selection, focus, primary buttons).
- One family, Archivo: condensed width (`font-stretch: 75%`) for headings/numbers, normal for text.
- Sizes in `rem`, `clamp()` and the `--step-*` / `--space-*` tokens; no hard-coded px (except 1px hairlines via `--hair`).
- Test at 1280×720 (projector) and ~400px wide (stacked layout below 56rem).
- If the basemap fails to load, keep layers on a plain dark background and show a small notice.

## Verify before saying done
`npm run build` passes, then open the page and check the changed screen (use `/run` or the Playwright MCP to screenshot). Before the demo run `/ui-honesty-check`.
