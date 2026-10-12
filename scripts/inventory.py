"""Read-only requirements inventory. Exit zero is NOT tool admission."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.common import IntakeError, canonical

DECLARATION = re.compile(r'([A-Za-z0-9][A-Za-z0-9._-]*)(?:\s*(?:===|==|!=|~=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+)?')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise IntakeError('INVALID_ARGUMENT')


def inventory(tool):
    tool = Path(tool)
    if tool.is_symlink():
        raise IntakeError('UNSAFE_PATH')
    if not tool.is_dir():
        raise IntakeError('INVALID_ARGUMENT')
    tool = tool.resolve()
    report = dict(schema_version=1, source_ref=str(tool), environment_ref=None,
                  coverage=['Root requirements.txt simple declarations only; no code, other manifests, plugins, accounts or target environment inspected'],
                  dependencies=[], issues=[], trial=dict(status='not_run', input_ref=None,
                  expected_ref=None, result_ref=None, evidence=[]), outcome='unverified')
    declaration = tool / 'requirements.txt'
    if declaration.is_symlink():
        raise IntakeError('UNSAFE_PATH')
    try:
        fd = os.open(declaration, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        report['issues'].append(dict(code='DECLARATION_MISSING',
            message='Root requirements.txt not found', next_step='Inspect other manifests, code and documentation'))
        return report
    except OSError:
        raise IntakeError('READ_FAILED') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise IntakeError('READ_FAILED')
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            fd = None
            content = stream.read()
    except (OSError, UnicodeError):
        raise IntakeError('READ_FAILED') from None
    finally:
        if fd is not None:
            os.close(fd)
    if not content.strip():
        report['coverage'].append('Declaration file is empty; dependency completeness is unknown')
    for number, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = DECLARATION.fullmatch(line)
        if match:
            report['dependencies'].append(dict(kind='python', name=match[1],
                requirement=line, status='unverified', evidence=[f'requirements.txt:{number}']))
        else:
            report['issues'].append(dict(code='UNSUPPORTED_DECLARATION',
                message=f'Unsupported declaration at requirements.txt:{number}',
                next_step='Review this line separately without executing or exposing its contents'))
    return report


def write_inventory(tool, output):
    output = Path(output)
    if output.is_symlink() or output.exists():
        raise IntakeError('OUTPUT_EXISTS')
    report = inventory(tool)
    if output.resolve().is_relative_to(Path(report['source_ref'])):
        raise IntakeError('UNSAFE_PATH')
    created = False
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(report) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise IntakeError('OUTPUT_EXISTS') from None
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise IntakeError('WRITE_FAILED') from None


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--tool', required=True)
        parser.add_argument('--output', required=True)
        args = parser.parse_args(argv)
        write_inventory(args.tool, args.output)
        return 0
    except IntakeError as error:
        print(json.dumps({'error': {'code': error.code, 'message': error.message}}), file=sys.stderr)
        return 3 if error.code in ('READ_FAILED', 'WRITE_FAILED') else 2


if __name__ == '__main__':
    sys.exit(main())
