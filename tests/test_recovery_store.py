import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from renamer.recovery_store import RecoveryStore, RecoveryStoreError


class RecoveryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "state" / "recovery.json"
        self.store = RecoveryStore(self.path)
        self.state = {"schema_version": 1, "history": [], "active": None}

    def test_missing_record_loads_as_empty(self):
        self.assertIsNone(self.store.load())

    def test_saved_state_survives_store_recreation(self):
        self.store.save(self.state)

        loaded = RecoveryStore(self.path).load()

        self.assertEqual(loaded, self.state)

    def test_corrupt_json_is_preserved_and_reported(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{truncated", encoding="utf-8")

        with self.assertRaises(RecoveryStoreError):
            self.store.load()

        self.assertEqual(self.path.read_text(encoding="utf-8"), "{truncated")

    def test_unknown_schema_is_preserved_and_reported(self):
        self.path.parent.mkdir(parents=True)
        contents = '{"schema_version":99,"history":[],"active":null}'
        self.path.write_text(contents, encoding="utf-8")

        with self.assertRaises(RecoveryStoreError):
            self.store.load()

        self.assertEqual(self.path.read_text(encoding="utf-8"), contents)

    def test_invalid_state_structure_is_preserved_and_reported(self):
        self.path.parent.mkdir(parents=True)
        contents = '{"schema_version":1,"history":{},"active":null}'
        self.path.write_text(contents, encoding="utf-8")

        with self.assertRaises(RecoveryStoreError):
            self.store.load()

        self.assertEqual(self.path.read_text(encoding="utf-8"), contents)

    def test_invalid_utf8_is_preserved_and_reported(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"\xff\xfe")

        with self.assertRaises(RecoveryStoreError):
            self.store.load()

        self.assertEqual(self.path.read_bytes(), b"\xff\xfe")

    def test_invalid_state_is_rejected_without_creating_record(self):
        with self.assertRaises(RecoveryStoreError):
            self.store.save({"schema_version": 1, "history": {}, "active": None})

        self.assertFalse(self.path.exists())

    def test_failed_atomic_replace_keeps_previous_record(self):
        self.store.save(self.state)
        replacement = {"schema_version": 1, "history": ["next"], "active": None}

        with patch("renamer.recovery_store.os.replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(RecoveryStoreError):
                self.store.save(replacement)

        self.assertEqual(self.store.load(), self.state)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_default_path_uses_local_app_data(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root)}):
            path = RecoveryStore.default_path()

        self.assertEqual(path, self.root / "Batch File Renamer" / "recovery.json")

    def test_default_path_requires_local_app_data(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OSError):
                RecoveryStore.default_path()

    def test_clear_is_safe_when_record_is_missing(self):
        self.store.clear()

        self.assertIsNone(self.store.load())

    def test_clear_removes_existing_record(self):
        self.store.save(self.state)

        self.store.clear()

        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
