---
name: ui-endpoint
description: Add or change a placeholder backend endpoint in the Angular UI (web/) — model type, DataApi method, mock implementation backed by public/data fixtures, HTTP implementation, and the endpoint table in web/PLAN.md. Use when the UI needs data or an action the (not yet existing) backend will provide, or when switching an endpoint from mock to real.
---

# Placeholder endpoint (web/)

The backend does not exist yet. Every endpoint has a mock today and an HTTP version for later,
behind one interface, so switching is a config change (`environment.api.mode`).

## Steps
1. **Contract first.** Find the shape in `Planificare.md` §4. If it is not defined there (e.g. `/extract`
   response, review/approve), use the proposal in `web/PLAN.md` §3 and mark it `// TBD: agree with Person N`.
   Never rename contract fields.
2. **Model** — add/update the interface in `web/src/app/core/models/`. Nullable contract fields are `T | null`.
3. **Path** — add it to `web/src/app/core/api/endpoints.ts` (single place for all URLs).
4. **Interface** — add the method to the abstract `DataApi` in `core/api/data-api.ts`, returning `Observable<T>`.
5. **Mock** — implement in `core/api/mock-data-api.ts`:
   - GET → `http.get('data/<file>.json')` from `public/data/`.
   - POST → read a fixture from `public/data/replay/` or update in-memory state; add `delay(1500)`.
   - Honour a `?fail=1` query flag or `environment.api.mockFail` to return an error, so error UI gets built.
   - Results that stand in for AI output set `mode: 'replay'`.
6. **HTTP** — implement in `core/api/http-data-api.ts` against `environment.api.baseUrl + path`.
7. **Fixture** — if new, add a small JSON file in `web/public/data/` (synthetic, marked `"SINTETIC"` where the
   contract has a source field). Do not put fixtures in `false_data/` — that folder belongs to Person 1.
8. **Docs** — add/update the row in `web/PLAN.md` §3 (method, path, returns, mock source, real owner).
9. Verify `npm run build` passes and the consuming screen shows data, loading and error states.

Tell the user which teammate must implement the real endpoint and what shape they need to return.
