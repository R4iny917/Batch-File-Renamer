import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QRect, QEvent, Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest

from PySide6.QtWidgets import QApplication, QMessageBox
from renamer.ui.main_window import MainWindow
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
        self.assertEqual(self.window.preview_panel.table.rowCount(), 1)
        self.window.rules_panel.prefix.setText("旅行_")
        self.assertEqual(self.window.preview_panel.table.item(0, 1).text(), "旅行_照片.JPG")
        self.assertTrue(self.window.execute_button.isEnabled())
        self.assertEqual(self.source.read_bytes(), b"photo")
        self.window.preview_panel.table.selectRow(0)
        self.window.remove_selected()
        self.assertEqual(self.window.preview_panel.table.rowCount(), 0)
        self.assertFalse(self.window.execute_button.isEnabled())

    def test_conflict_disables_execution(self):
        (self.root / "x照片.JPG").write_bytes(b"existing")
        self.window.add_paths([self.source])
        self.window.rules_panel.prefix.setText("x")
        self.assertFalse(self.window.execute_button.isEnabled())
        self.assertTrue(self.window.workspace.rows[0].error)

    def test_window_fits_small_screen_and_keeps_execute_visible(self):
        self.window.show()
        self.app.processEvents()
        for area in (QRect(0, 0, 1280, 750), QRect(1280, 0, 900, 600)):
            self.window.fit_to_available_area(area)
            self.app.processEvents()
            self.assertTrue(area.contains(self.window.frameGeometry()))
            button = self.window.execute_button
            position = button.mapTo(self.window, button.rect().bottomRight())
            self.assertTrue(self.window.rect().contains(position))
            self.assertLessEqual(self.window.width(), area.width() - 32)

    def test_copy_original_name_and_paste_part_into_find(self):
        self.window.add_paths([self.source])
        self.window.preview_panel.table.setCurrentCell(0, 0)
        self.assertEqual(self.window.preview_panel.original_name.text(), "照片")
        self.assertTrue(self.window.preview_panel.original_name.isReadOnly())
        self.window.preview_panel.original_name.setSelection(0, 2)
        self.window.preview_panel.original_name.copy()
        self.window.rules_panel.find.paste()
        self.window.rules_panel.replacement.setText("旅行")
        self.assertEqual(self.window.preview_panel.table.item(0, 1).text(), "旅行.JPG")
        self.assertEqual(self.source.read_bytes(), b"photo")

    def test_sidebar_scrolls_example_with_numbering_without_overlay(self):
        self.window.show()
        self.window.resize(810, 488)
        self.window.rules_panel.numbering.setChecked(True)
        QTest.qWait(260)
        self.app.processEvents()
        scroll = self.window.rules_panel.rules_scroll
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertTrue(scroll.isAncestorOf(self.window.rules_panel.example))
        self.assertFalse(scroll.edges.isVisible())
        self.assertTrue(self.window.rules_panel.example.isVisible())
        for control in (self.window.rules_panel.start, self.window.rules_panel.digits):
            position = control.mapTo(scroll.viewport(), control.rect().bottomRight())
            self.assertTrue(scroll.viewport().rect().contains(position))
        self.assertTrue(self.window.rules_panel.start.isEnabled())
        self.window.rules_panel.numbering.setChecked(False)
        self.assertFalse(self.window.rules_panel.start.isEnabled())

    def test_copy_selected_original_names_and_clear_selection(self):
        second = self.root / "second.txt"
        second.write_bytes(b"second")
        self.window.add_paths([self.source, second])
        self.window.preview_panel.table.selectAll()
        self.window.preview_panel.copy_name_action.trigger()
        self.assertEqual(self.app.clipboard().text(), "照片.JPG\nsecond.txt")
        self.window.set_paths([])
        self.assertEqual(self.window.preview_panel.original_name.text(), "")
        self.window.preview_panel.copy_name_action.trigger()
        self.assertEqual(self.app.clipboard().text(), "照片.JPG\nsecond.txt")

    def test_modern_number_controls_update_preview_and_reset(self):
        self.window.add_paths([self.source])
        self.window.rules_panel.numbering.setChecked(True)
        self.window.rules_panel.start.plus.click()
        self.window.rules_panel.digits.setCurrentIndex(3)
        self.assertEqual(self.window.preview_panel.table.item(0, 1).text(), "照片_0002.JPG")
        self.window.rules_panel.start.setValue(0)
        self.window.rules_panel.start.minus.click()
        self.assertEqual(self.window.rules_panel.start.value(), 0)
        self.window.rules_panel.digits.setValue(8)
        self.assertEqual(self.window.preview_panel.table.item(0, 1).text(), "照片_00000000.JPG")
        self.window.reset_rules()
        self.assertEqual(self.window.rules_panel.start.value(), 1)
        self.assertEqual(self.window.rules_panel.digits.value(), 3)
        self.assertFalse(self.window.rules_panel.start.isEnabled())

    def test_fill_find_uses_only_selected_substring(self):
        self.window.add_paths([self.source])
        self.window.preview_panel.table.setCurrentCell(0, 0)
        self.window.preview_panel.original_name.setSelection(0, 1)
        self.window.preview_panel.fill_find_button.click()
        self.assertEqual(self.window.rules_panel.find.text(), "照")
        self.window.rules_panel.replacement.setText("旅")
        self.assertEqual(self.window.workspace.rows[0].target.name, "旅片.JPG")
        self.window.preview_panel.original_name.deselect()
        self.window.preview_panel.fill_find_button.click()
        self.assertEqual(self.window.rules_panel.find.text(), "照")
        self.assertIn("请先", self.window.preview_panel.name_feedback.text())

    def test_fill_find_preserves_selection_after_native_focus_loss(self):
        self.window.add_paths([self.source])
        self.window.preview_panel.table.setCurrentCell(0, 0)
        for reason in (Qt.FocusReason.MouseFocusReason, Qt.FocusReason.TabFocusReason):
            self.window.preview_panel.original_name.setSelection(0, 1)
            self.app.sendEvent(self.window.preview_panel.original_name, QFocusEvent(QEvent.Type.FocusOut, reason))
            self.window.preview_panel.fill_find_button.click()
            self.assertEqual(self.window.rules_panel.find.text(), "照")
            self.assertEqual(self.window.preview_panel.original_name.selectedText(), "照")

    def test_filename_field_strips_only_last_extension_and_clears_selection(self):
        paths = [self.root / name for name in ("archive.tar.gz", "README", ".gitignore", "archive.tar.txt")]
        for path in paths:
            path.write_text("sample")
        self.window.add_paths(paths)
        for index, expected in enumerate(("archive.tar", "README", ".gitignore", "archive.tar")):
            self.window.preview_panel.table.setCurrentCell(index, 0)
            self.assertEqual(self.window.preview_panel.original_name.text(), expected)
            self.assertFalse(self.window.preview_panel.original_name.hasSelectedText())
            self.window.preview_panel.original_name.selectAll()
        self.window.preview_panel.table.setCurrentCell(0, 0)
        self.assertFalse(self.window.preview_panel.original_name.hasSelectedText())

    def test_numbering_rapid_toggle_and_reset_collapse(self):
        self.window.show()
        for checked in (True, False, True):
            self.window.rules_panel.numbering.setChecked(checked)
            QTest.qWait(30)
        self.window.reset_rules()
        QTest.qWait(260)
        self.assertEqual(self.window.rules_panel.number_settings.maximumHeight(), 0)
        self.assertFalse(self.window.rules_panel.number_settings.isEnabled())
        self.assertEqual(self.window.rules_panel.numbering.progress, 0)

    def test_confirmation_buttons_and_safe_keyboard_defaults(self):
        for action in ("confirm", "cancel", "escape", "enter", "close"):
            observed = {}
            def respond():
                box = self.app.activeModalWidget()
                observed["labels"] = [box.button(b).text() for b in
                                      (QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)]
                observed["default"] = box.defaultButton() == box.button(QMessageBox.StandardButton.Cancel)
                if action == "confirm":
                    box.button(QMessageBox.StandardButton.Yes).click()
                elif action == "cancel":
                    box.button(QMessageBox.StandardButton.Cancel).click()
                elif action == "close":
                    box.close()
                else:
                    QTest.keyClick(box, Qt.Key.Key_Escape if action == "escape" else Qt.Key.Key_Return)
            QTimer.singleShot(0, respond)
            result = self.window.confirm_action("确认批量改名", "将改名 1 个文件", "不会覆盖已有文件", "确认改名")
            self.assertEqual(observed["labels"], ["确认改名", "取消"])
            self.assertTrue(observed["default"])
            self.assertEqual(result, action == "confirm")

    def test_cancel_does_not_rename(self):
        self.window.add_paths([self.source])
        self.window.rules_panel.prefix.setText("x")
        with patch.object(MainWindow, "confirm_action", return_value=False):
            self.window.execute_button.click()
        self.assertFalse(self.window.busy)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.window.workspace.session.history)

    def test_confirm_execute_then_undo_updates_disk_and_table(self):
        self.window.add_paths([self.source])
        self.window.rules_panel.prefix.setText("旅行_")
        with patch.object(MainWindow, "confirm_action", return_value=True):
            self.window.execute_button.click()
            self.assertTrue(self.window.busy)
            self.assertFalse(self.window.content.isEnabled())
            self.wait_worker()
            self.assertEqual(self.window.preview_panel.table.item(0, 0).text(), "旅行_照片.JPG")
            self.assertEqual(self.window.rules_panel.prefix.text(), "")
            self.assertFalse(self.source.exists())
            self.assertTrue(self.window.undo_button.isEnabled())
            self.window.undo_button.click()
            self.wait_worker()
        self.assertEqual(self.source.read_bytes(), b"photo")
        self.assertEqual(self.window.preview_panel.table.item(0, 0).text(), "照片.JPG")
        self.assertFalse(self.window.undo_button.isEnabled())

    def test_stale_preview_is_reported_and_refreshes(self):
        self.window.add_paths([self.source])
        self.window.rules_panel.prefix.setText("x")
        self.source.write_bytes(b"changed")
        with patch.object(MainWindow, "confirm_action", return_value=True), patch.object(QMessageBox, "exec"):
            self.window.execute_button.click()
            self.wait_worker()
        self.assertTrue(self.source.exists())
        self.assertTrue(self.window.workspace.last_result.errors)
        self.assertFalse(self.window.workspace.last_result.ok)

    def test_refresh_preserves_same_filename_selection(self):
        self.window.add_paths([self.source])
        self.window.preview_panel.table.setCurrentCell(0, 0)
        self.window.preview_panel.original_name.setSelection(0, 1)
        self.window.rules_panel.prefix.setText("旅行_")
        self.window.refresh_preview()
        self.assertEqual(self.window.preview_panel.original_name.selectedText(), "照")
        self.assertEqual(self.window.rules_panel.example.text(), "旅行_照片.JPG")

    def test_clear_list_keeps_undo_history(self):
        self.window.add_paths([self.source])
        self.window.rules_panel.prefix.setText("旅行_")
        with patch.object(MainWindow, "confirm_action", return_value=True):
            self.window.execute_button.click()
            self.wait_worker()
            self.window.set_paths([])
            self.assertTrue(self.window.undo_button.isEnabled())
            self.window.undo_button.click()
            self.wait_worker()
        self.assertEqual(self.window.preview_panel.table.rowCount(), 0)
        self.assertEqual(self.source.read_bytes(), b"photo")

    def test_busy_window_rejects_close_and_duplicate_operation(self):
        from threading import Event
        from renamer.operations import Result
        gate = Event()
        self.window.show()
        self.window.start_operation(lambda: (gate.wait(5), Result(True, "完成"))[1], "test")
        worker = self.window.worker
        try:
            self.window.start_operation(lambda: self.fail("重复启动了任务"), "duplicate")
            self.assertIs(self.window.worker, worker)
            self.assertFalse(self.window.close())
            self.assertTrue(self.window.isVisible())
        finally:
            gate.set()
            self.wait_worker()

    def test_worker_exception_restores_interaction_and_preserves_rules(self):
        self.window.add_paths([self.source])
        self.window.rules_panel.prefix.setText("旅行_")
        def fail():
            raise RuntimeError("模拟后台异常")
        with patch.object(QMessageBox, "exec"):
            self.window.start_operation(fail, "execute")
            self.wait_worker()
        self.assertTrue(self.window.content.isEnabled())
        self.assertEqual(self.window.rules_panel.prefix.text(), "旅行_")
        self.assertFalse(self.window.workspace.last_result.ok)
        self.assertIn("模拟后台异常", self.window.workspace.last_result.errors[0])

    def test_partial_failure_and_recovery_update_table(self):
        second = self.root / "second.txt"
        second.write_bytes(b"second")
        self.window.add_paths([self.source, second])
        self.window.rules_panel.prefix.setText("x")
        real_rename = operations.rename_locked
        def fail_second(source, target, snapshot):
            if source == second:
                self.source.write_bytes(b"intruder")
                raise PermissionError("模拟占用")
            real_rename(source, target, snapshot)
        with patch.object(MainWindow, "confirm_action", return_value=True), patch.object(QMessageBox, "exec"):
            with patch("renamer.operations.rename_locked", side_effect=fail_second):
                self.window.execute_button.click()
                self.wait_worker()
            self.assertEqual(self.window.preview_panel.table.item(0, 0).text(), "x照片.JPG")
            self.assertTrue(self.window.workspace.session.pending)
            self.assertFalse(self.window.execute_button.isEnabled())
            self.source.unlink()
            self.window.recover_button.click()
            self.wait_worker()
        self.assertFalse(self.window.workspace.session.pending)
        self.assertEqual(self.window.preview_panel.table.item(0, 0).text(), "照片.JPG")
        self.assertEqual(self.source.read_bytes(), b"photo")


if __name__ == "__main__":
    unittest.main()
