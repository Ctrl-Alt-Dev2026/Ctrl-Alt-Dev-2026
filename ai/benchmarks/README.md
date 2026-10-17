# Archived synthetic experiment

Source snapshot: `false_data/` at commit `77b0a0908ecf2b6a919a13ef003056f1c815705e` of this repository. The integration was prepared after pulling the backend at `46eecde`, then refreshed and tested against `2f523ff`; shared article fixtures stayed unchanged.

- `source_articles.json`, `source_snapshot/`: immutable source copies, with hashes in `benchmark_manifest.json`.
- `repository_annotations.json`: four source-level annotations / three event groups, with explicit corrections for unsupported downstream fixture assumptions.
- `results_1p5/`, `results_3b/`: final five-pipeline results and metrics for both local models.
- `stress_articles.json`, `stress_expected.json`, `stress/`: ten author-created fictional challenge articles, annotations and final 1.5B-model results.
- `cache/`: 37 saved final bounded-schema requests/responses, including an unscored synthetic HTTP smoke call. No model weights or credentials.
- `replays.json`: three explicitly synthetic, unapproved replay examples.
- `verification.json`, `endpoint_smoke.json`, `offline_reproduction.json`: historical standalone-harness checks. Current package/backend checks are in `../VALIDATION.md`.
- `REPORT.md`: the earlier standalone research report. Its references to the old server/exports describe that original deliverable; `../README.md` describes the current package and router.

All extractions remain pending. This archive is not a publicable dataset, a real-news held-out evaluation, or evidence that four tuned examples generalize. Live extraction defaults to a separate ignored `ai/work/cache`, not this archive. The annotation/reference fixtures are never input to the extraction model.
