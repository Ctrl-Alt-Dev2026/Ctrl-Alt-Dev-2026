# Harta pietonului – Iași (hackathon, 6 people, deadline Sun 18 Oct 16:30)

Map of pedestrian accidents reported in Iași press, extracted with AI, human-verified, ranked by a
transparent score, with candidate measures and an exportable verification sheet for the city hall.

Read first: `Planificare.md` §4 (data contract), §5 (score), §7 (measures), §11 (pre-demo checks).
`docs/` holds an alternative plan (schema v1); the mock data and the team follow **`Planificare.md` (v2)**.

## Ownership
- Each person edits only their own folder, on their own branch. Shared files (`data/manifest.json`,
  dependencies, this file) are edited by Person 1. Propose contract changes, don't make them silently.
- `web/` = UI (Person 6, Angular). See `web/CLAUDE.md`.
- `false_data/` = synthetic fixtures for development (owned by Person 1).

## Data rules (apply to every area)
- Never invent accidents, coordinates, sources, costs or safety effects. Unknown stays `null`; `null` ≠ `false`.
- One event = one accident, not one article. Several articles share one `event_id`.
- Event date ≠ publication date. Unknown hour stays `null`, never `00:00`.
- Coordinates in GeoJSON/deck.gl are `[lon, lat]`.
- Synthetic (`data_mode: "synthetic"`) and observed data are never mixed; synthetic is always labelled.
- The score is a prioritisation rule on this sample, not a probability. No "accidents avoided" or "lives saved".
- A replayed AI result is labelled as replay, never presented as live.

## When you finish a task
Say which files changed, how to run it, what you verified, and what is still uncertain.
