"""Repository-root batch runner. Defaults only write beneath ignored ai/work/."""
import argparse
from pathlib import Path

from .engine import Ollama, atomic_json, load_articles, run
from .service import AI_DIR, PIPELINES, ExtractionConfig, ExtractionService


def main(argv=None):
    config = ExtractionConfig.from_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles", type=Path, help="implicit: CSV-ul clean din scraping; JSON explicit pentru benchmark")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache", type=Path, default=config.cache_dir)
    parser.add_argument("--model", default=config.model)
    parser.add_argument("--base-url", default=config.base_url)
    parser.add_argument("--pipelines", choices=PIPELINES, nargs="+")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    csv_mode = (args.articles is None and args.pipelines != ["rules"]) or (
        args.articles is not None and args.articles.suffix.lower() == ".csv")
    args.out = args.out or AI_DIR / "work" / ("presa" if csv_mode else "results")
    protected = AI_DIR.parent / "false_data"
    for target in (args.out, args.cache):
        if target.resolve().is_relative_to(protected.resolve()):
            parser.error("AI output/cache cannot overwrite the shared false_data directory")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if csv_mode:
        selected = args.pipelines or ["hybrid"]
        if len(selected) != 1:
            parser.error("Fluxul CSV folosește un singur pipeline de extracție.")
        service = ExtractionService(ExtractionConfig(model=args.model, base_url=args.base_url, cache_dir=args.cache))
        result = service.extract_clean_csv(source=args.articles, output=args.out,
                                           pipeline=selected[0], limit=args.limit)
        print(f"Press flow: {result['valid']} valid, {result['rejected']} rejected, {result['uncertain']} uncertain; {result['extracted']} extracted")
        return 1 if result["errors"] or result["status"] != "completed" else 0
    articles = load_articles(args.articles or AI_DIR.parent / "false_data" / "articles.json")
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

    for name in args.pipelines or list(PIPELINES):
        ensure(name)
    failures = any(row["trace"].get("failed") for result in results.values() for row in result["rows"])
    return 1 if failures else 0
