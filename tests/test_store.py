import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.common import IntakeError, atomic_json, parse_json
from scripts.store import Store, artifact_digest


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.store.initialize()
        self.tool = self.root / 'tool'; self.tool.mkdir()
        (self.tool / 'main.py').write_text('print(1)')

    def test_snapshot_content_and_mode_binding(self):
        with self.store.locked():
            key = self.store.snapshot(self.tool)
            self.assertEqual(key, artifact_digest(self.tool))
            self.assertEqual(key, self.store.snapshot(self.tool))
            (self.tool / 'main.py').chmod(0o700)
            self.assertNotEqual(key, self.store.snapshot(self.tool))
            snap = self.store.verified_snapshot(key) / 'main.py'
            snap.chmod(0o600); snap.write_text('print(2)')
            with self.assertRaises(IntakeError):
                self.store.verified_snapshot(key)

    def test_links_secrets_and_path_escape(self):
        with self.assertRaises(IntakeError):
            self.store.path('../outside')
        (self.tool / 'link').symlink_to('/tmp')
        with self.assertRaises(IntakeError):
            self.store.snapshot(self.tool)
        (self.tool / 'link').unlink()
        (self.tool / '.env').write_text('SECRET')
        with self.assertRaises(IntakeError):
            self.store.snapshot(self.tool)

    def test_atomic_failure_preserves_old_file(self):
        path = self.root / 'sample.json'
        atomic_json(path, {'old': True})
        with patch('scripts.common.os.replace', side_effect=OSError):
            with self.assertRaises(OSError):
                atomic_json(path, {'new': True})
        self.assertEqual(json.loads(path.read_text()), {'old': True})

    def test_corrupt_registry_and_mode_fail_closed(self):
        (self.store.root / 'allowlist.json').write_text('{')
        with self.assertRaises(IntakeError):
            self.store.registry()
        (self.store.root / 'mode.json').write_text('{"mode":"cloud"}')
        with self.assertRaises(IntakeError):
            with self.store.locked():
                pass
        with self.assertRaises(IntakeError):
            self.store.initialize()

    def test_strict_json(self):
        for value in ['{"a":1,"a":2}', 'NaN', '1e999']:
            with self.assertRaises(ValueError):
                parse_json(value)
