"""Serve an isolated compiled frontend with the explicit scenario data override."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import urllib.parse

from risk.inspect import ROOT, read
from risk.frontend_scenario import validate


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, app_directory, data_directory, **kwargs):
        self.app_directory = app_directory
        self.data_directory = data_directory
        super().__init__(*args, directory=app_directory, **kwargs)

    def do_GET(self):
        self.select_directory()
        super().do_GET()

    def do_HEAD(self):
        self.select_directory()
        super().do_HEAD()

    def select_directory(self):
        path = urllib.parse.urlsplit(self.path).path
        self.directory = self.data_directory if path == '/data' or path.startswith('/data/') else self.app_directory

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4201)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'risk/output/frontend-scenario')
    parser.add_argument('--app-output', type=Path, default=ROOT / 'risk/output/frontend-app-mock')
    args = parser.parse_args()
    output = args.app_output.resolve()
    if not output.is_relative_to((ROOT / 'risk/output').resolve()):
        parser.error('Compiled frontend output must stay inside risk/output/')
    names = ['manifest.json', 'crossings.geojson', 'hotspots.json', 'accidents.json']
    bundle = {name: read(args.dataset / 'data' / name) for name in names}
    validate(bundle)
    if read(args.dataset / 'data/scenario_provenance.json')['data_mode'] != 'simulation_mixed_sources':
        parser.error('Not an explicitly labeled mixed-source scenario')
    browser = output / 'browser'
    if not output.exists():
        cli = ROOT / 'web/node_modules/@angular/cli/bin/ng.js'
        if not cli.exists():
            parser.error('Install frontend dependencies with npm ci in web/ first')
        print('Building existing frontend into risk/output only...', flush=True)
        subprocess.run(['node', str(cli), 'build', '--configuration', 'development,mock', '--output-path', str(output)],
                       cwd=ROOT / 'web', check=True)
    if not (browser / 'index.html').is_file():
        parser.error('Compiled index.html missing; choose a new --app-output directory to build again')
    handler = functools.partial(Handler, app_directory=str(browser), data_directory=str(args.dataset.resolve()))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    print(f'SCENARIO preview: http://127.0.0.1:{args.port}/ | Ctrl+C to stop', flush=True)
    print('Real OSM infrastructure + hypothetical demo accidents. Frontend sources unchanged.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
