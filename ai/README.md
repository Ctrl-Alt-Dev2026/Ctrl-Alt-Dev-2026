# Person 2 — AI extraction

Importable extraction module for the existing **Romanian schema 2.0**, integrated into the team's FastAPI backend. The initial delivery at `7765748` only added `ai/`; the backend integration now registers its router through the standard `api.main` entry point. Shared requirements and `false_data/` are unchanged.

The extraction engine uses the Python standard library. The HTTP adapter uses FastAPI/Pydantic already pinned in the root requirements. It does not install packages or connect to an AI provider at import/startup.

The same backend now also serves the [recurring-pattern investigator](patterns/README.md) at `/patterns`, alongside the extraction and persisted review workflows. It uses prepared multilingual embeddings, exposes evidence and differences, and supports removing cases to reassess a hypothesis. Its synthetic exploration does not modify reviewed records or publish events. No embedding model is loaded or downloaded by normal server startup.

## Backend integration

The proposed backend seam in `docs/BACKEND_WORK_PLAN.md` is available:

```python
from ai import ExtractionUnavailable, extract_article

try:
    candidates = extract_article(article)  # default: hybrid + local Ollama
except ExtractionUnavailable as error:
    pending_fallback_and_errors = error.result
```

`article` is the same seven-field dictionary as `false_data/articles.json`: `article_id`, `sursa`, `url`, `titlu`, `text`, `publicat_la`, `colectat_la`. It is not mutated. Candidate dictionaries preserve the existing `article_ids`, `urls`, `data_eveniment`, `ora`, `loc_text`, `participanti`, `cauza_raportata`, `gravitate`, `noapte`, `dovezi`, and geography/review fields.

Candidates always have `verificat=false`, `review_status=pending`, and null coordinates, location precision and municipality membership. Extra fields add exact quote offsets, source/prompt/model provenance, and explicit issues. Candidate IDs are provisional; persistent reviewed identity belongs to the backend.

For the full import response, including excluded/uncertain article rows, errors and processing mode:

```python
from ai import ExtractionService

service = ExtractionService()  # reuse one instance per local process
result = service.extract(article, pipeline="hybrid")
# result: schema_version, data_mode, candidates, articles,
#         processing_mode, review_status, duplicate_review_queue, errors
```

Provider failures are distinct from irrelevant articles. Hybrid can retain an explicitly labeled rules fallback; the convenience function raises `ExtractionUnavailable` with that result rather than hiding the failure. Nothing is written to the backend's candidate/approved storage by this module. An empty candidate list or absence of issues is not approval.

## Run with the existing backend

From the repository root, use the existing environment and dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

`api.main.create_app(snapshot_directory)` includes the AI router by default. Existing `/`, `/health`, `/docs`, `/api/v1/manifest`, `/api/v1/events`, and the validated-snapshot lifespan are preserved. `ai.app:app` remains a compatibility alias to the **same** application and factory; importing either entry point first does not duplicate routes. `register_ai` remains available for existing callers and is idempotent. Startup does not contact Ollama or create an extraction service.

| Route | Behavior |
|---|---|
| `POST /api/v1/ai/extract` | Extract pending v2 candidates; default pipeline `hybrid` |
| `POST /extract` | Compatibility alias using the same handler |
| `GET /api/v1/ai/replays/{article_id}` | Explicitly labeled saved synthetic extraction |

Example without a model, using the actual shared article input:

```powershell
$article = (Get-Content -Raw false_data/articles.json | ConvertFrom-Json)[0]
$body = @{ article = $article; pipeline = 'rules' } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/ai/extract -ContentType 'application/json' -Body $body
```

For saved replay, POST `{"mode":"replay","article_id":"syn-003"}` to either extraction route. Replays explicitly say **SYNTHETIC REPLAY — saved extraction, not live AI**. The response distinguishes `rules`, `live`, `cache`, `replay`, `rules_fallback`, and `unavailable`. Invalid requests return 422; missing replays return 404; provider failure returns 503 with pending diagnostics/fallback.

The inherited `/health` still checks only backend liveness, not model availability. The development adapter serializes model/cache writes in one process; a multi-worker deployment needs shared synchronization/storage. Long or multi-event articles need preprocessing and evaluation beyond the current 4096-token single-event prototype.

## Local model configuration

Defaults: `qwen2.5:1.5b` at `http://127.0.0.1:11434`; a live call needs that model in a running Ollama service. No paid API key is required.

| Optional environment variable | Default |
|---|---|
| `SAFEIASI_AI_MODEL` | `qwen2.5:1.5b` |
| `SAFEIASI_AI_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `SAFEIASI_AI_CACHE_DIR` | Package-local `ai/work/cache` |

Configuration can also be passed directly with `ExtractionConfig`. Model weights, virtual environments and generated work files are not committed.

## Batch extraction from the repository root

```powershell
.\.venv\Scripts\python.exe -m ai --pipelines rules
.\.venv\Scripts\python.exe -m ai --pipelines hybrid
```

Defaults read the current `false_data/articles.json` and write only to ignored `ai/work/`. A single `hybrid` or `agreement` selection computes its dependencies; it does not read stale results from another input. `--articles`, `--out`, `--cache`, `--model`, `--base-url`, and `--limit` are supported. The CLI rejects output/cache paths inside the shared `false_data/` and returns nonzero on model failures.

The five alternatives are `rules` (no model), `direct` (one model pass returns values/evidence), `evidence` (one model pass chooses bounded sentence IDs, then deterministic normalization), `agreement` (two correlated model passes, abstain on disagreement), and `hybrid` (rules plus an AI second reading, with review flags).

## Reproduce the completed experiment offline

`benchmarks/` contains the frozen four-source snapshot, source annotations, two-model predictions, per-field metrics, saved replays and final raw requests/responses. These are **synthetic development experiments**, not approved data and not automatically loaded by live extraction. Only an explicit benchmark cache path enables their reuse.

```powershell
.\.venv\Scripts\python.exe -m ai --articles ai/benchmarks/source_articles.json --cache ai/benchmarks/cache --base-url http://127.0.0.1:11435 --out ai/work/reproduce --model qwen2.5:1.5b
.\.venv\Scripts\python.exe -m ai.evaluate --results ai/work/reproduce
```

The historical endpoint value `11435` is part of the cache key. No service is needed for these exact cache hits. Use another output directory and `--model qwen2.5:3b` to reproduce the second model. Changing inputs/options needs actual inference; a miss is reported, never silently called live success.

The [benchmark report](benchmarks/REPORT.md) records evidence-first results of 24/28 and 25/28 fields for the 1.5B and 3B models. Rules/hybrid scored 28/28 on four tailored development sources. Those scores do not establish accuracy on real articles. The ten author-created challenge cases retain known negation/cause/classification failures.

The shared dataset still has four article texts versus the manifest's 18 and 14 missing source references. We did not fabricate missing sources, copy fixture coordinates/approval flags into extraction, or change the backend audit. Relative dates explicitly use a publication-date anchor; times and vehicle categories remain unknown when not reported. Duplicate proposals need confirmation.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m pip check
```

The AI tests need no Ollama service or credentials. They cover all 28 annotated source fields, candidate/review semantics, provider failures, exact evidence, relative dates, protected shared input paths, cached reproduction for both models, the backend import seam, root CLI execution, existing health/OpenAPI behavior, replay, and startup from an empty working directory. See [VALIDATION.md](VALIDATION.md) for the integration check results.

The backend owner retains review/persistence, geocoding and publishing. This module does not implement those responsibilities or change shared schema/dependency files. Router composition follows the [official FastAPI application structure](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
