# `isu/`: real crash data for the map (ISU Iași releases, PMUD street baseline, press)

Three sources, kept separate and never summed. The UI shows one at a time (switch in the street panel):

| Source | What it gives | Used as |
|---|---|---|
| **ISU Iași press releases** (`isuis.igsu.ro/comunicate-de-presa/stiri-de-presa-<an>-<id>`) | One PDF per firefighter intervention at a road crash: event date, time, street/road, vehicles, victims. Oct 2024 onward, ~250/year in the county. No personal names. | Individual events (`accidents.json`, `articles.json`) |
| **PMUD Iași 2022, Table 2.11** (IPJ Iași data, p. 73) | Crashes per artery for 2020 and 2021, 12 arteries. | Street totals in `streets.geojson` |
| **Press: BZI, Ziarul de Iași** (`scraping/`, Person 1) | Articles about crashes, 2026. | Individual events, `sursa_tip: "presa"` |

### Press and street suggestions (Claude, `isu/ai.py`)

An AI step runs through **Claude Code** (`claude -p`, model `claude-haiku-5-5` = Haiku 5.5, effort `low`) on the operator's own claude.ai
login: no API key, no cost per call, a few seconds per call, 4 in parallel. It runs only where Claude Code is installed
and logged in (`npm run ai` from `web/`), never in Docker. Answers are saved in `isu/seed/ai/` and committed; the
build (Docker included) replays them, and the map labels them `Claude (<model>), rezultat salvat (reluare)`.

- **Articles** (`isu/seed/ai/articole.json`, one line per article, keyed by a hash of prompt version + URL + text): `tip` is
  `accident_actual` / `urmare_judiciara` (trials, sentences, arrests about an older crash: excluded) / `alt_subiect` /
  `neclar`. Scope: every current road crash, any participants. For `accident_actual` the answer carries the contract
  fields (`data_eveniment`, `ora`, `loc_text`, `participanti`, `gravitate`, `cauza_raportata`, `noapte`) plus street
  and locality, each with a quote. `verify()` drops any value whose quote is not found verbatim in the article and
  any malformed date/hour. Counts per verdict are in `manifest.statistici.presa_ai_*`.
- **Articles without a saved answer** (scraped after the last `npm run ai`) go through the strict provisional rules
  of `presa.py`, labelled `extractie: "reguli provizorii"`, until the next `npm run ai`.
- **Streets** (`isu/seed/ai/strazi.json`, one line per street id): for each street with at least 2 events (or on the
  "Străzi de verificat" list), Claude gets the street's events, its PMUD totals and the catalog of
  `measures/output/three-scenarios/measures.json`, and returns at most 3 studies **chosen from that catalog only**,
  each citing the street's event ids, plus what to check on site and what data is missing. No costs, effects or
  new measures. Unknown measure ids and uncited suggestions are dropped. `properties.recomandari_ai.actual` is false
  when the street's events changed after the suggestion.
- `npm run ai -- --limita 5` tries a few calls; `--refa` asks again; `SAFEIASI_AI_MODEL=sonnet` for a larger model.
- The team's Gemini pipeline (`ai/`, `POST /api/v1/ai/extract`) is left as is; the map no longer reads it, since its
  scope is pedestrians only.
- `build(…, presa_path=<accidents.json>)` still takes a finished contract file as is.

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
npm run backend          (in web/)            # API in Docker on 127.0.0.1:8000, collector on, dependencies in the image
npm run backend:share    (in web/)            # same, and rewrite isu/seed/ in the checkout after every collection
npm run ai               (in web/)            # Claude step: articles + street suggestions, rebuild, rewrite isu/seed/
python web/scripts/backend.py [--share]       # without Docker: .venv, installs requirements once
npm run ai               (in web/)            # Claude step: articles + street suggestions, rebuild, rewrite isu/seed/
.venv\Scripts\python -m isu                  # one run by hand, into the same database
.venv\Scripts\python -m isu --seed           # one run, then write isu/seed/ (add --no-run to skip the run)
.venv\Scripts\python -m isu --export out\   # ... and write the contract files for teammates who work on files
docker compose up --build                     # api + Angular UI (nginx) on http://localhost:4280, data in the `data` volume
```

## Sharing the data through git (`isu/seed/`)

`runtime/` (the database) is git-ignored; `isu/seed/` is committed (~1.8 MB) and is what a clone starts from:

- `documents.jsonl`: every ISU release text collected so far (so nobody downloads the ~400 PDFs again);
- `presa_candidati.csv`: press articles the live scraper found after the committed 2026 sample;
- `dataset.json`: the exact dataset the API serves (built_at inside), so a fresh start shows the map at once
  instead of waiting about a minute for the first build;
- `ai/articole.json`, `ai/strazi.json`: the saved Claude answers (`npm run ai`), replayed by every build.

The IPJ numbers have no file here: they are `pmud2022_tabel_2_11.csv` (source data, read at every build) and end
up in `dataset.json` as the street totals.

When the server (or `python -m isu`) opens the database it adds the seed's missing release texts, and the seed's
dataset if it is newer than the local one. So after `git clone` or `git pull` + restart, everyone sees the same data
as whoever wrote the seed, with no network needed; their own collector then only fetches what came after.

To share fresh data: `python -m isu --seed` (or run the backend with `--share`), then commit `isu/seed/`.
One person should do it (the data owner): `isu/.gitattributes` marks the seed `-diff merge=binary`, so two seeds
written in parallel conflict as a whole. Resolve by taking either side and running `python -m isu --seed` again.

Without a seed, the first run on an empty database fetches ~400 releases (~3-5 min). After that a run takes ~3-7 s
plus the scraper.
Tables: `documents` (release texts), `runs` (log), `datasets` (last 5, served as is), `extras` (article texts and
geocoding report of each dataset). A failed listing keeps the stored releases; a failed PDF is retried next run.
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
