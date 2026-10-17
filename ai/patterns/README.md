# Investigator de tipare — idea 6

An implemented, opt-in module for SafeIași that proposes **recurring reported patterns across locations**, shows the underlying cases and provenance, and lets a reviewer challenge a pattern by removing a case and recomputing the groups.

## Try the demo

Open `ai/patterns/static/index.html` in a browser. It is a complete offline application: embedded event records, genuine model-computed vectors, interactive geographic plot, evidence dialogs, case exclusion/restore, similarity controls, source-only mode, and JSON analysis export. No API key, internet, Python, model server, or installation is required to view and regroup the prepared data. The interface is Romanian.

For the integrated API, from the repository root with the existing backend dependencies installed:

```powershell
python -m uvicorn ai.patterns.app:app --host 127.0.0.1 --port 8016
```

Open `http://127.0.0.1:8016/patterns`. This opt-in app preserves the backend and extraction routes. The original `ai.app` and `api.main` entry points stay unchanged.

| Route | Purpose |
|---|---|
| `GET /patterns` | Self-contained interactive demo |
| `GET /api/v1/ai/patterns/corpus` | Prepared synthetic profiles, vectors and provenance |
| `POST /api/v1/ai/patterns/discover` | Recompute groups from prepared vectors |

Example request body:

```json
{"scope":"fixtures","threshold":0.35,"excluded":["ev-001"]}
```

Use `scope: "sources"` for the stricter matched-excerpt mode. Controls are validated; no publishing or mutation endpoints exist. Corpus/discovery routes return an explicit 503 if prepared vectors are missing, corrupt or stale relative to the input-file SHA-256. The standalone HTML is a frozen export of the prepared data and displays its hash in the method dialog.

## What is actually AI?

The actual pretrained encoder is [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), pinned to revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, with 384-dimensional normalized sentence vectors. It ran locally on CPU through sentence-transformers 5.5.0. Stored vectors are model outputs, not hand-assigned cluster labels or random coordinates. The model card describes multilingual semantic search/clustering and the Apache-2.0 license.

The model encodes short Romanian profiles built from reported concern, recorded time context, and explicitly associated crossing context. Names, coordinates, IDs, dates and severity are excluded. Unknown values contribute no phrases. Source-only profiles contain only exact matched excerpts; only those excerpts' associated facets may label source-only groups.

For fixture profiles, subtracting the eligible corpus mean and renormalizing reduces the generic language common to nearly every case. This transform was chosen while inspecting the synthetic development corpus. It is frozen in the prepared artifact: removing a case recomputes groups and counts without changing the embedding reference space.

Discovery builds overlapping neighborhoods with these transparent rules:

1. Every pair in a group must meet the cosine threshold; a bridge case cannot join unrelated cases by transitivity.
2. At least 3 unique events and 2 distinct explicitly linked sites or unassociated location descriptions are required; groups have at most 6 events.
3. Group labels summarize facets present in at least 66% of members, ordered by their difference in frequency from the eligible population. Counts include unknowns in the denominator. Labels do not claim all members share every facet.
4. Near-duplicate neighborhoods with Jaccard overlap ≥0.60 are suppressed. At most 4 candidates are shown; membership may overlap.

**AI** supplies the semantic geometry. **Deterministic logic** supplies the support requirements, descriptive labels, exact counts, provenance checks and suggested verification questions. There is no generative model inventing explanations or interventions.

The map is an offline geographic coordinate plot with points aggregated by explicit site. It has no street basemap or invented road geometry. Dashed connections mean semantic similarity, not travel paths, causality or shared road infrastructure. Coordinates are synthetic.

## What the present data supports

Input: the user's requested repository `false_data/`, frozen from the base repository at commit `7765748`.

| Available | Count |
|---|---:|
| Canonical synthetic events | 17 |
| Article texts | 4 |
| Distinct events with any article text attached | 3 |
| Fixture-only events | 14 |
| Events with exact matched explanatory excerpts | 2 |
| Missing referenced article IDs | 14 |
| Fixture profiles eligible for semantic grouping | 14 |
| Events outside Iași | 1 |
| In-city event without coordinates | 1 |

The two reports `syn-002`/`syn-003` belong to `ev-003` and never inflate event support. Context comes only from the event-to-crossing links in `hotspots.json`; the nearby Alexandru cel Bun crossing is deliberately not guessed for `ev-014`. Unknown lighting at Podu Roș is not converted into absent lighting. A source text attached to a case does **not** authenticate all of that case's fixture fields. Field-level labels show exact excerpt matches or synthetic fixture provenance.

At default threshold 0.35, two candidate groups emerge:

- **Night-time / transit proximity:** `ev-001`, `ev-003`, `ev-010`, `ev-011`, across Podu Roș and Nicolina. All four fixtures record night-time, transit proximity and an unsignalized crossing. Lighting is unknown in two of four cases. Only two cases have article text attached.
- **Lit / partly signalized context:** `ev-006`, `ev-012`, `ev-013`, across Păcurari and Copou. Lit context occurs in 3/3; signalized context in 2/3. All three are fixture-only. This is a comparison hypothesis, not a finding that lighting or signals cause accidents.

Removing `ev-001` changes the first group from 4 to 3 members, source coverage from 2 to 1, and its most distinctive labels. Removing further support can dissolve a group. Raising the threshold can leave no group. Source-only mode abstains: fewer than 5 events have matched explanatory excerpts. Five is an explicit demo guardrail, **not a scientifically sufficient sample size**.

No exposure denominator, validated causal labels or independent cluster ground truth exists. Similarity is not a calibrated confidence, accident probability, ranking of unsafe locations, causal mechanism, or estimated intervention benefit. Even fixture `verificat` flags do not turn fictional data into observed evidence. Real deployment needs larger independently reviewed report sets and domain evaluation.

The shared `false_data` remains inconsistent for the strict approved-snapshot API. Its `/api/v1/events` and `/api/v1/manifest` continue to return `invalid_snapshot` 503. This separate, explicitly labelled fixture exploration does not bypass those publication rules.

## Recompute the embeddings

Serving/viewing the prepared demo does not import or download an encoder. To deliberately regenerate it:

```powershell
python -m pip install -r ai/patterns/requirements.txt
python -m ai.patterns.download_model
python -m ai.patterns.prepare --model-path ai/patterns/work/model
python -m ai.patterns.export
```

The download is explicit, from the pinned public model repository, with remote code disabled. Cache and model weights go under ignored `ai/patterns/work/`; weights are not included in Git or the demo ZIP. Preparation uses a local model only. Re-run preparation/export whenever source profiles change. Never write generated artifacts into `false_data`.

## Validation

```powershell
python -m unittest discover -s ai/patterns/tests -v
python -m unittest discover -s tests -v
python -m unittest discover -s ai/tests -v
node ai/patterns/tests/check_parity.cjs python ai/patterns/evaluation/parity.json
python -m ai.patterns.evaluate --model-path ai/patterns/work/model
```

The new unit/integration tests cover event deduplication, unknowns, explicit associations, exact source excerpts, source-only abstention, pairwise support, exclusion/restore semantics, unchanged input files, stale/corrupt vectors, offline export and composition with existing backend/extraction routes. The Node check compares every result field against independently executed Python for 18 thresholds × 19 exclusion sets × 2 scopes: **684 matching scenarios**.

`evaluation/semantic_probes.json` stores an actual run of ten authored Romanian, English and Italian paraphrase retrieval probes against a basic TF-IDF baseline. **Embedding hit@1: 5/10; TF-IDF: 0/10. MRR: 0.634 vs 0.033.** The five embedding misses are retained. These development probes were written after inspecting the schema, are not held-out field validation, and do not establish clustering quality. The shared threshold in the supplementary cluster comparison is exploratory, not a calibrated comparison between vector methods.

## A 90-second demo

1. Open the HTML; show the synthetic banner, 17 events, and 3 events with articles.
2. Select the night-time group; show the two highlighted locations and 4 unique cases.
3. Open `ev-001`: inspect the exact speed passage and the separate unknown-lighting fixture field.
4. Remove it: watch 4 become 3, the labels change, and article coverage fall. Open another case and inspect differences.
5. Inspect a nearby case outside the group. Ask what would disprove the hypothesis.
6. Switch to source-only mode: show explicit abstention on sparse evidence. Reset and export the analysis.

This demonstrates discovery, traceability and challenge through a single coherent interaction; it does not promise a causal conclusion from seventeen fictional records.
