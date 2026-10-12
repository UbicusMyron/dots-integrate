"""Trusted synthetic example; no network, credentials or external writes."""
import json
import sys

data = json.load(sys.stdin)
values = data['values']
if not isinstance(values, list) or not all(type(v) in (int, float) for v in values):
    raise ValueError('Expected numeric values')
json.dump({'total': sum(values)}, sys.stdout, allow_nan=False)
