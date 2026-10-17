"""Standalone ChatGPT UI worker. No AI APIs, Codex, stealth or automatic resend."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time

from measures.chatgpt_exchange import ROOT, SOURCE, chat_message, import_response, prepare, strict_json
from measures.storage import atomic_json, digest

VERSION = 'measures-web-scraper-1'
CACHE = ROOT/'measures/cache/web-scraper'
OUTPUT = ROOT/'measures/output/web-scraper'
URL = 'https://chatgpt.com/'


class BrowserBlocked(RuntimeError):
    pass


def own_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT/'measures').resolve()) or path == (ROOT/'measures').resolve():
        raise ValueError('Worker paths must stay below measures/')
    return path


@contextmanager
def exclusive(path):
    """One worker/profile at a time; stale locks require operator inspection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise BrowserBlocked(f'Worker locked: inspect {path}; no automatic retry') from None
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(dict(pid=os.getpid(), created=datetime.now(timezone.utc).isoformat()), file)
        yield
    finally:
        path.unlink()


def parse_response(text):
    # Markdown fences are presentation only. No substring extraction or JSON repair.
    text = text.strip()
    fence = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, re.S)
    if fence:
        text = fence.group(1)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f'Invalid JSON constant: {value}')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def validate_text(text, packet, articles):
    response = parse_response(text)
    report = import_response(packet, response, articles, 'ChatGPT web - model not independently verified')
    report['provider'] = 'chatgpt_browser_dom'
    report['transport'] = VERSION
    return response, report


def visible(locator):
    return locator.count() > 0 and locator.first.is_visible()


def check_blocker(page):
    # Read rendered text only, never cookies, storage or network responses.
    text = page.locator('body').inner_text(timeout=5000).lower()
    phrases = ('verify you are human', 'verifying you are human', 'checking your browser',
               'unusual activity', 'too many requests', 'you have reached your',
               "you've reached your", 'usage limit', 'verify to continue',
               'verifică dacă ești om', 'suspicious activity', 'verifying...')
    challenge = page.locator('iframe[src*="challenges.cloudflare.com"]')
    if any(phrase in text for phrase in phrases) or visible(challenge):
        raise BrowserBlocked('Security check or usage limit displayed; operator action required')
    dialogs = page.get_by_role('dialog')
    if visible(dialogs) and re.search(r'log in|sign in|autentific', dialogs.first.inner_text(), re.I):
        raise BrowserBlocked('Login dialog displayed; guest run stopped')


def composer(page):
    # Prefer semantic controls; fail on ambiguity instead of choosing an arbitrary field.
    for locator in (page.get_by_role('textbox', name='Chat with ChatGPT', exact=True),
                    page.get_by_role('textbox', name=re.compile(r'Ask anything|Message ChatGPT', re.I)),
                    page.locator('#prompt-textarea'), page.locator('#mobile-composer-prompt')):
        if locator.count() == 1 and locator.is_visible():
            return locator
    raise BrowserBlocked('Composer unavailable; inspect page.png (login or changed page)')


def assistant_text(page):
    standard = page.locator('[data-message-author-role="assistant"]')
    if standard.count():
        return standard.last.inner_text().strip()
    # Alternate rendered layout observed during the guest pilot.
    region = page.get_by_role('region', name='DIL content', exact=True)
    if region.count() == 1:
        return region.inner_text().strip()
    return ''


def completed(page):
    stop = page.get_by_role('button', name=re.compile(r'^Stop(?: generating| response)?$', re.I))
    if visible(stop):
        return False
    return (visible(page.get_by_role('button', name='Copy response', exact=True)) or
            visible(page.get_by_role('button', name='Copy', exact=True)))


def wait_for_composer(page, record, directory, manual_wait=0):
    """Observe only while the human handles the challenge; never click it."""
    deadline = time.monotonic()+manual_wait
    announced = False
    while True:
        try:
            check_blocker(page)
            return composer(page)
        except BrowserBlocked:
            if not manual_wait or time.monotonic() >= deadline:
                raise
            if not announced:
                record('waiting_for_user', url=page.url)
                page.screenshot(path=str(directory/'manual-check.png'), timeout=5000)
                print(json.dumps(dict(status='waiting_for_user', seconds=manual_wait,
                    message='Resolve the check in the visible browser. Do not type or send articles; the worker continues automatically.')),
                    file=sys.stderr, flush=True)
                announced = True
            if page.is_closed():
                raise BrowserBlocked('Browser closed during manual verification')
            page.wait_for_timeout(1000)


def browser_transport(message, record, directory, *, headless=False, timeout=180, channel=None, manual_wait=0):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise BrowserBlocked('Install measures/requirements-web.txt in an isolated environment first') from None
    # Fresh context: no existing account/profile is imported or persisted.
    with sync_playwright() as playwright:
        options = dict(headless=headless)
        if channel:
            options['channel'] = channel
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(locale='en-US')
        page = context.new_page()
        page.set_default_timeout(15000)
        try:
            page.goto(URL, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(1500)
            editor = wait_for_composer(page, record, directory, manual_wait)
            existing = editor.input_value() if editor.evaluate('(e) => e.tagName') == 'TEXTAREA' else editor.inner_text()
            if existing.strip() or assistant_text(page):
                raise BrowserBlocked('Expected a new conversation and an empty composer')
            editor.fill(message)
            check_blocker(page)
            send = page.get_by_role('button', name='Send message', exact=True)
            if send.count() != 1:
                raise BrowserBlocked('Send button unavailable or ambiguous')
            # Wait for normal readiness, not an authentication assumption based on an empty draft.
            from playwright.sync_api import expect
            expect(send).to_be_enabled(timeout=15000)
            record('dispatch_started', url=page.url)
            send.click(timeout=15000)  # Exactly one attempt, including timeout ambiguity.
            record('waiting', url=page.url)
            deadline, previous, repeats = time.monotonic()+timeout, '', 0
            while time.monotonic() < deadline:
                check_blocker(page)
                text = assistant_text(page)
                repeats = repeats+1 if text and text == previous else 0
                if text and repeats >= 2 and completed(page):
                    record('received', url=page.url)
                    return text, page.url
                previous = text
                page.wait_for_timeout(1000)
            raise BrowserBlocked('Timed out after send; no resend. Inspect saved journal and page.png')
        finally:
            try:
                page.screenshot(path=str(directory/'page.png'), full_page=False, timeout=5000)
            except Exception:
                pass
            context.close()
            browser.close()


def run_worker(*, cache=CACHE, output=OUTPUT, headless=False, timeout=180, channel=None, manual_wait=0,
               transport=None):
    if manual_wait and headless:
        raise ValueError('Manual verification requires a visible browser; omit --headless')
    cache, output = own_path(cache), own_path(output)
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    with exclusive(cache/'worker.lock'):
        articles = strict_json(SOURCE)
        packet = prepare(articles)
        message = chat_message(packet)
        key = digest(dict(version=VERSION, packet=packet, prompt=message))
        directory = cache/key
        directory.mkdir(exist_ok=True)
        journal_path = directory/'job.json'
        job = strict_json(journal_path) if journal_path.exists() else dict(
            version=VERSION, key=key, packet_id=packet['packet_id'], state='prepared', history=[])
        if job.get('key') != key or job.get('version') != VERSION:
            raise ValueError('Cache identity mismatch')
        atomic_json(output/'status.json', dict(state='starting', key=key, packet_id=packet['packet_id']))
        if job['state'] == 'validated':
            # Revalidate against original articles on every cache hit.
            raw = (directory/'response.txt').read_text(encoding='utf-8')
            _, report = validate_text(raw, packet, articles)
            if digest(parse_response(raw)) != job['response_sha256']:
                raise ValueError('Cached response changed')
            report.update(browser_url=job['url'], cache_hit=True)
            atomic_json(output/'chatgpt_suggestions.json', report)
            atomic_json(output/'status.json', dict(state='validated', key=key, packet_id=packet['packet_id'], cache_hit=True))
            return report
        if job['state'] != 'prepared':
            atomic_json(output/'status.json', dict(state='stopped', key=key,
                packet_id=packet['packet_id'], error='Existing incomplete/stopped job; no automatic resend'))
            raise BrowserBlocked(f"Previous state {job['state']}; no resend. Inspect {journal_path}")
        def record(state, **fields):
            job.update(state=state, **fields)
            job['history'].append(dict(state=state, at=datetime.now(timezone.utc).isoformat()))
            atomic_json(journal_path, job)
        record('prepared')
        atomic_json(directory/'articles_packet.json', packet)
        (directory/'message.txt').write_text(message, encoding='utf-8')
        try:
            raw, url = (transport or browser_transport)(message, record, directory,
                headless=headless, timeout=timeout, channel=channel, manual_wait=manual_wait)
            (directory/'response.txt').write_text(raw, encoding='utf-8')
            response, report = validate_text(raw, packet, articles)
            record('validated', url=url, response_sha256=digest(response))
            report.update(browser_url=url, cache_hit=False)
            atomic_json(output/'chatgpt_suggestions.json', report)
            atomic_json(output/'status.json', dict(state='validated', key=key, packet_id=packet['packet_id'], cache_hit=False))
            return report
        except Exception as error:
            record('stopped', last_phase=job['state'], error=str(error)[:1000])
            atomic_json(output/'status.json', dict(state='stopped', key=key,
                packet_id=packet['packet_id'], error=str(error)[:1000]))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--headless', action='store_true', help='Run without a visible browser window')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--manual-wait', type=int, default=0,
                        help='Seconds to wait for the human to clear a check before sending (visible browser only)')
    parser.add_argument('--channel', choices=['chrome', 'msedge'], help='Use an installed browser instead of bundled Chromium')
    parser.add_argument('--cache', type=Path, default=CACHE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if not 15 <= args.timeout <= 600:
        parser.error('--timeout must be between 15 and 600 seconds')
    if not 0 <= args.manual_wait <= 1800 or (args.manual_wait and args.headless):
        parser.error('--manual-wait must be 0..1800 and requires a visible browser')
    try:
        report = run_worker(cache=args.cache, output=args.output, headless=args.headless,
                            timeout=args.timeout, channel=args.channel, manual_wait=args.manual_wait)
        print(json.dumps(dict(status='validated', cache_hit=report['cache_hit'], articles=len(report['rows']),
            suggestions=sum(len(r['suggestions']) for r in report['rows']),
            approved=report['approved_suggestions'], output=str(own_path(args.output)/'chatgpt_suggestions.json'))))
    except Exception as error:
        print(json.dumps(dict(status='stopped', error=str(error)), ensure_ascii=True), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
