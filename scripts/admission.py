"""Pure, fail-closed allowlist decision. Does not establish input trust."""
from datetime import datetime
import re

IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]*')
DIGEST = re.compile(r'[a-f0-9]{64}')
TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})', re.ASCII)
BINDING_FIELDS = ('tool_id', 'operation', 'artifact_digest', 'runtime_digest', 'context_digest', 'suite_digest')
ENTRY_FIELDS = set(BINDING_FIELDS) | {'validation_id', 'validated_at', 'evidence_ref', 'evidence_digest'}


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def valid_binding(value):
    return (isinstance(value, dict) and set(value) == set(BINDING_FIELDS)
            and all(matches(IDENTIFIER, value[k]) for k in BINDING_FIELDS[:2])
            and all(matches(DIGEST, value[k]) for k in BINDING_FIELDS[2:]))


def valid_time(value):
    if not matches(TIMESTAMP, value):
        return False
    try:
        # fromisoformat normalizes offsets such as +01:99; explicitly reject them.
        if value[-1:] not in ('z', 'Z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            return False
        return datetime.fromisoformat(value.upper().replace('Z', '+00:00')).utcoffset() is not None
    except ValueError:
        return False


def binding_key(binding):
    return tuple(binding[k] for k in BINDING_FIELDS)


def valid_registry(registry):
    if not isinstance(registry, dict) or set(registry) != {'schema_version', 'revision', 'entries'}:
        return False
    if type(registry['schema_version']) is not int or registry['schema_version'] != 1:
        return False
    if type(registry['revision']) is not int or registry['revision'] < 0 or not isinstance(registry['entries'], list):
        return False
    seen = set()
    for entry in registry['entries']:
        if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
            return False
        binding = {k: entry[k] for k in BINDING_FIELDS}
        if not valid_binding(binding) or not matches(IDENTIFIER, entry['validation_id']):
            return False
        if not valid_time(entry['validated_at']) or not matches(DIGEST, entry['evidence_digest']):
            return False
        if not isinstance(entry['evidence_ref'], str) or not entry['evidence_ref']:
            return False
        key = binding_key(binding)
        if key in seen:
            return False
        seen.add(key)
    return True


def evaluate_admission(binding, registry):
    result = dict(allowed=False, code='INVALID_BINDING', validation_id=None)
    if not valid_binding(binding):
        return result
    if registry is None:
        return dict(result, code='REGISTRY_UNAVAILABLE')
    if not valid_registry(registry):
        return dict(result, code='REGISTRY_INVALID')
    candidates = [e for e in registry['entries'] if e['tool_id'] == binding['tool_id'] and e['operation'] == binding['operation']]
    for entry in candidates:
        if binding_key(entry) == binding_key(binding):
            return dict(allowed=True, code='ADMITTED', validation_id=entry['validation_id'])
    return dict(result, code='BINDING_MISMATCH' if candidates else 'NOT_ALLOWLISTED')
