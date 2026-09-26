import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QPoint, QMimeData, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from renamer.core import Rules, build_preview
from renamer.ui.preview_panel import PreviewPanel
from renamer.ui.rules_panel import RulesPanel


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rules_restore_is_silent_and_reset_emits_once(self):
        panel = RulesPanel()
        self.addCleanup(panel.close)
        spy = QSignalSpy(panel.rules_changed)
        rules = Rules("old", "new", "prefix", "suffix", True, 0, 8)
        panel.set_rules(rules)
        self.assertEqual(panel.rules(), rules)
        self.assertEqual(spy.count(), 0)
        self.assertTrue(panel.start.isEnabled())
        panel.reset()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(spy.at(0)[0], Rules())
        QTest.qWait(260)
        self.assertEqual(panel.number_settings.maximumHeight(), 0)
        self.assertFalse(panel.start.isEnabled())

    def test_fill_find_emits_updated_rules_without_changing_other_fields(self):
        panel = RulesPanel()
        self.addCleanup(panel.close)
        panel.set_rules(Rules(replace="new", prefix="prefix", numbering=True, start=0))
        spy = QSignalSpy(panel.rules_changed)
        panel.fill_find("part")
        self.assertEqual(spy.count(), 1)
        self.assertEqual(spy.at(0)[0], Rules("part", "new", "prefix", numbering=True, start=0))
        self.assertEqual(panel.find.selectedText(), "part")

    def test_preview_emits_only_selected_text_and_preserves_selection_on_render(self):
        panel = PreviewPanel()
        self.addCleanup(panel.close)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "archive.tar.gz"
            source.write_bytes(b"example")
            rows = build_preview([source], Rules(prefix="x"))
            panel.render(rows)
            panel.table.setCurrentCell(0, 0)
            panel.original_name.setSelection(8, 3)
            panel.render(rows)
            spy = QSignalSpy(panel.find_requested)
            panel.fill_find_button.click()
            self.assertEqual(spy.count(), 1)
            self.assertEqual(spy.at(0)[0], "tar")
            panel.original_name.deselect()
            panel.fill_find_button.click()
            self.assertEqual(spy.count(), 1)
            panel.render([])
            self.assertEqual(panel.original_name.text(), "")
            self.assertFalse(panel.remove_button.isEnabled())
            self.assertFalse(panel.clear_button.isEnabled())

    def test_external_file_drag_shows_and_hides_drop_overlay(self):
        panel = PreviewPanel()
        self.addCleanup(panel.close)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("sample")
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(path))])
            event = QDragEnterEvent(
                QPoint(20, 20), Qt.DropAction.CopyAction, mime,
                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
            )

            panel.table.dragEnterEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertFalse(panel.table.drop_overlay.isHidden())

            panel.table.dragLeaveEvent(QDragLeaveEvent())
            self.assertFalse(panel.table.drop_overlay.isVisible())


if __name__ == "__main__":
    unittest.main()
