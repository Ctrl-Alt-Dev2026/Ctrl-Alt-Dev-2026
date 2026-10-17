"""Produce a self-contained, offline HTML demo; no model/server required to view."""
import argparse
import json
from pathlib import Path

from .service import MODULE, PatternService


def export(output, bundle_path=MODULE / 'data' / 'bundle.json', data_directory=None):
    args = {} if data_directory is None else {'data_directory': data_directory}
    bundle = PatternService(bundle_path, **args).load()
    source_directory = PatternService(bundle_path, **args).data_directory
    if Path(output).resolve().is_relative_to(source_directory.resolve()):
        raise ValueError('HTML output must not be written into the source fixture directory')
    static = MODULE / 'static'
    html = (static / 'template.html').read_text(encoding='utf-8')
    parts = {'STYLE': (static / 'style.css').read_text(encoding='utf-8'),
             'ENGINE': (static / 'engine.js').read_text(encoding='utf-8'),
             'APP': (static / 'app.js').read_text(encoding='utf-8'),
             'BUNDLE': json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')}
    for key, text in parts.items():
        html = html.replace('@@' + key + '@@', text)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    print(f'Offline demo: {output} ({output.stat().st_size:,} bytes)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=MODULE / 'static' / 'index.html')
    args = parser.parse_args()
    export(args.output)
