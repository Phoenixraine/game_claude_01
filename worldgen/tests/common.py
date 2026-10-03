import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import generate  # noqa: E402

_CACHE = {}


def district(seed=1):
    """Builds (and caches) a district once per seed for the whole test run."""
    if seed not in _CACHE:
        _CACHE[seed] = generate.build(seed)
    return _CACHE[seed]


def schema():
    with open(os.path.join(ROOT, "schema.json"), encoding="utf-8") as f:
        return json.load(f)
