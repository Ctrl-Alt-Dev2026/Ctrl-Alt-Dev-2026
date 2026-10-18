# `isu/`: real crash data for the map (ISU Iași releases, PMUD street baseline, press)

Three sources, kept separate and never summed. The UI shows one at a time (switch in the street panel):

| Source | What it gives | Used as |
|---|---|---|
| **ISU Iași press releases** (`isuis.igsu.ro/comunicate-de-presa/stiri-de-presa-<an>-<id>`) | One PDF per firefighter intervention at a road crash: event date, time, street/road, vehicles, victims. Oct 2024 onward, ~250/year in the county. No personal names. | Individual events (`accidents.json`, `articles.json`) |
| **PMUD Iași 2022, Table 2.11** (IPJ Iași data, p. 73) | Crashes per artery for 2020 and 2021, 12 arteries. | Street totals in `streets.geojson` |
| **Press: BZI, Ziarul de Iași** (`scraping/`, Person 1) | Articles about crashes, 2026. | Individual events, `sursa_tip: "presa"` |

### Press (provisional)

The team's press extraction (`ai/` → `coordonate/`) is still in progress. Until it delivers an `accidents.json`,
`presa.py` reads `scraping/articole_extrase_accident_clean.csv` with strict rules: the title must describe a
crash, enforcement round-ups, court cases and follow-ups are dropped, as are articles whose accident date the scraper
found outside the period. Location = street phrase, else a known neighbourhood (`zona Podu Roș`, no point).
`cauza_raportata` is the cause *as reported* (four contract values only). Events say `extractie: "reguli provizorii"`.
Every collection reads the committed 2026 sample plus the live scraper export (`runtime/presa/candidati.csv`,
see Run). When the team's AI output exists, `build(…, presa_path=<accidents.json>)` uses it as is.

Press events are never merged with ISU events. When a press event and an ISU event are on the same street and the ISU
event happened up to 3 days before the article, both get `posibil_acelasi_cu` (shown in the UI, not merged).

### Streets to check first (`prioritate`, `semnale`, `de_verificat` in `streets.geojson`)

Fixed rule, written before looking at the result. One signal per independent fact:
1. top 5 streets by ISU interventions; 2. top 5 PMUD arteries by 2021 crashes; 3. at least one event (ISU or press)
with a death or serious injury; 4. at least 2 distinct press reports; 5. at least 2 events with pedestrians.
Streets with 2+ signals are listed, ordered by number of signals, then ISU count, then PMUD 2021 (max 10).
This is a reading order for a field check, not a risk score; it is a **proposal** for Person 4 (scores) and
Person 1, not part of Planificare §5. `de_verificat` applies Planificare §7 at street level: 2+ night events → lighting;
2+ reported failures to yield → intersection visibility; always "field observation", since sources name the street only.

## Run

The server does it: with `SAFEIASI_LIVE=1` the API (`api/live_router.py`) starts a collector thread that runs
`isu.live.run_once()` at start (unless the stored data is younger than the interval) and then every
`SAFEIASI_REFRESH_MIN` minutes (default 30). One run:

1. the press scraper (`scraping.scraper_stiri --noutati`, Person 1's CLI) as a subprocess, at most 40 tasks 5 s apart,
   15 min timeout, in `SAFEIASI_PRESS_DIR` (default `runtime/presa`); `SAFEIASI_SCRAPE_PRESS=0` skips it;
2. the 3 ISU listing pages, then only the releases not yet in the database (PDF -> text, the PDF is not kept);
3. parse, geocode, build, and store the dataset in SQLite (`SAFEIASI_DB`, default `runtime/safeiasi.sqlite3`).

The UI reads `GET /api/v1/live/status` and `GET /api/v1/live/dataset`; everyone sees the same stored dataset.

```powershell
python web/scripts/backend.py                 # API on :8000 with the collector on (installs requirements once)
.venv\Scripts\python -m isu                  # one run by hand, into the same database
.venv\Scripts\python -m isu --export out\   # ... and write the contract files for teammates who work on files
docker compose up --build                     # api + nginx web on http://localhost:8080, data in the `data` volume
```

The first run on an empty database fetches ~400 releases (~3-5 min). After that a run takes ~7 s plus the scraper.
Tables: `documents` (release texts), `runs` (log), `datasets` (last 5, served as is), `extras` (article texts and
geocoding report of each dataset). A failed listing keeps the stored releases; a failed PDF is retried next run.
`isu/cache/` is only read once to seed an empty database from an earlier file-cache version; it can be deleted.
New year: add its listing slug to `config.LISTINGS` (the ids are not discoverable).

## How a release becomes an event (rules in `parse.py`, no LLM)

- **Kept:** titles matching a crash (`config.TITLE_CRASH`), minus railway, aviation, work accidents and drills
  (`config.TITLE_EXCLUDE`); the body must then confirm a road crash (`parse.BODY_CRASH`).
- **Body:** text between the header and the safety advice/footer. The advice talks about speed and alcohol and
  is never read. The footer holds ISU's own address (Strada Lascăr Catargi), so it is cut too.
- **Release date:** the later of the listing title date and the PDF header date (both have typos at times).
  **Event date** is the date in the body ("în data de 23.09.2026", "7 ianuarie a.c."), accepted only from 1 day after
  to 40 days before the release date. Otherwise it stays `null`. The release date is never used as the event date.
- **Time:** "ora 18:24". Missing → `null`.
- **Location:** street phrase (strada/bulevardul/șoseaua/calea/… + capitalised name) from the title, then the body;
  otherwise the road number (DN28, DJ208L, E583); plus the locality. Geocoded offline with `coordonate/`.
  When the geocoder can't choose between disconnected OSM pieces of a street (Șoseaua Nicolina), the event has
  no point (`vag`), but still counts on that street in `streets.geojson`.
- **`in_iasi`:** from the geocoder; if unknown but the release says "municipiul Iași", `true`.
- **`gravitate`:** `deces` if the release reports a death; `grav` if it says "stare gravă", "inconștient",
  "politraumatizat", resuscitation, or ISU titles it "accident rutier grav"; `usor` if there are victims and none of the
  above (ISU calls them "conștiente"); `necunoscut` if there were no victims or nothing is said.
  The quoted passage is in `dovezi.gravitate`.
- **`noapte`:** the reported time is between sunset and sunrise in Iași on that date (NOAA formula, ±2 min).
  `null` without a time.
- **`cauza_raportata`:** always `null`. ISU does not report causes; the police investigation does.
- **Duplicates:** releases on the same day and place within 90 minutes are merged into one event (several `article_ids`).

## Output (stored dataset, `data_mode: "observed"`)

Contract files (`Planificare.md` §4) plus extensions, **proposed to Person 1, not yet in the plan**:

- `accidents.json`: contract fields + `sursa`, `strada_osm`.
- `manifest.json`: + `surse` (both sources with URLs), `statistici` (counts per step).
- `streets.geojson` (new file): one MultiLineString per street (OSM geometry), with `isu_evenimente`, `isu_deces`,
  `isu_grav`, `isu_noapte`, `isu_event_ids`, `pmud_2020`, `pmud_2021`, `pmud_strada`, `pmud_nota`.
  `pmud_*: null` means "not in the PMUD table", not zero.
- `hotspots.json`: Planificare §5 only on precisely located events with 2+ events at the same point. With ISU text
  this is currently empty (releases name streets, not crossings), so the UI ranks streets by count instead.
- `raport_geocodare.json`: method and "to check" notes per event (not synced to the UI).

PMUD table → OSM: the table writes "Str." for every artery. `pmud2022_tabel_2_11.csv` maps each row to the OSM artery
and says why in `nota_mapare` (e.g. "Str. Bucium" → Șoseaua Bucium). Values were read from the rendered page,
because text extraction shifts the rows.

## Limits (say them in the pitch)

- ISU covers only crashes where firefighters were called. The police register about 650 crashes a year in the
  municipality; ISU reports ~75 a year there. The data is real, but it is a sample.
- Street precision only: a count per street is not a risk per km.
- Not verified by hand (`verificat: false` everywhere).
- County events outside the city are kept in `accidents.json` but have no coordinates (the OSM index covers the city).
