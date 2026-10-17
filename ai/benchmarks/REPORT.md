# Person 2 — measured AI pipeline comparison

Use the **hybrid pipeline as the development prototype**, with source quotes and mandatory review. For an independent model extraction path, compare the evidence-first results below before using direct JSON extraction. The two local models are benchmark candidates; these tests do not establish production suitability or a best model for real news.

The data is the requested [repository false_data snapshot](https://github.com/andrei-vladjitaru/Ctrl-Alt-Dev-2026/tree/77b0a0908ecf2b6a919a13ef003056f1c815705e/false_data), commit `77b0a0908ecf2b6a919a13ef003056f1c815705e`. The original ZIP is excluded from these final metrics.

## What is actually available

Four source articles describe three fictional events. The larger accident fixture has 17 events and references 18 source IDs, of which 14 are missing. Its coordinates and verification flags belong to a downstream synthetic demo fixture. They are not evidence from extraction and were never given to the model.

The four sources are development data. There is no meaningful held-out estimate here, and all four are positive pedestrian reports. Reported field totals measure agreement with source annotations under the declared date/participant policies; they do not mean real-world factual accuracy.

## Repository results

| Model | Pipeline | Correct source fields | Correct known fields | Relevance | Median original inference / article |
|---|---|---:|---:|---:|---:|
| none | rules | 28/28 | 24/24 | 4/4 | 0 model calls |
| Qwen2.5 1.5B | direct | 5/28 | 3/24 | 2/4 | 9.86 s |
| Qwen2.5 1.5B | evidence | 24/28 | 20/24 | 4/4 | 5.01 s |
| Qwen2.5 1.5B | agreement | 5/28 | 3/24 | 2/4 | 14.87 s |
| Qwen2.5 1.5B | hybrid | 28/28 | 24/24 | 4/4 | 5.01 s |
| none | rules | 28/28 | 24/24 | 4/4 | 0 model calls |
| Qwen2.5 3B | direct | 16/28 | 12/24 | 4/4 | 21.95 s |
| Qwen2.5 3B | evidence | 25/28 | 21/24 | 4/4 | 11.57 s |
| Qwen2.5 3B | agreement | 16/28 | 12/24 | 4/4 | 33.47 s |
| Qwen2.5 3B | hybrid | 28/28 | 24/24 | 4/4 | 11.57 s |

Each article contributes seven fields, for 28 fields total. Known-field recall excludes correct unknown/null values. Location matching normalizes accents and street abbreviations but requires the full location phrase. The agreement latency sums its two component calls; hybrid reuses the evidence call in the comparison and needs one model call per fresh article. No third-model invocation is hidden in either score. Timings include local CPU execution and cold-start effects, excluding downloads. Replaying the cache is not live inference.

The rules profile was adapted to these four examples, so its score is not evidence of generalization. Hybrid extraction has the same rule-based facts here; AI adds discrepancy review, not extra factual accuracy. A lower disagreement score can reflect abstention rather than a newly invented value.

## Additional challenge test

Ten additional author-created fictional cases contain eight positive events and two negatives. They are a regression/challenge set, not independently collected real articles. Seven fields are scored on the eight positive events (56 fields); relevance is scored on all ten articles.

| Model | Pipeline | Correct source fields | Correct known fields | Relevance | Median original inference / article |
|---|---|---:|---:|---:|---:|
| none | rules | 54/56 | 29/30 | 9/10 | 0 model calls |
| Qwen2.5 1.5B | direct | 25/56 | 4/30 | 8/10 | 6.74 s |
| Qwen2.5 1.5B | evidence | 40/56 | 20/30 | 8/10 | 3.63 s |
| Qwen2.5 1.5B | agreement | 23/56 | 2/30 | 8/10 | 10.29 s |
| Qwen2.5 1.5B | hybrid | 54/56 | 29/30 | 9/10 | 3.63 s |

All errors, field breakdowns, token counts, and original response traces are retained in the metrics and cache. Exact source offsets show that the quoted text exists. They do not constitute a semantic entailment proof. Hypothetical-cause confusion and negation remain cases that need a reviewer even when the output is valid JSON.

## Duplicate handling and three described events

syn-002 and syn-003 describe the same Wednesday-evening fatality at Podu Roș. The follow-up does not repeat the hour or an explicit vehicle category. Rule/hybrid blocking proposes this pair for review, without copying the missing time into the follow-up's source-level extraction or asserting a car class from 'șofer'. The final extraction export can therefore contain four pending candidates and one duplicate-review item. Three unique events is the source annotation after confirming that pair, not a claim of four accidents.

## Decisions and limitations

- Prefer evidence-first generation over unconstrained value generation for the model path, retaining bounded evidence IDs and deterministic checks. A valid schema still allows the wrong valid sentence to be selected.
- Keep the hybrid as a review assistant. It retains explicit source patterns when the AI misses an article and makes disagreements visible. It can retain a wrong rule-based candidate, so review must remain mandatory.
- Retain the agreement pipeline as a comparison, not a preferred default. It costs two calls, loses coverage through abstention, and uses correlated predictions from the same model.
- Resolve relative dates with a visible publication-date anchor. Missing dates remain unknown; 'seara' does not invent a time. Source wording, not a clock-only cutoff, determines the night/evening field.
- Do not use synthetic coordinates, source fixture approvals, or missing-source events to increase extraction scores. The pipeline leaves geometry, municipality membership and approval to the responsible reviewers/P3.
- Before real deployment, collect the missing sources or replace the fixture, freeze the prompt, and evaluate at least the planned 15 independent real articles with human annotations. Four tuned examples and a synthetic challenge set cannot establish a trustworthy error rate.

## Delivered and verified

The package contains runnable code, original repository data, two local-model comparisons, five pipeline outputs, bounded schemas/prompts, raw responses, per-field errors, original inference timings, conservative duplicate queues, local POST /extract, explicit replay mode, failure-handling tests, and optional v1/v2 candidate exports. Model weights are excluded from the ZIP. See `verification.json` for completed checks and `benchmark_manifest.json` for identities/hashes.

The initial unbounded-schema run exposed invented sentence IDs and missed articles. Its saved outputs are retained under `experiments/`. The final bounded schema restricts IDs to the current article; prompts and parsers were revised during development. No final score is presented as a blind independent evaluation.

Technical implementation uses [Ollama's schema format](https://docs.ollama.com/capabilities/structured-outputs) and [Generate API](https://docs.ollama.com/api/generate). Model identities are documented on the [1.5B](https://ollama.com/library/qwen2.5:1.5b) and [3B](https://ollama.com/library/qwen2.5:3b) pages. These API/model sources do not support extraction-accuracy claims; the saved experiments do.
