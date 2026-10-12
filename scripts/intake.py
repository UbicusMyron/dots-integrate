"""Local-demo controller. Production/cloud mode is deliberately fail-closed."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.common import IntakeError, canonical, read_json
from scripts.controller import Controller


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise IntakeError('INVALID_ARGUMENT')


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--state', required=True)
        parser.add_argument('--local-demo', action='store_true')
        sub = parser.add_subparsers(dest='command', required=True)
        sub.add_parser('init')
        sub.add_parser('list')
        upload = sub.add_parser('upload')
        upload.add_argument('--tool', required=True)
        for name in ('validate', 'call', 'revoke'):
            command = sub.add_parser(name)
            command.add_argument('--artifact', required=True)
            command.add_argument('--operation', required=True)
            if name == 'call':
                command.add_argument('--input', required=True)
        args = parser.parse_args(argv)
        controller = Controller(args.state, local_demo=args.local_demo)
        if args.command == 'init':
            result = controller.initialize()
        elif args.command == 'upload':
            result = controller.upload(args.tool)
        elif args.command == 'call':
            result = controller.call(args.artifact, args.operation, read_json(args.input, 'INVALID_INPUT'))
        elif args.command == 'list':
            result = controller.listing()
        else:
            result = getattr(controller, args.command)(args.artifact, args.operation)
        print(canonical(result).decode('utf-8'))
        return 1 if any(r['state'] != 'passed' for r in result.get('results', [])) else 0
    except IntakeError as error:
        print(json.dumps({'error': {'code': error.code, 'message': error.message}}), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({'error': {'code': 'STATE_INVALID', 'message': 'Operation failed; no permission granted'}}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
