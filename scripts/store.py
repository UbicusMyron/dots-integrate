"""Single-writer local demo storage; not a security boundary against same-UID code."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import shutil
import stat
import tempfile

from scripts.admission import DIGEST, matches, valid_registry
from scripts.common import IntakeError, atomic_json, byte_digest, canonical, digest, now, read_json


def files_in(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise IntakeError('UNSAFE_PATH')
    found, total = [], 0
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in sorted(dirs + names):
            path = Path(folder) / name
            if path.is_symlink():
                raise IntakeError('UNSAFE_PATH')
        dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__'))
        for name in dirs:
            if name.startswith('.'):
                raise IntakeError('UNSAFE_PATH')
        for name in sorted(names):
            path = Path(folder) / name
            if name.endswith('.pyc'):
                continue
            if name.startswith('.') or path.suffix.lower() in ('.pem', '.key'):
                raise IntakeError('UNSAFE_PATH')
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise IntakeError('UNSAFE_PATH')
            total += info.st_size
            if total > 16 * 1024 * 1024 or len(found) >= 512:
                raise IntakeError('ARTIFACT_LIMIT')
            found.append((path.relative_to(root).as_posix(), path, bool(info.st_mode & 0o111)))
    return sorted(found)


def artifact_digest(root):
    return digest([{'path': name, 'sha256': byte_digest(path.read_bytes()), 'executable': executable}
                   for name, path, executable in files_in(root)])


def remove_tree(path):
    """Only used for this program's private temporary snapshot directories."""
    for folder, dirs, names in os.walk(path):
        os.chmod(folder, 0o700)
        for name in names:
            os.chmod(Path(folder) / name, 0o600)
    shutil.rmtree(path)


class Store:
    def __init__(self, root):
        self.root = Path(root).absolute()

    def initialize(self):
        if self.root.exists() or self.root.is_symlink():
            raise IntakeError('STATE_EXISTS')
        self.root.mkdir(mode=0o700)
        for name in ('snapshots', 'records', 'evidence'):
            (self.root / name).mkdir(mode=0o700)
        atomic_json(self.root / 'mode.json', {'mode': 'local-demo', 'schema_version': 1})
        atomic_json(self.root / 'allowlist.json', {'schema_version': 1, 'revision': 0, 'entries': []})

    def path(self, relative):
        path = self.root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise IntakeError('UNSAFE_PATH')
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise IntakeError('UNSAFE_PATH')
            if candidate == self.root:
                break
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise IntakeError('UNSAFE_PATH')
        return path

    @contextmanager
    def locked(self):
        if self.root.is_symlink() or not self.root.is_dir():
            raise IntakeError('STATE_INVALID')
        if self.root.stat().st_mode & 0o077:
            raise IntakeError('UNTRUSTED_REGISTRY')
        if read_json(self.path('mode.json')) != {'mode': 'local-demo', 'schema_version': 1}:
            raise IntakeError('STATE_INVALID')
        fd = os.open(self.path('control.lock'), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield self
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def registry(self):
        value = read_json(self.path('allowlist.json'), 'REGISTRY_INVALID')
        if not valid_registry(value):
            raise IntakeError('REGISTRY_INVALID')
        return value

    def save_registry(self, value):
        if not valid_registry(value):
            raise IntakeError('REGISTRY_INVALID')
        atomic_json(self.path('allowlist.json'), value)

    def records(self):
        return [(p, read_json(p)) for p in sorted(self.path('records').glob('*.json'))]

    def save_record(self, value):
        atomic_json(self.path(f"records/{value['validation_id']}.json"), value)

    def audit(self, event, code, validation_id=None):
        payload = dict(mode='local-demo', at=now(), event=event, code=code, validation_id=validation_id)
        fd = os.open(self.path('events.jsonl'), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'ab') as stream:
            stream.write(canonical(payload) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())

    def snapshot(self, tool):
        tool = Path(tool)
        if self.root.resolve().is_relative_to(tool.resolve()):
            raise IntakeError('UNSAFE_PATH')
        source_files = files_in(tool)
        before = artifact_digest(tool)
        temp = Path(tempfile.mkdtemp(prefix='upload-', dir=self.path('snapshots')))
        try:
            for name, path, executable in source_files:
                target = temp / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                target.chmod(0o500 if executable else 0o400)
            computed = artifact_digest(temp)
            if computed != before or artifact_digest(tool) != before:
                raise IntakeError('ARTIFACT_CHANGED')
            destination = self.path(f'snapshots/{computed}')
            if destination.exists():
                self.verified_snapshot(computed)
            else:
                for folder, _, _ in os.walk(temp):
                    os.chmod(folder, 0o500)
                os.rename(temp, destination)
                temp = None
            return computed
        finally:
            if temp is not None:
                remove_tree(temp)

    def verified_snapshot(self, key):
        if not matches(DIGEST, key):
            raise IntakeError('INVALID_ARGUMENT')
        path = self.path(f'snapshots/{key}')
        if not path.is_dir() or artifact_digest(path) != key:
            raise IntakeError('ARTIFACT_CHANGED')
        return path
