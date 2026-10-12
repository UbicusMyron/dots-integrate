import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.common import IntakeError, atomic_json, read_json
from scripts.controller import Controller
from scripts.intake import main
from scripts.runner import runtime


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = self.root / 'tool'
        shutil.copytree(Path(__file__).resolve().parents[1] / 'examples/sum-tool', self.tool)
        self.controller = Controller(self.root / 'state', local_demo=True)
        self.controller.initialize()

    def change_manifest(self, change):
        path = self.tool / 'intake.json'
        data = read_json(path); change(data); path.write_text(json.dumps(data))

    def upload(self):
        return self.controller.upload(self.tool)

    def test_upload_auto_validate_call_second_input_revoke(self):
        upload = self.upload(); key = upload['artifact_digest']
        self.assertTrue(all(r['state'] == 'passed' for r in upload['results']))
        called = self.controller.call(key, 'sum', {'values':[10,20,30]})
        self.assertEqual(called['result'], {'total':60})
        self.assertEqual(called['mode'], 'local-demo')
        self.assertEqual(len(self.controller.listing()['registry']['entries']), 1)
        self.controller.revoke(key, 'sum')
        with self.assertRaises(IntakeError) as error:
            self.controller.call(key, 'sum', {'values':[1]})
        self.assertEqual(error.exception.code, 'NOT_ALLOWLISTED')
        events = [json.loads(line) for line in (self.controller.store.root / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events[-1]['event'], 'invocation_denied')
        starts = [e for e in events if e['event'] == 'invocation_started']
        self.assertEqual(starts[0]['validation_id'], called['validation_id'])

    def test_failure_and_missing_case_remain_denied(self):
        self.change_manifest(lambda m:m['operations']['sum']['cases'][0].update(expected={'total':999}))
        upload = self.upload(); key = upload['artifact_digest']
        self.assertEqual(upload['results'][0]['state'], 'failed')
        with self.assertRaises(IntakeError):
            self.controller.call(key, 'sum', {'values':[1]})
        self.change_manifest(lambda m:m['operations']['sum'].update(cases=[]))
        result = self.upload()['results'][0]
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['reason_code'], 'MISSING_TEST_CASE')

    def test_pending_upload_snapshot_not_callable_and_cloud_cannot_import_local(self):
        with self.controller.store.locked():
            key = self.controller.store.snapshot(self.tool)
        with self.assertRaises(IntakeError):
            self.controller.call(key, 'sum', {'values':[1]})
        with self.assertRaises(IntakeError) as error:
            Controller(self.root / 'state')
        self.assertEqual(error.exception.code, 'CLOUD_ADAPTER_UNAVAILABLE')

    def test_modified_version_does_not_inherit_admission(self):
        first = self.upload()['artifact_digest']
        (self.tool / 'sum.py').write_text('print("{}")')
        second = self.upload()['artifact_digest']
        self.assertNotEqual(first, second)
        with self.assertRaises(IntakeError):
            self.controller.call(second, 'sum', {'values':[1]})
        self.assertEqual(self.controller.call(first, 'sum', {'values':[1]})['result'], {'total':1})

    def test_runtime_change_and_unvalidated_operation_denied(self):
        key = self.upload()['artifact_digest']
        changed = runtime(); changed['test-change'] = True
        with patch('scripts.controller.runtime', return_value=changed):
            with self.assertRaises(IntakeError) as error:
                self.controller.call(key, 'sum', {'values':[1]})
            self.assertEqual(error.exception.code, 'BINDING_MISMATCH')
        with self.assertRaises(IntakeError):
            self.controller.call(key, 'publish', {})

    def test_evidence_tampering_revokes_and_corrupt_registry_denies(self):
        key = self.upload()['artifact_digest']
        entry = self.controller.store.registry()['entries'][0]
        evidence_path = self.controller.store.path(entry['evidence_ref'])
        evidence_path.write_text('{}')
        with self.assertRaises(IntakeError):
            self.controller.call(key, 'sum', {})
        self.assertEqual(self.controller.store.registry()['entries'], [])
        (self.controller.store.root / 'allowlist.json').write_text('{')
        with self.assertRaises(IntakeError) as error:
            self.controller.listing()
        self.assertEqual(error.exception.code, 'REGISTRY_INVALID')

    def test_retry_revokes_first_and_only_one_effective_entry(self):
        key = self.upload()['artifact_digest']
        retried = self.controller.validate(key, 'sum')['results'][0]
        self.assertEqual(retried['attempt'], 2)
        self.assertEqual(len(self.controller.store.registry()['entries']), 1)
        with patch('scripts.controller.execute', side_effect=IntakeError('TEST_TIMEOUT')):
            failed = self.controller.validate(key, 'sum')['results'][0]
        self.assertEqual(failed['state'], 'failed')
        self.assertEqual(self.controller.store.registry()['entries'], [])

    def test_restart_recovery_removes_inconsistent_grant(self):
        upload = self.upload(); key = upload['artifact_digest']
        record = upload['results'][0]
        record['state'] = 'validating'
        self.controller.store.save_record(record)
        restarted = Controller(self.root / 'state', local_demo=True)
        self.assertEqual(restarted.listing()['registry']['entries'], [])
        with self.assertRaises(IntakeError):
            restarted.call(key, 'sum', {})

    def test_persistence_failure_does_not_survive_recovery(self):
        original = self.controller.store.save_record
        def fail_final(record):
            if record['state'] == 'passed':
                raise OSError('injected failure')
            return original(record)
        with patch.object(self.controller.store, 'save_record', side_effect=fail_final):
            with self.assertRaises(OSError):
                self.upload()
        self.assertEqual(self.controller.listing()['registry']['entries'], [])

    def test_cli_fail_closed_before_state_creation(self):
        out, err = io.StringIO(), io.StringIO()
        state = self.root / 'never-created'
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(['--state',str(state),'init'])
        self.assertEqual(status, 2)
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(json.loads(err.getvalue())['error']['code'], 'CLOUD_ADAPTER_UNAVAILABLE')
        self.assertFalse(state.exists())
