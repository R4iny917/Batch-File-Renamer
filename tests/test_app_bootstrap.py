import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from renamer.app import create_workspace
from renamer.core import Rules


class AppBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.local_app_data = Path(self.temp.name)

    def test_workspace_loads_recovery_state_from_local_app_data(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.local_app_data)}, clear=True):
            workspace = create_workspace()

        self.assertEqual(
            workspace.session.store.path,
            self.local_app_data / "Batch File Renamer" / "recovery.json",
        )
        self.assertFalse(workspace.session.recovery_error)

    def test_corrupt_recovery_record_is_preserved_and_blocks_rename(self):
        recovery_path = self.local_app_data / "Batch File Renamer" / "recovery.json"
        recovery_path.parent.mkdir(parents=True)
        recovery_path.write_text("{broken", encoding="utf-8")

        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.local_app_data)}, clear=True):
            workspace = create_workspace()

        result = workspace.session.execute([])

        self.assertTrue(workspace.session.recovery_error)
        self.assertFalse(result.ok)
        self.assertEqual(recovery_path.read_text(encoding="utf-8"), "{broken")

    def test_application_workspace_can_undo_a_saved_batch_after_restart(self):
        original = self.local_app_data / "photo.jpg"
        original.write_bytes(b"photo")

        def rename(source, target, snapshot):
            os.rename(source, target)

        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.local_app_data)}, clear=True):
            first_workspace = create_workspace()
            first_workspace.add_paths([original])
            first_workspace.set_rules(Rules(prefix="trip_"))
            with patch("renamer.operations.rename_locked", side_effect=rename):
                self.assertTrue(first_workspace.session.execute(first_workspace.rows).ok)

            restarted_workspace = create_workspace()
            self.assertEqual(len(restarted_workspace.session.history), 1)
            with patch("renamer.operations.rename_locked", side_effect=rename):
                result = restarted_workspace.session.undo()

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(original.exists())
        self.assertEqual(original.read_bytes(), b"photo")


if __name__ == "__main__":
    unittest.main()
