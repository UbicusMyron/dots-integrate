import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.common import IntakeError, digest
from scripts.runner import execute, manifest, dependencies


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = dict(script='main.py', timeout_seconds=1, side_effects='none', cases=[])

    def run_script(self, code, value=None):
        (self.root / 'main.py').write_text(code)
        return execute(self.root, self.config, value)

    def test_actual_json_roundtrip_and_clean_environment(self):
        with patch.dict('os.environ', {'AWS_SECRET_ACCESS_KEY': 'sensitive-test-value'}):
            result = self.run_script('import sys,json,os\njson.dump({"input":json.load(sys.stdin),"secret":os.getenv("AWS_SECRET_ACCESS_KEY")},sys.stdout)', {'hello': '中文'})
        self.assertEqual(result, {'input': {'hello': '中文'}, 'secret': None})
        self.assertNotEqual(digest(True), digest(1))

    def test_timeout_failure_invalid_output_and_limit(self):
        for code, expected in [('import time; time.sleep(4)', 'TEST_TIMEOUT'),
                               ('raise RuntimeError("SECRET")', 'EXECUTION_FAILED'),
                               ('print("not json")', 'INVALID_OUTPUT'),
                               ('print("x" * 1100000)', 'OUTPUT_LIMIT'),
                               ('print("NaN")', 'INVALID_OUTPUT')]:
            with self.subTest(expected=expected):
                with self.assertRaises(IntakeError) as error:
                    self.run_script(code)
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn('SECRET', str(error.exception))

    def test_manifest_rejects_unsafe_command_and_bad_timeout(self):
        (self.root / 'main.py').write_text('print(1)')
        value = dict(schema_version=1, tool_id='test', kind='module', dependencies=[], operations={'run':self.config})
        (self.root / 'intake.json').write_text(json.dumps(value))
        self.assertEqual(manifest(self.root)['operations']['run']['cases'], [])
        for key, bad in [('script', '../main.py'), ('timeout_seconds', True), ('side_effects', 'write')]:
            modified = json.loads(json.dumps(value)); modified['operations']['run'][key] = bad
            (self.root / 'intake.json').write_text(json.dumps(modified))
            with self.assertRaises(IntakeError):
                manifest(self.root)

    def test_missing_dependencies(self):
        results, issues = dependencies([{'distribution':'dots-nonexistent-test-package-xyz','version':'1.0'}])
        self.assertEqual(results[0]['status'], 'missing')
        self.assertEqual(issues[0]['code'], 'DEPENDENCY_MISSING')
