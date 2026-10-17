"""Offline provenance/evidence verification; not validation of engineering quality."""
import argparse
import hashlib
import json
from pathlib import Path

from measures.local_ai import digest

ROOT = Path(__file__).resolve().parents[1]


def verify(report, articles):
    if report['source_sha256'] != digest(articles):
        raise ValueError('Article file changed since generation')
    if report['data_mode'] != 'observed_press_unverified':
        raise ValueError('Unreviewed press labeling missing')
    indexed = {a['article_id']: a for a in articles}
    seen = set()
    suggestions = 0
    for row in report['rows']:
        article = indexed[row['article_id']]
        if row['article_id'] in seen or row['article_id'] not in report['selected_article_ids']:
            raise ValueError('Duplicate/unselected result')
        seen.add(row['article_id'])
        if row['article_sha256'] != digest(article) or row['text_sha256'] != hashlib.sha256(article['text'].encode()).hexdigest():
            raise ValueError('Source mismatch')
        if row['url'] != article['url'] or row['location_id'] is not None or row['in_iasi'] is not None:
            raise ValueError('Unverified location/source claim')
        for item in row['suggestions']:
            suggestions += 1
            if item['cost_ron'] is not None or item['reduction'] is not None or item['status'] != 'needs_human_review':
                raise ValueError('Invalid suggestion labeling')
            if not item['evidence']:
                raise ValueError('Missing evidence')
            for passage in item['evidence']:
                if (type(passage['start']) is not int or type(passage['end']) is not int
                        or not 0 <= passage['start'] < passage['end'] <= len(article['text'])
                        or article['text'][passage['start']:passage['end']] != passage['quote']):
                    raise ValueError('Quote does not match original text')
    if report['completed'] and (report['errors'] or seen != set(report['selected_article_ids'])):
        raise ValueError('Incomplete report presented as complete')
    return dict(completed=report['completed'], articles=len(seen), suggestions=suggestions,
                exact_passages_verified=True, semantic_review_required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT/'measures/output/ai-real-pilot/ai_suggestions.json')
    parser.add_argument('--articles', type=Path, default=ROOT/'scraping/predare_ai/articole_v2.json')
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.report.read_text(encoding='utf-8')),
                            json.loads(args.articles.read_text(encoding='utf-8'))), indent=2))


if __name__ == '__main__':
    main()
