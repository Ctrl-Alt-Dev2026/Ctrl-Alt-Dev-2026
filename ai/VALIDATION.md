# AI/backend integration verification

Verified on 17 October 2026 with Python 3.12. Pulled `main` initially through `46eecde`, then pulled the concurrent backend/snapshot updates through `2f523ff` and repeated compatibility checks.

## Standard backend entry point integration

The subsequent integration starts from `main` at `282ed36`, which already contains the AI delivery. `api.main:app` now includes extraction/replay routes by default; `ai.app:app` aliases the same app and factory. Registration is idempotent, and fresh processes can import either entry point first without contacting the provider.

- **28 backend tests and 42 AI tests passed**; `pip check` reported no broken requirements.
- Actual HTTP checks on the restarted `api.main:app` server confirmed health/docs/OpenAPI, rules extraction, the legacy alias, GET/POST replay, invalid-input 422, and missing-replay 404. Candidates remain pending, unverified and without coordinates.
- Ollama was unavailable on the default local endpoint. A hybrid request returned 503 with explicitly marked pending rules fallback; no live-model success is claimed.
- Manifest/events continue returning the expected `invalid_snapshot` 503 for the incomplete shared fixture. Shared fixture file hashes were unchanged after extraction. Saving candidates and approving/rejecting them are subsequent backend work.

## Checks completed

- **42 AI tests passed**: 17 extraction safety/regression checks and 25 service/router/CLI/cache integration checks.
- **26 original backend tests passed unchanged**: startup, health/OpenAPI, snapshot loading/eligibility/versioning, and the synthetic fixture audit's behavior.
- Installed the exact existing `requirements-dev.txt` / `requirements.txt` pins in an isolated ignored `.venv`; `pip check` reported no broken requirements. Shared dependency files were not edited.
- Both frozen local-model predictions reproduced from raw response cache with network access explicitly blocked in the test. The copied extraction engine retains the original benchmark behavior; service adapters add provenance without replacing core v2 fields.
- Existing backend `/health`, `/`, and OpenAPI remain accessible through `ai.app`. The backend plus AI adapter starts from an empty current directory without AI credentials or source data in that directory.
- The native `create_app(snapshot_directory)` seam and snapshot lifespan are preserved. Valid snapshot responses remain unchanged after extraction; an invalid shared snapshot continues returning 503 on data routes while pending extraction remains available.
- Rules and legacy `/extract` use the same handler as `/api/v1/ai/extract`; invalid input/coordinate injection returns 422, unavailable providers return 503 with pending diagnostics, and unknown replays return 404.
- Replay GET/POST responses are explicitly synthetic and unapproved. Extraction never copies coordinates or `verificat: true` from the team's downstream accident fixtures.
- Batch extraction runs with `python -m ai` from the repository root. Selecting only `hybrid` computes its evidence dependency. Output/cache paths within shared `false_data/` are rejected.
- The known shared fixture incompleteness remains visible: four available articles, manifest count 18, and 14 missing source references. The audit and fixtures were not relaxed or rewritten to make that inconsistency disappear.

## Commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

The current shared TestClient pins emit an upstream deprecation warning about httpx; the tests pass and the shared pins remain unchanged. On the restricted Windows agent, HTTP/ASGI tests needed localhost access; no external AI calls or credentials were used for these integration tests.

`benchmarks/verification.json` records the earlier standalone experiment's 22 checks; it is historical evidence, not this integration's test count. `benchmarks/REPORT.md` retains the four-source development results and limitations. Real model weights and generated work/venv files are not committed.
