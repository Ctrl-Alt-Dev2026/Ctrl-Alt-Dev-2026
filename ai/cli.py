"""Repository-root batch runner. Defaults only write beneath ignored ai/work/."""
import argparse
from pathlib import Path

from .engine import Ollama, atomic_json, load_articles, run
from .service import AI_DIR, PIPELINES, ExtractionConfig


def main(argv=None):
    config = ExtractionConfig.from_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=Path, default=AI_DIR.parent / "false_data" / "articles.json")
    parser.add_argument("--out", type=Path, default=AI_DIR / "work" / "results")
    parser.add_argument("--cache", type=Path, default=config.cache_dir)
    parser.add_argument("--model", default=config.model)
    parser.add_argument("--base-url", default=config.base_url)
    parser.add_argument("--pipelines", choices=PIPELINES, nargs="+", default=list(PIPELINES))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    protected = AI_DIR.parent / "false_data"
    for target in (args.out, args.cache):
        if target.resolve().is_relative_to(protected.resolve()):
            parser.error("AI output/cache cannot overwrite the shared false_data directory")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    articles = load_articles(args.articles)
    if args.limit:
        articles = articles[:args.limit]
    client = Ollama(args.model, args.base_url, args.cache)
    components, results = {}, {}

    def ensure(name):
        if name in results:
            return results[name]
        dependencies = ("direct", "evidence") if name == "agreement" else ("evidence",) if name == "hybrid" else ()
        for dependency in dependencies:
            ensure(dependency)
        result = run(articles, name, client, components)
        results[name] = result
        components[name] = {row["article_id"]: row for row in result["rows"]}
        atomic_json(args.out / (name + ".json"), result)
        atomic_json(args.out / name / "accidents.json", result["accidents"])
        atomic_json(args.out / name / "manifest.json", {
            "schema_version": "2.0", "data_mode": result["data_mode"],
            "pipeline": name, "nr_articole": len(articles),
            "candidate_group_count": len(result["accidents"]),
            "duplicate_review_count": len(result["duplicate_review_queue"]),
            "nr_verificate": 0, "nr_localizate_precis": 0, "review_status": "pending",
        })
        print(f"Saved {name}: {len(result['accidents'])} pending candidate groups; {len(result['duplicate_review_queue'])} duplicate review items")
        return result

    for name in args.pipelines:
        ensure(name)
    failures = any(row["trace"].get("failed") for result in results.values() for row in result["rows"])
    return 1 if failures else 0
