"""Verify data actually served by the separate local Angular preview."""
import argparse
import json
import urllib.request

from risk.frontend_scenario import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4201)
    args = parser.parse_args()
    base = f'http://127.0.0.1:{args.port}'
    names = ['manifest.json', 'crossings.geojson', 'hotspots.json', 'accidents.json',
             'measures.json', 'cameras.json', 'scenario_provenance.json']
    bundle = {}
    for name in names:
        with urllib.request.urlopen(base + '/data/' + name, timeout=15) as response:
            bundle[name] = json.load(response)
    validate(bundle)
    if bundle['scenario_provenance.json']['data_mode'] != 'simulation_mixed_sources':
        raise ValueError('Preview does not serve the explicitly mixed-source scenario')
    with urllib.request.urlopen(base, timeout=15) as response:
        if response.status != 200:
            raise ValueError('Frontend document not available')
    print(json.dumps(dict(status='ok', frontend=base,
        real_crossings=len(bundle['crossings.geojson']['features']),
        demo_events=len(bundle['accidents.json']),
        scores=[h['scor'] for h in bundle['hotspots.json']],
        data_mode='simulation_mixed_sources', verified_events=0), indent=2))


if __name__ == '__main__':
    main()
