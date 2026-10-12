import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.common import IntakeError
from scripts.inventory import inventory, main, write_inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tool = self.base / 'tool'
        self.tool.mkdir()
        self.output = self.base / 'report.json'

    def test_declarations_and_no_execution(self):
        (self.tool / 'requirements.txt').write_text('# comment\nSomeLib==1.0\nSomeLib==1.0\nother>=2\n')
        (self.tool / 'setup.py').write_text(f'open({str(self.base / "SENTINEL")!r}, "w").write("bad")')
        write_inventory(self.tool, self.output)
        report = json.loads(self.output.read_text())
        self.assertEqual(report['outcome'], 'unverified')
        self.assertEqual(report['trial']['status'], 'not_run')
        self.assertEqual(len(report['dependencies']), 3)
        self.assertEqual(report['dependencies'][0]['evidence'], ['requirements.txt:2'])
        self.assertFalse((self.base / 'SENTINEL').exists())

    def test_missing_and_empty_do_not_imply_complete(self):
        self.assertEqual(inventory(self.tool)['issues'][0]['code'], 'DECLARATION_MISSING')
        (self.tool / 'requirements.txt').write_text('')
        self.assertIn('unknown', inventory(self.tool)['coverage'][-1])

    def test_sensitive_unsupported_lines_are_not_reflected(self):
        (self.tool / 'requirements.txt').write_text('--index-url https://user:SECRET@example.org\n-r private.txt\na>=1,<3\nb;sys_platform=="linux"\n')
        report = inventory(self.tool)
        self.assertEqual(len(report['issues']), 4)
        self.assertNotIn('SECRET', json.dumps(report))

    def test_reject_paths_encoding_and_overwrite(self):
        self.output.write_text('original')
        with self.assertRaises(IntakeError) as error:
            write_inventory(self.tool, self.output)
        self.assertEqual(error.exception.code, 'OUTPUT_EXISTS')
        self.assertEqual(self.output.read_text(), 'original')
        with self.assertRaises(IntakeError):
            write_inventory(self.tool, self.tool / 'out.json')
        req = self.tool / 'requirements.txt'
        req.write_bytes(b'\xff')
        with self.assertRaises(IntakeError) as error:
            inventory(self.tool)
        self.assertEqual(error.exception.code, 'READ_FAILED')
        req.unlink()
        req.symlink_to(self.output)
        with self.assertRaises(IntakeError):
            inventory(self.tool)
        with self.assertRaises(IntakeError):
            inventory(self.base / 'missing')

    def test_io_failure_does_not_leave_success_report(self):
        with patch('scripts.inventory.os.fsync', side_effect=OSError):
            with self.assertRaises(IntakeError) as error:
                write_inventory(self.tool, self.output)
        self.assertEqual(error.exception.code, 'WRITE_FAILED')
        self.assertFalse(self.output.exists())
        with self.assertRaises(IntakeError):
            write_inventory(self.tool, self.base / 'missing' / 'out.json')

    def test_cli_error_envelope(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main(['--unknown', 'SECRET'])
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(json.loads(stderr.getvalue())['error']['code'], 'INVALID_ARGUMENT')
        self.assertNotIn('SECRET', stderr.getvalue())
