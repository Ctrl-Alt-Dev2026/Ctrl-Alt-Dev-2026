"""Durable jobs for assistant-driven browser actions; no private HTTP APIs."""
import argparse
import hashlib
import json
from pathlib import Path

from measures.chatgpt_exchange import (ROOT, SOURCE, import_response, output_path,
                                      prepare, prompt, response_schema, strict_json, chat_message)
from measures.storage import atomic_json


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create_job(directory):
    directory = output_path(directory)
    packet = prepare(strict_json(SOURCE))
    directory.mkdir(parents=True)
    atomic_json(directory/'articles_packet.json', packet)
    atomic_json(directory/'response_schema.json', response_schema(packet))
    (directory/'PROMPT.txt').write_text(prompt(packet), encoding='utf-8')
    (directory/'CHAT_MESSAGE.txt').write_text(chat_message(packet), encoding='utf-8')
    job = dict(schema_version='measures-browser-job-1', destination='https://chatgpt.com/',
               transport='assistant_browser_ui_or_page_exposed_webmcp', state='prepared',
               packet_id=packet['packet_id'], conversation_id=None,
               files={n: file_hash(directory/n) for n in ('articles_packet.json', 'response_schema.json', 'PROMPT.txt', 'CHAT_MESSAGE.txt')},
               history=['prepared'], automatically_approved=False)
    atomic_json(directory/'job.json', job)
    return job


def load_job(directory):
    directory = Path(directory).resolve()
    if not directory.is_relative_to((ROOT/'measures/output').resolve()):
        raise ValueError('Jobs must stay in measures/output')
    job = strict_json(directory/'job.json')
    if job.get('schema_version') != 'measures-browser-job-1' or job.get('destination') != 'https://chatgpt.com/':
        raise ValueError('Unexpected job type or destination')
    if set(job['files']) != {'articles_packet.json', 'response_schema.json', 'PROMPT.txt', 'CHAT_MESSAGE.txt'}:
        raise ValueError('Unexpected job files')
    if any(file_hash(directory/n) != h for n, h in job['files'].items()):
        raise ValueError('Job input changed')
    if strict_json(directory/'articles_packet.json') != prepare(strict_json(SOURCE)):
        raise ValueError('Source changed; do not send a stale job')
    return directory, job


def mark_job(directory, state, conversation_id=None):
    directory, job = load_job(directory)
    expected = {'dispatch_started': 'prepared', 'sent': 'dispatch_started'}
    if state not in expected or job['state'] != expected[state]:
        raise ValueError('Unsafe/repeated transition; never automatically retry a dispatched send')
    if state == 'sent' and (not isinstance(conversation_id, str) or not conversation_id.strip()):
        raise ValueError('Record the conversation ID returned by the browser')
    job['state'] = state
    job['conversation_id'] = conversation_id
    job['history'].append(state)
    atomic_json(directory/'job.json', job)
    return job


def finish_job(directory, response_path, model_label='ChatGPT web — model neprecizat de operator'):
    directory, job = load_job(directory)
    if job['state'] != 'sent':
        raise ValueError('Expected a recorded send; incomplete/duplicate completion refused')
    response = strict_json(response_path)
    report = import_response(strict_json(directory/'articles_packet.json'), response, strict_json(SOURCE), model_label)
    report['browser_conversation_id'] = job['conversation_id']
    atomic_json(directory/'chatgpt_suggestions.json', report)
    atomic_json(directory/'original_response.json', response)
    job['state'] = 'validated'
    job['response_sha256'] = file_hash(directory/'original_response.json')
    job['history'].append('validated')
    atomic_json(directory/'job.json', job)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--output', type=Path, required=True)
    for action in ('status', 'mark', 'finish'):
        p = sub.add_parser(action)
        p.add_argument('--job', type=Path, required=True)
        if action == 'mark':
            p.add_argument('--state', choices=['dispatch_started', 'sent'], required=True)
            p.add_argument('--conversation-id')
        if action == 'finish':
            p.add_argument('--response', type=Path, required=True)
            p.add_argument('--model-label', default='ChatGPT web — model neprecizat de operator')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            result = create_job(args.output)
        elif args.action == 'status':
            result = load_job(args.job)[1]
        elif args.action == 'mark':
            result = mark_job(args.job, args.state, args.conversation_id)
        else:
            result = finish_job(args.job, args.response, args.model_label)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'Refused: {error}\n')


if __name__ == '__main__':
    main()
