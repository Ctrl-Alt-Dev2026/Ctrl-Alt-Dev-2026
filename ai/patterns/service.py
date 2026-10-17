from __future__ import annotations

import json
import math
from pathlib import Path
import re

from .corpus import SCHEMA, digest
from .engine import discover

MODULE = Path(__file__).resolve().parent
DEFAULT_DATA = MODULE.parents[1] / 'false_data'


class PatternService:
    def __init__(self, bundle_path=MODULE / 'data' / 'bundle.json', data_directory=DEFAULT_DATA):
        self.bundle_path = Path(bundle_path)
        self.data_directory = Path(data_directory)

    def load(self):
        try:
            return self._load()
        except (TypeError, AttributeError, KeyError, IndexError) as exc:
            raise ValueError('Malformed prepared pattern bundle. Prepare it again.') from exc

    def _load(self):
        bundle = json.loads(self.bundle_path.read_text(encoding='utf-8'))
        if bundle.get('schema') != SCHEMA or bundle.get('synthetic') is not True:
            raise ValueError('Unsupported or non-synthetic pattern bundle')
        if bundle.get('input_sha256') != digest(self.data_directory):
            raise ValueError('Stale prepared vectors: source files changed. Prepare the bundle again.')
        ids = [e['id'] for e in bundle['events']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate event IDs in prepared bundle')
        dimensions = bundle['model']['dimensions']
        if type(dimensions) is not int or not 1 <= dimensions <= 4096:
            raise ValueError('Invalid vector dimensions')
        for key in ('vectors', 'source_vectors'):
            if not isinstance(bundle[key], dict):
                raise ValueError('Invalid vector mapping')
            if set(bundle[key]) != set(ids):
                raise ValueError('Vector IDs do not match corpus')
            for vector in bundle[key].values():
                if not isinstance(vector, list) or len(vector) != dimensions or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in vector
                ):
                    raise ValueError('Invalid vector shape or value')
        return bundle

    def validate_demo(self, path):
        """HTTP must not silently serve a stale export after corpus regeneration."""
        bundle = self.load()
        html = Path(path).read_text(encoding='utf-8')
        match = re.search(r'<script id="pattern-data" type="application/json">(.*?)</script>', html, re.DOTALL)
        if match is None or json.loads(match.group(1)) != bundle:
            raise ValueError('Stale or missing HTML data: run python -m ai.patterns.export.')

    def discover(self, **kwargs):
        return discover(self.load(), **kwargs)
