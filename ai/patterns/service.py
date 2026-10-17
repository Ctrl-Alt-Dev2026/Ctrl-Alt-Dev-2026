from __future__ import annotations

import json
import math
from pathlib import Path

from .corpus import SCHEMA, digest
from .engine import discover

MODULE = Path(__file__).resolve().parent
DEFAULT_DATA = MODULE.parents[1] / 'false_data'


class PatternService:
    def __init__(self, bundle_path=MODULE / 'data' / 'bundle.json', data_directory=DEFAULT_DATA):
        self.bundle_path = Path(bundle_path)
        self.data_directory = Path(data_directory)

    def load(self):
        bundle = json.loads(self.bundle_path.read_text(encoding='utf-8'))
        if bundle.get('schema') != SCHEMA or bundle.get('synthetic') is not True:
            raise ValueError('Unsupported or non-synthetic pattern bundle')
        if bundle.get('input_sha256') != digest(self.data_directory):
            raise ValueError('Stale prepared vectors: source files changed. Prepare the bundle again.')
        ids = [e['id'] for e in bundle['events']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate event IDs in prepared bundle')
        for key in ('vectors', 'source_vectors'):
            if set(bundle[key]) != set(ids):
                raise ValueError('Vector IDs do not match corpus')
            for vector in bundle[key].values():
                if len(vector) != bundle['model']['dimensions'] or any(not math.isfinite(v) for v in vector):
                    raise ValueError('Invalid vector shape or value')
        return bundle

    def discover(self, **kwargs):
        return discover(self.load(), **kwargs)
