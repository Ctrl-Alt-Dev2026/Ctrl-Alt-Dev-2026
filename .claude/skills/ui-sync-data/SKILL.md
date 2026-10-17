---
name: ui-sync-data
description: Refresh the UI's data files from the team's contract files (../data or ../false_data) and check them against the TypeScript models, reporting contract drift. Use after teammates push new data, when the UI shows wrong/missing fields, or before a demo build.
---

# Sync data into web/public/data

1. From `web/`, run `npm run sync-data`. It copies `../data/*` if that folder exists, else `../false_data/*`,
   into `public/data/`, renaming `measure.json` → `measures.json`.
2. Read `public/data/manifest.json` and report `data_mode`, `perioada` and the counts.
   If `data_mode` changed (synthetic ↔ observed), say so loudly — the banner and demo depend on it.
3. Check every file against `src/app/core/models/` and the contract in `Planificare.md` §4. Write a small
   throwaway script in the scratchpad, or inspect with `node -e`, and report:
   - fields present in data but missing in models, and vice versa;
   - enum values outside the contract (`gravitate`, `precizie_loc`, `cauza_raportata`);
   - `lat`/`lon` outside Iași (~47.10–47.22 N, 27.48–27.68 E) or likely swapped;
   - `hotspots[].event_ids` that don't exist in `accidents.json`; `masuri[].measure_id` missing in `measures.json`;
   - `nr_evenimente` ≠ `event_ids.length`; `pe_ore` not 24 values.
4. Do **not** edit the source data. Contract problems go to the file's owner (table in `Planificare.md` §4);
   draft the message for the user to send. Adapt the UI models only if the contract itself changed.
5. Run `npm run build` and confirm the app still loads.
