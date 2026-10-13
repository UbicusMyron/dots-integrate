"""Build a source/demo handoff archive, not a Dots installer."""
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
# Only these maintained source files and documentation are distributed.
PATTERNS = (
    'README.md', 'AGENTS.md', '.gitignore',
    'skills/dots-intake/SKILL.md',
    'scripts/common.py', 'scripts/inventory.py', 'scripts/admission.py',
    'scripts/store.py', 'scripts/runner.py', 'scripts/controller.py',
    'scripts/intake.py', 'scripts/build_delivery.py',
    'tests/test_*.py', 'docs/**/*.md', 'docs/**/*.json',
    'examples/sum-tool/sum.py', 'examples/sum-tool/intake.json',
    'examples/call-input.json', 'runtime/requirements.in',
)


def main():
    paths = set()
    for pattern in PATTERNS:
        matches = list(ROOT.glob(pattern))
        if not matches:
            raise ValueError(f'Missing delivery source: {pattern}')
        for path in matches:
            if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError(f'Invalid delivery source: {path}')
            if not path.resolve().is_relative_to(ROOT):
                raise ValueError('Delivery source escapes project')
            paths.add(path)
    output = ROOT / 'dist'
    if output.is_symlink():
        raise ValueError('Delivery directory must not be a symlink')
    output.mkdir(exist_ok=True)
    archive = output / 'dots-intake-source-demo.zip'
    checksum = archive.with_suffix('.zip.sha256')
    if archive.is_symlink() or checksum.is_symlink():
        raise ValueError('Delivery output must not be a symlink')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(paths):
            info = zipfile.ZipInfo('dots-intake-source-demo/' + path.relative_to(ROOT).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'{archive}: {len(paths)} source files; SHA-256 {digest}')


if __name__ == '__main__':
    main()
