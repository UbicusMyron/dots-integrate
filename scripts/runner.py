"""Trusted synthetic Python adapter. No network or same-UID sandbox guarantee."""
import importlib.metadata
import os
from pathlib import Path, PurePosixPath
import platform
import signal
import subprocess
import sys
import tempfile
import time

from scripts.admission import IDENTIFIER, matches
from scripts.common import IntakeError, byte_digest, canonical, digest, parse_json, read_json

LIMIT = 1024 * 1024
COMPARATOR = 'canonical-json-equality-v1'


def manifest(root):
    value = read_json(Path(root) / 'intake.json', 'INVALID_MANIFEST')
    if not isinstance(value, dict) or set(value) != {'schema_version', 'tool_id', 'kind', 'dependencies', 'operations'}:
        raise IntakeError('INVALID_MANIFEST')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise IntakeError('INVALID_MANIFEST')
    if not matches(IDENTIFIER, value['tool_id']) or value['kind'] not in ('skill', 'plugin', 'module'):
        raise IntakeError('INVALID_MANIFEST')
    dependencies = value['dependencies']
    if not isinstance(dependencies, list):
        raise IntakeError('INVALID_MANIFEST')
    names = set()
    for dep in dependencies:
        if not isinstance(dep, dict) or set(dep) != {'distribution', 'version'}:
            raise IntakeError('INVALID_MANIFEST')
        if not all(isinstance(v, str) and v and len(v) < 128 for v in dep.values()):
            raise IntakeError('INVALID_MANIFEST')
        import re
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', dep['distribution']):
            raise IntakeError('INVALID_MANIFEST')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.!+_-]*', dep['version']):
            raise IntakeError('INVALID_MANIFEST')
        normalized = re.sub(r'[-_.]+', '-', dep['distribution']).lower()
        if normalized in names:
            raise IntakeError('INVALID_MANIFEST')
        names.add(normalized)
    operations = value['operations']
    if not isinstance(operations, dict) or not operations:
        raise IntakeError('INVALID_MANIFEST')
    for name, operation in operations.items():
        if not matches(IDENTIFIER, name) or not isinstance(operation, dict):
            raise IntakeError('INVALID_MANIFEST')
        if set(operation) - {'script', 'timeout_seconds', 'side_effects', 'cases'} or not {'script', 'side_effects', 'cases'} <= set(operation):
            raise IntakeError('INVALID_MANIFEST')
        script = operation['script']
        if not isinstance(script, str) or not script or '\\' in script:
            raise IntakeError('INVALID_MANIFEST')
        relative = PurePosixPath(script)
        if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.py':
            raise IntakeError('UNSAFE_PATH')
        target = Path(root) / script
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(Path(root).resolve()):
            raise IntakeError('UNSAFE_PATH')
        operation.setdefault('timeout_seconds', 300)
        timeout = operation['timeout_seconds']
        if type(timeout) is not int or not 1 <= timeout <= 3600 or operation['side_effects'] != 'none':
            raise IntakeError('INVALID_MANIFEST')
        if not isinstance(operation['cases'], list) or len(operation['cases']) > 100:
            raise IntakeError('INVALID_MANIFEST')
        for case in operation['cases']:
            if not isinstance(case, dict) or set(case) != {'input', 'expected'}:
                raise IntakeError('INVALID_MANIFEST')
            if len(canonical(case)) > LIMIT:
                raise IntakeError('INVALID_MANIFEST')
    return value


def runtime():
    packages = sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions())
    return {'mode': 'local-demo', 'python': sys.version, 'executable': str(Path(sys.executable).resolve()),
            'executable_digest': byte_digest(Path(sys.executable).read_bytes()),
            'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(),
            'libc': list(platform.libc_ver()), 'packages': packages}


def dependencies(declared):
    found, issues = [], []
    for dep in declared:
        try:
            actual = importlib.metadata.version(dep['distribution'])
            status = 'satisfied' if actual == dep['version'] else 'conflict'
        except importlib.metadata.PackageNotFoundError:
            actual, status = None, 'missing'
        found.append({'kind': 'python', 'name': dep['distribution'],
                      'requirement': dep['distribution'] + '==' + dep['version'], 'status': status,
                      'evidence': ['Local metadata version: ' + (actual or 'not installed')]})
        if status != 'satisfied':
            issues.append({'code': 'DEPENDENCY_MISSING' if actual is None else 'DEPENDENCY_CONFLICT',
                           'message': 'Declared Python distribution unavailable at required version',
                           'next_step': 'Resolve dependencies in a candidate environment and retry'})
    return found, issues


def execute(root, operation, value):
    raw = canonical(value)
    if len(raw) > LIMIT:
        raise IntakeError('INPUT_LIMIT')
    root = Path(root).resolve()
    wrapper = 'import sys,runpy; root,script=sys.argv[1:]; sys.path.insert(0,root); sys.argv=[script]; runpy.run_path(script,run_name="__main__")'
    with tempfile.TemporaryDirectory(prefix='dots-run-') as temp:
        work = Path(temp)
        input_path = work / 'stdin.json'
        input_path.write_bytes(raw)
        env = {'PATH': os.defpath, 'HOME': temp, 'TMPDIR': temp, 'LANG': 'C.UTF-8'}
        with input_path.open('rb') as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                proc = subprocess.Popen([sys.executable, '-I', '-B', '-c', wrapper, str(root), str(root / operation['script'])],
                                        stdin=stdin, stdout=stdout, stderr=stderr, cwd=work,
                                        env=env, start_new_session=True)
            except OSError:
                raise IntakeError('EXECUTION_FAILED') from None
            start = time.monotonic()
            try:
                while proc.poll() is None:
                    if time.monotonic() - start > operation['timeout_seconds']:
                        raise IntakeError('TEST_TIMEOUT')
                    if max(os.fstat(stdout.fileno()).st_size, os.fstat(stderr.fileno()).st_size) > LIMIT:
                        raise IntakeError('OUTPUT_LIMIT')
                    time.sleep(0.02)
                if max(os.fstat(stdout.fileno()).st_size, os.fstat(stderr.fileno()).st_size) > LIMIT:
                    raise IntakeError('OUTPUT_LIMIT')
                if proc.returncode != 0:
                    raise IntakeError('EXECUTION_FAILED')
                stdout.seek(0)
                try:
                    result = parse_json(stdout.read(LIMIT + 1))
                except (ValueError, UnicodeError, RecursionError):
                    raise IntakeError('INVALID_OUTPUT') from None
                return result
            finally:
                # Also terminate descendants still in the original process group.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()


def suite_digest(operation):
    return digest({'operation': operation, 'comparator': COMPARATOR})
