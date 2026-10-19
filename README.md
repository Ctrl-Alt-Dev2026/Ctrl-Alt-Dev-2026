# SafeIași — Application Documentation

Project overview, functionality, architecture, technologies and intended beneficiaries.

Prepared from the repository on **19 October 2026**. This document describes the implementation present in the checkout. Earlier plans and handoff documents describe different development stages; they should not be read as proof that every proposed feature is available in the current interface. This review did not run the application, contact data providers or re-evaluate model accuracy.

## 1. Purpose and product vision

**SafeIași is a road safety decision-support application for Iași, Romania.** It brings together reports of road crashes, historical street statistics and mapped infrastructure to help people answer:

> Which streets or locations should we investigate first, what evidence supports that choice, and what should be checked on site?

The project was developed for the AI Iași 2026 hackathon. Its earlier name, “Harta pietonului” (The Pedestrian Map), reflects its initial focus on pedestrians. The current collected-data workflow covers road crashes involving several participant categories, while some extraction experiments retain the earlier pedestrian scope.

The application turns information distributed across public releases, news articles and geographic datasets into a map with source references, explainable priorities and investigation suggestions. It can support preparation for site visits, internal discussions and location reports. It does not replace an official crash register, a certified road safety audit or an engineering design process.

The intended institutional customer is **Iași City Hall**, particularly teams working on mobility and road safety. A confirmed customer contract, institutional partnership or production adoption is not established by the repository.

## 2. Beneficiaries and practical value

| Beneficiary | Potential use |
|---|---|
| Municipal mobility and road safety teams | Identify streets for further investigation and inspect the evidence behind their order of priority. |
| Traffic engineers and urban planners | Compare reported events with mapped infrastructure and prepare questions for a site visit. |
| Operators and analysts | Collect sources, inspect extracted information, correct location proposals and manage reviewed records. |
| Public authorities and project evaluators | Read location dossiers and discuss the basis and limits of proposed studies. |
| Residents, pedestrians, cyclists and other road users | Indirect beneficiaries of better-informed investigation and eventual infrastructure decisions. |
| Researchers and civic organizations | Explore documented reports while retaining source and coverage limitations. |

These are intended uses. The project does not demonstrate a measured reduction in crashes, a validated financial return or a deployed institutional workflow.

## 3. Application at a glance

The repository contains several related workflows:

| Workflow | Implementation and role |
|---|---|
| Collected-data map | The current Angular interface reads a shared dataset collected from ISU releases and press sources, enriched with street analysis and infrastructure context. |
| Controlled import, review and publication | Backend endpoints support article import, correction, human review, assisted geocoding and explicit immutable publication. This remains a separate workflow; the current Angular data store reads the live dataset. |
| Street analysis and measures | Deterministic counts, severity components, source-specific scores, infrastructure descriptions and candidate studies. Saved AI suggestions can supplement the street panel. |
| Live cameras | Optional browser camera viewing and local frame inference, with tracking, possible incident signals and image brightness indicators. |
| SafeCross clips | A separate local interface for video analysis, evidence inspection, operator review and export. |
| Pattern investigator | A separate synthetic demonstration of semantic grouping, evidence inspection and hypothesis reassessment. |

“Live dataset” means the latest stored collection. It is not a real-time emergency feed. Camera observations are a different stream and do not automatically become crash records.

## 4. Main functionality

### 4.1 Interactive map and street exploration

The Angular interface provides a city map with street layers, sufficiently precise event locations, H3 spatial aggregation and optional camera markers. Users can select a street or location, inspect related events and follow references to their sources.

The street panel supports separate views of:

- ISU-reported interventions;
- press-reported events;
- PMUD historical street totals.

The user can compare street ordering by event count or score and filter event participants. PMUD totals have no participant breakdown, so that filter cannot be applied to those totals. A dedicated attention list identifies streets to check first using a separate fixed signal rule.

Events known only at street level remain useful in street summaries. They do not receive a precise crash pin merely because the geocoder can find a representative street point. H3 aggregation uses sufficiently precise locations.

The interface polls collection status and downloads a newer dataset when available. If the server stops responding, already loaded data can remain visible with an error indicator.

### 4.2 Automated collection

With `SAFEIASI_LIVE=1`, a background collector runs at startup when needed and then at a configurable interval, normally 30 minutes. It:

1. Runs the press scraper for new articles.
2. Fetches configured ISU listing pages and previously unseen releases.
3. Extracts text from PDFs and parses relevant crash reports.
4. Resolves locations using the local OSM index.
5. Builds a dataset and stores it in SQLite.
6. Serves the newest stored dataset to viewers.

Stored release texts and committed seed data reduce repeated downloads. Collection status and run outcomes are exposed through the API. Failure to collect new data does not mean previously stored events disappear.

### 4.3 Extraction and source evidence

There are distinct extraction paths rather than one model used everywhere:

- **ISU releases:** deterministic parsing of report text.
- **Current press collection:** saved Claude classifications and extractions where available; provisional rules for articles without saved answers.
- **Standalone extraction service:** rules and local Ollama/Qwen pipelines, plus Gemini batch/cache workflows.

Extracted fields include event date, time, location text, participants, reported cause, severity and night-time status when supported by the source. The AI service produces pending candidates and provenance, including supporting quotes. Extraction alone does not approve a record.

The Claude integration invokes the locally installed, authenticated Claude Code CLI. Its saved answers are shared through seed files and replayed during dataset builds. The build does not require running Claude in Docker. The verifier discards unsupported quoted values and malformed dates or times. This validation improves traceability but does not establish that every remaining interpretation is correct.

### 4.4 Human review and explicit publication

The controlled backend workflow supports:

1. Importing an article and saving its extraction.
2. Listing and inspecting candidates with original evidence and corrections.
3. Editing pending candidates using an expected version.
4. Previewing a geocoding suggestion and applying it with operator confirmation.
5. Approving, rejecting or linking a duplicate to a canonical event.
6. Previewing publication eligibility and deterministic scores.
7. Explicitly publishing a selected, version-checked set of events.

Approval and publication are separate actions. Published versions preserve the selected events and associated context so that map outputs, dossiers and exports can refer to the same snapshot. The publication API includes location lists, GeoJSON, detailed dossiers and JSON or printable HTML export.

**The collected-data map does not pass every automatically collected event through this review process.** Verification flags, provisional extraction labels and source limitations must therefore be interpreted per record and workflow. The presence of a collected record on the map is not evidence of human approval.

### 4.5 Geocoding and infrastructure context

`coordonate/` resolves Romanian location descriptions against a local OpenStreetMap index. It normalizes names and handles streets, intersections, segments and known nodes, preserving uncertainty and municipality membership. Normal resolution works offline; refreshing the reference extract is a separate network operation.

`context/` prepares infrastructure data such as crossings, road geometry, lane counts, signalization, lighting tags, schools and public transport stops. It validates geographic boundaries and retains collection provenance.

A street-wide infrastructure description does not prove that a particular crash happened at a particular crossing. Missing OSM tags remain unknown; they do not establish that an infrastructure feature is absent.

### 4.6 Explainable prioritization

The shared event components in `risk/scoring.py` are:

```text
event component = N + 4 × fatal-severity events + 2 × serious-severity events
```

Here, `N` is the number of distinct events in the analyzed group. The severity terms count events carrying those classifications, not numbers of victims.

For the current street analysis, the context contribution is zero. ISU and press scores are calculated separately. PMUD remains a historical total rather than being added to those scores.

The location pipeline can add documented infrastructure bonuses: +2 for a confirmed unsignalized crossing on a road with at least four lanes, +1 for a school within 150 m and +1 for a public transport stop within 100 m, when the corresponding conditions are known.

The “streets to check first” list is another mechanism: signals include high ISU or PMUD counts, severe reported events, repeated press reports and repeated pedestrian events. It is an investigation order, distinct from the numeric score.

All these outputs prioritize the available sample. They are not calibrated crash probabilities. Without exposure data, such as traffic volumes and pedestrian counts, they do not establish comparable risk per trip.

### 4.7 Candidate measures and recommendations

`measures/` contains a catalog, deterministic rules, research evidence and scenario exports. Current street analysis maps reported causes to study topics, including traffic calming, priority and crossing organization, pedestrian routes, visibility and lighting.

Saved Claude street suggestions are restricted to catalog entries and must cite relevant event IDs. They include checks to perform and missing information. Suggestions can be marked outdated when their event basis changes.

Recommendations describe candidate investigations. A street-level suggestion does not establish an installation site or number of works. Some research outputs contain historical indicative unit estimates with provenance and limitations; these are not verified local project budgets. Total implementation cost and expected safety effects cannot be inferred from the street score.

### 4.8 Live camera analysis

The optional live vision service accepts current JPEG frames within bounded in-memory sessions. Its detector combines **YOLO11s** traffic detection with a conditional **YOLO-World** pass for tram classification. Tracking and temporal heuristics produce operator signals about possible incidents. Configured crossing regions can be inspected for persistent low image brightness.

The interface can fall back to a provider player when analysis is unavailable. Model dependencies and weights require separate installation or inclusion in the container build.

These signals are unvalidated observations in image space. Image brightness is not illumination measured in lux, and tracking is not a calibrated physical speed measurement. Frame analysis does not automatically create accident records.

### 4.9 SafeCross video clips

SafeCross is a separate local module and interface at `/safecross`. It analyzes bounded clips using **YOLOX Nano**, tracking and image-space proximity rules. It provides processing jobs, evidence frames, media artifacts, versioned review of flagged candidates and exports containing provenance and decisions.

The documented public demonstration uses footage from Toronto. It does not establish validated crash or conflict detection in Iași. Clip flags remain separate from documented accidents and street rankings.

### 4.10 Semantic pattern exploration

The investigator at `/patterns` uses prepared multilingual MiniLM embeddings to explore similarities among synthetic event records. Users can inspect evidence and differences, exclude cases and recalculate groups to see how a hypothesis changes.

The prepared demo can be viewed without downloading a model at request time. Model preparation uses Sentence Transformers and scikit-learn. Sparse article evidence limits what can be concluded, and source-only analysis can abstain. This module neither proves causes nor modifies reviewed records or publications.

## 5. Sources and interpretation

| Source | Information | Main limitation |
|---|---|---|
| ISU Iași public releases | Individual reported crash interventions, dates, locations and consequences | Covers published interventions, not all crashes; collection may include county locations outside the municipality. |
| BZI and Ziarul de Iași | News reports and source text | Selective coverage, possible duplicates, ambiguous descriptions and articles about older cases. |
| PMUD Iași 2022, Table 2.11 | Historical 2020/2021 crash totals for selected arteries, attributed to IPJ data | Different period and aggregation level; not individual current events. |
| OpenStreetMap | Geographic reference and infrastructure context | Variable coverage, completeness and tag availability. |
| Public camera providers | Video for optional observation | Availability, framing and image quality depend on the provider. |
| Synthetic fixtures | Development, experiments and demonstrations | Fictional records; not evidence about actual road safety. |

ISU and press events are kept separate. Where location and timing suggest overlap, the collected workflow can flag a possible match rather than silently merge records. Counts across sources must not be summed as if duplication had been resolved.

## 6. Architecture and technologies

```text
ISU PDFs + press articles + PMUD totals
                    |
           Collection and parsing
                    |
        Local OSM location resolution
                    |
       SQLite dataset + street analysis
                    |
                 FastAPI
                    |
     Angular + MapLibre GL + deck.gl

Separate controlled path:
Article -> extraction -> candidate -> human review
        -> canonical event -> explicit publication -> dossier/export

Optional paths: live camera inference, SafeCross clips, synthetic patterns
```

| Layer | Technologies | Purpose |
|---|---|---|
| Frontend | Angular 21, TypeScript 5.9, RxJS, Angular signals, SCSS | Application views, routing, state, HTTP access and styling. |
| Mapping | MapLibre GL 5, deck.gl 9, GeoJSON | Base map, geographic overlays and aggregation rendering. |
| Video playback | hls.js | Browser playback support for compatible streams. |
| Backend | Python 3.12, FastAPI, Pydantic 2, Uvicorn, Starlette | HTTP API, validation, lifecycle management and static frontend hosting. |
| Collection | Requests, Beautiful Soup, pypdf | Fetching sources, parsing pages and reading PDF text. |
| Persistence | SQLite, JSON and JSONL files | Collected datasets, run logs, seed data, review records and publication artifacts. |
| Spatial processing | Shapely, pyproj, H3; OSMnx for reference downloads | Geometry validation, metric projection, spatial indexing and OSM preparation. |
| Text AI | Claude Code CLI, Ollama/Qwen, Gemini integrations | Distinct extraction, classification and suggestion workflows. |
| Semantic exploration | Sentence Transformers, multilingual MiniLM, scikit-learn | Offline embedding preparation and pattern experiments. |
| Computer vision | Ultralytics, PyTorch, YOLO11s, YOLO-World, YOLOX Nano, OpenCV, NumPy, CLIP dependency | Optional detection, tracking and frame/clip processing. |
| Clip utilities | FFmpeg and FFprobe | Video inspection and media processing. |
| Packaging | Docker, Docker Compose, nginx, npm, Angular CLI | Reproducible builds and local serving. |
| Deployment assets | Cloud Run container instructions and Vercel-oriented Dockerfile | Supported packaging configurations, not proof of a current public deployment. |
| Verification | Python unittest suites and module-specific validators | Contracts, workflow behavior, spatial rules and failure handling. |

Core dependencies are pinned in the root requirements; optional modules have separate requirement files. Frontend versions come from `web/package.json`. Python's standard library handles much of the extraction and offline geocoding logic.

## 7. Repository map

| Directory | Responsibility |
|---|---|
| `web/` | Angular application, map and street panels, location/report views, cameras and helper scripts. |
| `api/` | Application assembly, live dataset routes, review, publication, geocoding adapters, vision and frontend hosting. |
| `isu/` | Release collection, parsing, press integration, SQLite storage, scheduling and committed seeds. |
| `scraping/` | Press scraping, cleaning and text export. |
| `ai/` | Extraction service, providers, CSV workflows, caches, benchmarks and semantic pattern demo. |
| `coordonate/` | Location normalization, local OSM index, resolution and verification reports. |
| `context/` | OSM collection, infrastructure enrichment, city exports and validation. |
| `risk/` | Distinct-event statistics, scoring, street enrichment, H3 and scenario analysis. |
| `measures/` | Candidate intervention catalog, rules, evidence and frontend exports. |
| `safecross/` | Clip analysis, live detectors, tracking, setup and standalone UI. |
| `tests/` | Backend and integration behavior tests. |
| `false_data/` | Legacy synthetic development fixtures. |
| `deploy/` | Container builds, nginx configuration and deployment guidance. |
| `docs/` | Workflow contracts, technical guidance and historical planning. |

## 8. Data model and persistence

The shared schema distinguishes an **article** from an **event**. Several articles can describe the same canonical event. Important identifiers include `article_id`, `event_id`, candidate IDs, location/crossing IDs and publication snapshot IDs.

Records retain event dates separately from publication and collection dates. They also carry participant categories, severity, reported cause, location text, precision, geographic fields, source references and review information as applicable. Unknown values stay `null`; an unknown hour is not midnight. GeoJSON coordinates use `[longitude, latitude]`.

The live SQLite database defaults to `runtime/safeiasi.sqlite3`, with tables for documents, collection runs, datasets and extra artifacts. The store retains recent dataset versions. `isu/seed/` shares release texts, a built dataset and saved AI outputs so a fresh checkout can start from committed data.

The controlled review and publication workflows use separate runtime directories. Saved publications are immutable versions. Camera tracking sessions are in memory; live frame analysis does not persist submitted JPEGs. SafeCross jobs have their own artifact storage.

Synthetic and observed data are explicitly distinguished and must not be mixed into a purported real dataset.

## 9. API overview

The complete route schemas are available at `/docs` when the backend is running.

| Route family | Purpose |
|---|---|
| `/health` | Process liveness; does not validate datasets or model readiness. |
| `/api/v1/live/status`, `/api/v1/live/dataset` | Collection status and newest enriched dataset used by the current frontend. |
| `POST /api/v1/live/refresh` | Locally trigger collection when the scheduler is enabled. |
| `/api/v1/ai/extract`, `/extract` | Pending extraction results and compatibility entry point. |
| `/api/v1/imports`, `/api/v1/candidates`, `/api/v1/reviewed-events` | Persisted controlled review workflow. |
| `/api/v1/candidates/{id}/geocoding/preview` and `/apply` | Proposed location and explicit application. |
| `/api/v1/publications`, `/api/v1/publications/preview` | Inspect or create versioned publications. |
| `/api/v1/locations`, `/api/v1/locations.geojson`, location detail/export routes | Read published location dossiers and map outputs. |
| `/api/v1/vision/*` | Model readiness, camera sessions and JPEG frame inference. |
| `/api/v1/safecross/*` | Clip jobs, evidence, review and exports. |
| `/api/v1/ai/patterns/*` | Synthetic corpus and pattern discovery. |
| `/api/v1/manifest`, `/api/v1/events` | Legacy validated synthetic snapshot reader; separate from the live dataset. |

The legacy reader refuses invalid snapshots rather than serving partial data. Its failure does not imply that the separate live dataset endpoint is unavailable.

## 10. Running the application

### Full local stack with Docker

From the repository root, with Docker available:

```powershell
docker compose up --build
```

Default local addresses:

- Application: `http://localhost:4280`
- API documentation: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Compose builds the Angular frontend and backend, proxies API requests through nginx and persists collection data in a Docker volume. Its backend image includes the collection configuration. Vision dependencies can increase build size and startup time; `SAFEIASI_VISION=0` disables their inclusion in the build.

### Frontend development

From `web/`:

```powershell
npm ci
npm run backend
npm start
```

`npm run backend` starts the Docker-backed API. `npm run backend:local` is the Python helper alternative. Angular's development address is normally `http://localhost:4200`.

### Minimal Python API

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

This starts the core API; it does not install every optional collector, geometry, AI or vision dependency. Use the Docker stack or the module-specific requirements for the intended workflow. A bare Uvicorn invocation does not enable automatic collection unless `SAFEIASI_LIVE=1` is configured.

For the controlled publication workflow, install `requirements-publication.txt`. For clip processing, follow the SafeCross guide and install `requirements-safecross.txt`, the model and media utilities. For live inference, use `requirements-vision.txt` and `python -m safecross.live_setup`.

### Selected configuration

| Variable | Role |
|---|---|
| `SAFEIASI_LIVE` | Enable the collector scheduler. |
| `SAFEIASI_REFRESH_MIN` | Collection interval; normally 30 minutes. |
| `SAFEIASI_DB` | SQLite database path. |
| `SAFEIASI_SCRAPE_PRESS` | Enable or skip the press scraper. |
| `SAFEIASI_REVIEW_DIR`, `SAFEIASI_PUBLICATION_DIR` | Controlled workflow storage paths. |
| `SAFEIASI_SNAPSHOT_DIR` | Legacy synthetic snapshot directory. |
| `SAFEIASI_PUBLIC` | Select explicitly public surfaces, such as `ui,vision`, in supported deployment configurations. |
| `SAFEIASI_VISION_MODEL`, `SAFEIASI_VISION_TRAFFIC_MODEL` | Live detector weight paths. |
| `SAFEIASI_VISION_DEVICE` | Inference device selection. |

AI configuration is workflow-specific. In particular, `SAFEIASI_AI_MODEL` is interpreted by different module entry points; consult the relevant module guide before changing it.

## 11. Access, deployment and operational limits

Sensitive mutation workflows use local-request checks. Supported public deployment configuration can expose the interface and optionally vision inference while keeping review, publication, SafeCross and manual refresh local. These controls are not a complete institutional authentication and role-management system.

Local Compose binds exposed ports to loopback and uses a persistent volume. The deployment guide also describes a single-container build serving Angular through FastAPI and a Cloud Run configuration. In that configuration, instance-local storage and in-memory camera sessions constrain horizontal scaling. Restarted cloud instances start from the image seed unless durable external storage is added. Background collection also depends on the hosting platform allowing background CPU execution.

Prepared seed data and saved AI answers support startup without a fresh AI call. New collection still depends on source availability. Model inference depends on installed packages, weights and adequate hardware. Repository deployment files establish packaging support, not the current availability of a hosted service.

## 12. Verification and known limitations

Existing automated tests cover API startup, snapshot validation, review versions, publication consistency, geocoding, live street analysis, camera behavior, clip processing logic and AI service semantics. Module-specific suites cover context, scores, recommendations and pattern exploration.

Example backend verification commands:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/patterns/tests -v
```

Some checks require optional dependencies. This documentation update did not execute these suites and does not certify that they currently pass.

Principal product limitations are:

- Public releases and news are incomplete and selective observations of crashes.
- ISU, press and PMUD have different coverage and periods; cross-source duplication is not fully resolved.
- Street-level locations cannot establish exact crash sites or individual infrastructure defects.
- Extracted facts, reported causes and AI suggestions need human interpretation and verification.
- Scores are deterministic priorities, not validated predictive risk estimates.
- Candidate measures lack confirmed sites, quantities, local budgets and demonstrated effects.
- Camera signals and synthetic semantic patterns are experimental.
- The current frontend and the earlier controlled publication workflow use different data paths.
- A production pilot would require further decisions on authentication, durable storage, monitoring, data governance, model evaluation and operational ownership.

## 13. Possible next steps

The following are development opportunities, not completed features or commitments:

1. Agree on a unified operational workflow for collected records, human verification and public releases.
2. Establish a verified evaluation set and measure extraction and location quality on representative sources.
3. Resolve cross-source duplicates without losing provenance.
4. Validate priority rules with road safety practitioners and obtain exposure data where possible.
5. Validate candidate studies through site visits and local engineering requirements.
6. Add durable hosted storage, user roles and operational monitoring for an institutional pilot.
7. Evaluate camera signals against annotated footage before using them operationally.

## 14. Further technical reading

- [ISU, press collection and seed sharing](isu/README.md)
- [Frontend](web/README.md)
- [Deployment](deploy/README.md)
- [Review workflow](docs/REVIEW_WORKFLOW.md)
- [Publication workflow](docs/PUBLICATION_WORKFLOW.md)
- [Geocoding workflow](docs/GEOCODING_WORKFLOW.md)
- [Offline coordinate resolver](coordonate/README.md)
- [Municipal infrastructure context](context/CITY.md)
- [Risk pipeline](risk/IMPLEMENTATION.md)
- [Measures catalog and research](measures/README.md)
- [AI extraction](ai/README.md)
- [Semantic investigator](ai/patterns/README.md)
- [SafeCross](docs/SAFECROSS.md)
- [Live vision](docs/LIVE_VISION.md)

For current behavior, implementation files and current workflow-specific guides take precedence over historical planning documents.
