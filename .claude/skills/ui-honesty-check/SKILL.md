---
name: ui-honesty-check
description: Audit the Angular UI against the project's data-honesty rules and the pre-demo checklist (Planificare.md §11) before a demo, freeze or deploy. Use when asked to check the UI is demo-ready, before the 14:30 feature freeze, or before publishing the GitHub Pages link.
---

# UI honesty / demo-readiness check

Run each check, then report a table: check · pass/fail · evidence (file:line or screenshot) · fix.
Don't fix silently; list fixes and apply them only if the user agrees.

## Code search (web/src)
1. No forbidden claims: grep for `evitat`, `salvat` (outside "rezultat salvat"), `vieți`, `probabilitate`,
   `efect estimat`, `%` next to accidents. The score must not be called a risk probability.
2. No score math in the UI: no reweighting of `gravitate`, no sum over events producing `scor`.
3. `null` handling: every nullable model field rendered through the null pipe/component; no `?? 0`,
   `?? false`, `|| 'nu'` on contract data.
4. Synthetic banner bound to `manifest.data_mode === 'synthetic'`; replay label bound to `mode === 'replay'`.
5. No hard-coded counts, names or coordinates in components (all from the store).

## In the running app (Playwright MCP or /run, 1280×720)
6. Top bar numbers equal `manifest.json`. Ranked list length = number of hotspots (no padding to 10).
7. Pick 2 hotspots: dossier event count, map tooltip, "Aplică măsurile" counter and `/fisa` show the same numbers.
8. An event with `ora: null` shows "oră necunoscută"; `iluminat: null` shows "necunoscut".
9. Approximate events (`strada`/`vag`) look different and are not in the ranking; `lat: null` events are not on the map.
10. Every event shows a link per source URL.
11. Network off (or basemap URL broken): layers still render, notice shown.
12. Import screen: replay label visible on the public build; a failing extract (`mockFail`) shows an error and leaves approved data intact.
13. Text readable on a projector: body ≥ 14px, contrast OK in the dark theme.

## Final build
14. If this is the demo build: `manifest.data_mode` must be `observed` (Planificare.md §11.6). If it is still
    synthetic, say so as a blocker.
