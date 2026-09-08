import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from renamer.app import MainWindow
from renamer import operations


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "照片.JPG"
        self.source.write_bytes(b"photo")
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def wait_worker(self):
        deadline = time.monotonic() + 10
        while self.window.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertFalse(self.window.busy)

    def test_add_deduplicate_preview_and_remove(self):
        self.window.add_paths([self.source, self.source])
        self.assertEqual(self.window.table.rowCount(), 1)
        self.window.prefix.setText("旅行_")
        self.assertEqual(self.window.table.item(0, 1).text(), "旅行_照片.JPG")
        self.assertTrue(self.window.execute_button.isEnabled())
        self.assertEqual(self.source.read_bytes(), b"photo")
        self.window.table.selectRow(0)
        self.window.remove_selected()
        self.assertEqual(self.window.table.rowCount(), 0)
        self.assertFalse(self.window.execute_button.isEnabled())

    def test_conflict_disables_execution(self):
        (self.root / "x照片.JPG").write_bytes(b"existing")
        self.window.add_paths([self.source])
        self.window.prefix.setText("x")
        self.assertFalse(self.window.execute_button.isEnabled())
        self.assertTrue(self.window.rows[0].error)

    def test_cancel_does_not_rename(self):
        self.window.add_paths([self.source])
        self.window.prefix.setText("x")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.window.execute_button.click()
        self.assertFalse(self.window.busy)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.window.session.history)

    def test_confirm_execute_then_undo_updates_disk_and_table(self):
        self.window.add_paths([self.source])
        self.window.prefix.setText("旅行_")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window.execute_button.click()
            self.assertTrue(self.window.busy)
            self.assertFalse(self.window.content.isEnabled())
            self.wait_worker()
            self.assertEqual(self.window.table.item(0, 0).text(), "旅行_照片.JPG")
            self.assertEqual(self.window.prefix.text(), "")
            self.assertFalse(self.source.exists())
            self.assertTrue(self.window.undo_button.isEnabled())
            self.window.undo_button.click()
            self.wait_worker()
        self.assertEqual(self.source.read_bytes(), b"photo")
        self.assertEqual(self.window.table.item(0, 0).text(), "照片.JPG")
        self.assertFalse(self.window.undo_button.isEnabled())

    def test_stale_preview_is_reported_and_refreshes(self):
        self.window.add_paths([self.source])
        self.window.prefix.setText("x")
        self.source.write_bytes(b"changed")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), patch.object(QMessageBox, "exec"):
            self.window.execute_button.click()
            self.wait_worker()
        self.assertTrue(self.source.exists())
        self.assertTrue(self.window.last_result.errors)
        self.assertFalse(self.window.last_result.ok)

    def test_partial_failure_and_recovery_update_table(self):
        second = self.root / "second.txt"
        second.write_bytes(b"second")
        self.window.add_paths([self.source, second])
        self.window.prefix.setText("x")
        real_rename = operations.rename_locked
        def fail_second(source, target, snapshot):
            if source == second:
                self.source.write_bytes(b"intruder")
                raise PermissionError("模拟占用")
            real_rename(source, target, snapshot)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), patch.object(QMessageBox, "exec"):
            with patch("renamer.operations.rename_locked", side_effect=fail_second):
                self.window.execute_button.click()
                self.wait_worker()
            self.assertEqual(self.window.table.item(0, 0).text(), "x照片.JPG")
            self.assertTrue(self.window.session.pending)
            self.assertFalse(self.window.execute_button.isEnabled())
            self.source.unlink()
            self.window.recover_button.click()
            self.wait_worker()
        self.assertFalse(self.window.session.pending)
        self.assertEqual(self.window.table.item(0, 0).text(), "照片.JPG")
        self.assertEqual(self.source.read_bytes(), b"photo")


if __name__ == "__main__":
    unittest.main()
