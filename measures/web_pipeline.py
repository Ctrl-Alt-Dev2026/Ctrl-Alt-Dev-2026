"""Incremental article processing through the ChatGPT website, without an AI API."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

from measures.chatgpt_exchange import ROOT, SOURCE, chat_message, import_response, prepare, strict_json
from measures.storage import atomic_json, digest
from measures.web_scraper import BrowserBlocked, browser_transport, exclusive, own_path, parse_response

VERSION = 'measures-web-pipeline-1'
CACHE = ROOT/'measures/cache/web-incremental'
OUTPUT = ROOT/'measures/output/web-incremental'
FIELDS = ('article_id', 'sursa', 'url', 'titlu', 'text', 'publicat_la')


def normalize(article):
    if not isinstance(article, dict):
        raise ValueError('Article must be an object')
    for name in FIELDS[:-1]:
        if not isinstance(article.get(name), str) or not article[name].strip():
            raise ValueError(f'Invalid/missing {name}')
    if article['sursa'].upper() == 'SINTETIC':
        raise ValueError('Synthetic article is not an observed press source')
    if article.get('publicat_la') is not None and not isinstance(article['publicat_la'], str):
        raise ValueError('Invalid publication date type')
    # Collection timestamps and unrelated metadata do not change the AI input.
    return {key: article.get(key) for key in FIELDS}


def packet_for(articles):
    return prepare(articles, ids=[a['article_id'] for a in articles])


def article_key(article):
    return digest(dict(version=VERSION, message=chat_message(packet_for([article]))))


def validate_batch(directory):
    job = strict_json(directory/'job.json')
    articles = strict_json(directory/'articles.json')
    ids = job.get('selection_ids') or [a['article_id'] for a in articles]
    packet = prepare(articles, ids=ids)
    selected = {a['article_id']: a for a in articles}
    message = chat_message(packet)
    if (job.get('version') != VERSION or job.get('key') != directory.name or
            job.get('key') != digest(dict(version=VERSION, message=message)) or
            job.get('members') != [article_key(normalize(selected[i])) for i in ids] or
            (directory/'message.txt').read_text(encoding='utf-8') != message):
        raise ValueError('Batch journal/input identity mismatch')
    if job['state'] != 'validated':
        return job, None
    raw = (directory/'response.txt').read_text(encoding='utf-8')
    response = parse_response(raw)
    if digest(response) != job['response_sha256']:
        raise ValueError('Cached response changed')
    report = import_response(packet, response, articles,
        'ChatGPT web - model not independently verified', ids=ids)
    for row in report['rows']:
        original_hash = row['article_sha256']
        row['article_sha256'] = digest(normalize(selected[row['article_id']]))
        if original_hash != row['article_sha256']:
            row['original_article_sha256'] = original_hash
    report.update(provider='chatgpt_browser_dom', transport=VERSION, browser_url=job['url'])
    return job, report


def seed_pilot(cache, pilot_cache, articles, index):
    """Adopt verified old pilot replies, preserving original prompt/source/response."""
    pilot_cache = own_path(pilot_cache)
    if pilot_cache == cache or not pilot_cache.exists():
        raise ValueError('Choose an existing, separate pilot cache')
    for path in sorted(pilot_cache.glob('*/job.json')):
        old = strict_json(path)
        if old.get('version') != 'measures-web-scraper-1' or old.get('state') != 'validated':
            continue
        original = path.parent
        packet = strict_json(original/'articles_packet.json')
        raw = (original/'response.txt').read_text(encoding='utf-8')
        response = parse_response(raw)
        if old['response_sha256'] != digest(response):
            raise ValueError('Pilot response changed')
        ids = [a['article']['article_id'] for a in packet['articles']]
        # Full source snapshot must still match the original pilot; otherwise refuse adoption.
        import_response(packet, response, articles, ids=ids)
        message = chat_message(packet)
        if (original/'message.txt').read_text(encoding='utf-8') != message:
            raise ValueError('Pilot prompt changed')
        normalized = {a['article_id']: normalize(a) for a in articles}
        members = [article_key(normalized[i]) for i in ids]
        if any(key in index['articles'] for key in members):
            # Never replace an existing/uncertain claim with a seed.
            continue
        key = digest(dict(version=VERSION, message=message))
        directory = cache/'jobs'/key
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory/'articles.json', articles)
        (directory/'message.txt').write_text(message, encoding='utf-8')
        (directory/'response.txt').write_text(raw, encoding='utf-8')
        atomic_json(directory/'job.json', dict(version=VERSION, key=key, members=members,
            selection_ids=ids, state='validated', url=old['url'], response_sha256=digest(response),
            origin='validated_pilot_seed', original_cache=str(original), history=old['history']))
        validate_batch(directory)
        index['articles'].update({member: key for member in members})
        atomic_json(cache/'index.json', index)


def load_index(cache):
    if not (cache/'index.json').exists():
        # An existing sent job without an index is not a clean first run.
        if (cache/'jobs').exists() and any((cache/'jobs').iterdir()):
            raise ValueError('Index missing beside existing jobs; inspect cache, do not resend')
        return dict(version=VERSION, articles={})
    index = strict_json(cache/'index.json')
    if index.get('version') != VERSION or not isinstance(index.get('articles'), dict):
        raise ValueError('Invalid cache index')
    for key, job_key in index['articles'].items():
        if not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(job_key, str) or not re.fullmatch('[0-9a-f]{64}', job_key):
            raise ValueError('Invalid cache reference')
    return index


def inspect_articles(articles, cache, index, max_chars):
    if not isinstance(articles, list):
        raise ValueError('Input must be a JSON array of articles')
    identifiers = [a.get('article_id') for a in articles if isinstance(a, dict)]
    valid_ids = [i for i in identifiers if isinstance(i, str) and i.strip()]
    if len(valid_ids) != len(set(valid_ids)):
        raise ValueError('Duplicate article IDs in input; nothing sent')
    entries, batches = [], {}
    for position, article in enumerate(articles):
        entry = dict(position=position, article_id=article.get('article_id') if isinstance(article, dict) else None)
        try:
            normalized = normalize(article)
            if len(chat_message(packet_for([normalized]))) > max_chars:
                raise ValueError('Article exceeds maximum prompt length; not truncated')
            key = article_key(normalized)
            entry.update(key=key, article=normalized, article_sha256=digest(normalized), state='pending')
            if key in index['articles']:
                job_key = index['articles'][key]
                if job_key not in batches:
                    batches[job_key] = validate_batch(cache/'jobs'/job_key)
                job, report = batches[job_key]
                if key not in job['members']:
                    raise ValueError('Cache index points to unrelated batch')
                entry['job_key'] = job_key
                if report is None:
                    entry.update(state='blocked', error=f"Existing batch state: {job['state']}; no automatic resend")
                else:
                    rows = [r for r in report['rows'] if r['article_id'] == normalized['article_id']]
                    if len(rows) != 1 or rows[0]['article_sha256'] != digest(normalized):
                        raise ValueError('Cached article identity mismatch')
                    entry.update(state='validated', row=rows[0], cache_hit=True,
                                 browser_url=report['browser_url'])
        except (ValueError, KeyError, TypeError, OSError) as error:
            # Invalid cache must never be treated as a cache miss.
            entry.update(state='blocked' if entry.get('key') in index['articles'] else 'invalid', error=str(error))
        entries.append(entry)
    return entries


def export_report(entries, output, run_id, source, source_hash, processed, error=None, planned=False):
    counts = {state: sum(e['state'] == state for e in entries) for state in ('validated', 'pending', 'blocked', 'invalid')}
    counts.update(total=len(entries), new_processed=processed,
                  cached=sum(e['state'] == 'validated' and e.get('cache_hit', False) for e in entries))
    state = ('planned' if planned else 'stopped' if error or counts['blocked'] else
             'partial' if counts['pending'] or counts['invalid'] else 'complete')
    report = dict(schema_version=VERSION, run_id=run_id, state=state,
        data_mode='observed_press_unverified', source_path=str(source), source_sha256=source_hash,
        counts=counts, error=error, approved_suggestions=0,
        warning='Sugestii AI neaprobate, cu citate validate; fără asociere OSM sau modificare de scor.',
        articles=[{k: deepcopy(v) for k, v in e.items() if k not in ('article', 'row')} for e in entries],
        rows=[dict(deepcopy(e['row']), browser_url=e['browser_url'], cache_hit=e['cache_hit'])
              for e in entries if e['state'] == 'validated'])
    if planned:
        atomic_json(output/'plan.json', report)
    else:
        # One atomic snapshot contains coverage + rows; readers need no multi-file transaction.
        atomic_json(output/'chatgpt_suggestions.json', report)
    return report


def run_pipeline(*, source=SOURCE, cache=CACHE, output=OUTPUT, batch_size=3, limit=0,
                 max_chars=40000, plan=False, channel=None, headless=False, manual_wait=0,
                 timeout=180, transport=None, seed_pilot_cache=None):
    if not 1 <= batch_size <= 5 or limit < 0 or max_chars < 8000:
        raise ValueError('batch_size=1..5, limit>=0, max_chars>=8000 required')
    if headless and manual_wait:
        raise ValueError('Manual verification requires a visible browser')
    source, cache, output = Path(source).resolve(), own_path(cache), own_path(output)
    if cache == output or cache.is_relative_to(output) or output.is_relative_to(cache):
        raise ValueError('Cache and output must be separate directories')
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    with exclusive(cache/'worker.lock'):
        articles = strict_json(source)
        index = load_index(cache)
        if seed_pilot_cache and not plan and not index['articles']:
            seed_pilot(cache, seed_pilot_cache, articles, index)
        entries = inspect_articles(articles, cache, index, max_chars)
        run_id, source_hash, processed = str(uuid.uuid4()), digest(articles), 0
        def publish(error=None):
            return export_report(entries, output, run_id, source, source_hash, processed, error, planned=plan)
        if plan:
            return publish()
        publish()
        if any(e['state'] == 'blocked' for e in entries):
            return publish('Existing unresolved cache job; inspect before sending new articles')
        pending = [e for e in entries if e['state'] == 'pending']
        if limit:
            pending = pending[:limit]
        while pending:
            batch = pending[:batch_size]
            while len(batch) > 1 and len(chat_message(packet_for([e['article'] for e in batch]))) > max_chars:
                batch = batch[:-1]
            selected = [e['article'] for e in batch]
            message = chat_message(packet_for(selected))
            job_key = digest(dict(version=VERSION, message=message))
            directory = cache/'jobs'/job_key
            directory.mkdir(parents=True, exist_ok=True)
            job = dict(version=VERSION, key=job_key, members=[e['key'] for e in batch], state='prepared', history=[])
            def record(state, **fields):
                job.update(state=state, **fields)
                job['history'].append(dict(state=state, at=datetime.now(timezone.utc).isoformat()))
                atomic_json(directory/'job.json', job)
            atomic_json(directory/'articles.json', selected)
            (directory/'message.txt').write_text(message, encoding='utf-8')
            record('prepared')
            # Persist all claims BEFORE any send; a crash later cannot cause automatic resubmission.
            index['articles'].update({e['key']: job_key for e in batch})
            atomic_json(cache/'index.json', index)
            try:
                raw, url = (transport or browser_transport)(message, record, directory,
                    headless=headless, timeout=timeout, channel=channel, manual_wait=manual_wait)
                (directory/'response.txt').write_text(raw, encoding='utf-8')
                response = parse_response(raw)
                import_response(packet_for(selected), response, selected,
                    ids=[a['article_id'] for a in selected])
                record('validated', url=url, response_sha256=digest(response))
                _, checked = validate_batch(directory)
                indexed_rows = {r['article_id']: r for r in checked['rows']}
                for entry in batch:
                    entry.update(state='validated', row=indexed_rows[entry['article_id']], cache_hit=False,
                                 browser_url=url, job_key=job_key)
                processed += len(batch)
                pending = pending[len(batch):]
                publish()
                print(json.dumps(dict(status='batch_validated', processed=processed, remaining=len(pending))),
                      file=sys.stderr, flush=True)
            except (Exception, KeyboardInterrupt) as error:
                record('stopped', last_phase=job['state'], error=str(error)[:1000])
                for entry in batch:
                    entry.update(state='blocked', job_key=job_key, error=str(error)[:1000])
                return publish(str(error)[:1000] or 'Interrupted; no automatic resend')
        return publish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=SOURCE)
    parser.add_argument('--cache', type=Path, default=CACHE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--batch-size', type=int, default=3)
    parser.add_argument('--limit', type=int, default=0, help='Maximum new/changed articles this run; 0=all')
    parser.add_argument('--max-chars', type=int, default=40000)
    parser.add_argument('--plan', action='store_true', help='Inspect source/cache, without opening a browser or sending')
    parser.add_argument('--seed-pilot-cache', type=Path, help='Adopt a validated three-article pilot cache on the first real run')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--channel', choices=['chrome', 'msedge'])
    parser.add_argument('--manual-wait', type=int, default=0)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not 0 <= args.manual_wait <= 1800 or not 15 <= args.timeout <= 600:
        parser.error('manual-wait=0..1800 and timeout=15..600 required')
    try:
        report = run_pipeline(source=args.input, cache=args.cache, output=args.output,
            batch_size=args.batch_size, limit=args.limit, max_chars=args.max_chars, plan=args.plan,
            channel=args.channel, headless=args.headless, manual_wait=args.manual_wait, timeout=args.timeout,
            seed_pilot_cache=args.seed_pilot_cache)
        print(json.dumps(dict(state=report['state'], run_id=report['run_id'], **report['counts']), ensure_ascii=True))
        return 0 if report['state'] in ('complete', 'planned') else 2 if report['state'] == 'stopped' else 3
    except Exception as error:
        print(json.dumps(dict(state='stopped', error=str(error)), ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
