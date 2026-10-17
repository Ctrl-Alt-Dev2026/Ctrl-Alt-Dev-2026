---
name: ui-component
description: Create or extend an Angular component in web/ following the project conventions (standalone, signals, OnPush, store-driven, Romanian UI text, null-safe rendering). Use when adding a screen, panel, widget or shared UI piece to the Harta pietonului UI.
---

# New UI component (web/)

1. Read `web/CLAUDE.md` and the matching screen section in `web/PLAN.md` §5. If the component shows
   contract data, open the model in `web/src/app/core/models/` — do not guess field names.
2. Place it:
   - screen-specific → `web/src/app/features/<feature>/<name>/`
   - reused by 2+ features → `web/src/app/shared/<name>/`
   Generate with `npx ng g c <path> --change-detection OnPush` (run from `web/`), or write `name.ts|html|scss` by hand (Angular 21 naming).
3. Write it with:
   - `input()` / `output()` / `model()`, `computed()` for derived values, `inject()` for services.
   - Read shared data from `DataStore` signals; never call `DataApi` or `HttpClient` from a presentational component.
   - `@if / @for (track id)` control flow.
   - Styles only through tokens from `styles.scss` (`--ink`, `--muted`, `--accent`, `--heat-1..4`, `--step-*`, `--space-*`); rem/clamp, no px. Floating panels use `.glass`.
4. Data rendering rules:
   - Every nullable field goes through the `nullLabel` pipe / `<app-null-value>` → "necunoscut".
   - Enum values (`gravitate`, `precizie_loc`, `cauza_raportata`) go through `core/format/labels.ts`.
   - Sources are links (`target="_blank" rel="noopener"`), one per URL.
   - Empty list → explicit empty state text, not nothing.
5. Accessibility: clickable things are `<button>`, focus-visible outline, `aria-label` on icon-only controls.
6. Verify: `npm run build` from `web/` passes; open the screen and check it renders the synthetic fixtures
   (e.g. hotspot `h-1` "Demo – Podu Roș", score 13, 4 events). No unit tests (hackathon scope). Report files changed and what you looked at.
