"""Run local AI proposals on explicitly selected press articles, never on map data."""
import argparse
import json
from pathlib import Path
import sys

from measures.local_ai import LocalAI, atomic_json, digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--articles', type=Path, default=ROOT/'scraping/predare_ai/articole_v2.json')
    parser.add_argument('--article-id', action='append', default=[])
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--model', default='qwen2.5:1.5b')
    parser.add_argument('--base-url', default='http://127.0.0.1:11434')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--cache', type=Path, default=ROOT/'measures/cache/local-ai')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    for path, allowed in ((args.output, ROOT/'measures/output'), (args.cache, ROOT/'measures/cache')):
        if not path.resolve().is_relative_to(allowed.resolve()) or path.resolve() == allowed.resolve():
            parser.error('Output/cache must be in dedicated measures/output or measures/cache subdirectories')
    if args.output.exists():
        parser.error('Choose a new output directory')
    articles = json.loads(args.articles.read_text(encoding='utf-8'))
    if (not isinstance(articles, list) or len({a['article_id'] for a in articles}) != len(articles)
            or args.limit < 1 or args.timeout < 1):
        parser.error('Invalid article list, limit or timeout')
    if args.article_id:
        requested = set(args.article_id)
        articles = [a for a in articles if a['article_id'] in requested]
        if requested != {a['article_id'] for a in articles}:
            parser.error('Unknown article ID')
    articles = articles[:args.limit]
    if not articles:
        parser.error('No articles selected')
    report = dict(schema_version='measures-ai-preview-1', data_mode='observed_press_unverified',
                  label='Sugestii AI locale — necesită verificare umană, fără publicare pe hartă',
                  source_file=str(args.articles), source_sha256=digest(json.loads(args.articles.read_text(encoding='utf-8'))),
                  selected_article_ids=[a['article_id'] for a in articles], rows=[], errors=[], completed=False)
    args.output.mkdir(parents=True)
    target = args.output/'ai_suggestions.json'
    try:
        client = LocalAI(args.cache, args.model, args.base_url, args.timeout, args.offline)
        for article in articles:
            print('Procesare:', article['article_id'], '|', article['titlu'], flush=True)
            try:
                row = client.suggest(article)
            except Exception as error:
                report['errors'].append(dict(article_id=article['article_id'], error=f'{type(error).__name__}: {error}'))
                atomic_json(target, report)
                print('  Respins:', report['errors'][-1]['error'], flush=True)
                continue
            report['rows'].append(row)
            atomic_json(target, report)
            print('  Sugestii:', len(row['suggestions']), '| cache:', row['trace']['cache_hit'], flush=True)
        report['completed'] = not report['errors']
    except Exception as error:
        report['provider_error'] = f'{type(error).__name__}: {error}'
        atomic_json(target, report)
        print('Eroare, fără fallback inventat:', report['provider_error'], file=sys.stderr)
        return 1
    atomic_json(target, report)
    print('Salvat:', target)
    return 0 if report['completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
