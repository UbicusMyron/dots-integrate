"""Strict JSON and deterministic, non-secret control errors (stdlib only)."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class IntakeError(Exception):
    def __init__(self, code, message=None):
        self.code = code
        self.message = message or code.replace('_', ' ').capitalize()
        super().__init__(self.message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def byte_digest(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _constant(_):
    raise ValueError('Non-finite JSON number')


def parse_json(data):
    value = json.loads(data, object_pairs_hook=_pairs, parse_constant=_constant)
    canonical(value)  # Reject overflowed floats and invalid Unicode too.
    return value


def read_json(path, code='STATE_INVALID'):
    try:
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('Not a regular file')
        return parse_json(path.read_bytes())
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise IntakeError(code) from None


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    """Caller holds the control lock. fsync data and containing directory."""
    path = Path(path)
    raw = canonical(value) + b'\n'
    if path.is_symlink():
        raise IntakeError('UNSAFE_PATH')
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
