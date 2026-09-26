import os
import sys
import tempfile
import unittest
from pathlib import Path

NATIVE_RUN = __name__ == "__main__" and "--run" in sys.argv
if NATIVE_RUN:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontInfo, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QTextEdit, QPushButton, QStyle, QStyleOptionButton

from renamer.ui.dialogs import AppMessageBox
from renamer.ui.controls import HeadingLabel
from renamer.ui.main_window import MainWindow
from renamer.ui.runtime import configure_fonts, configure_platform, set_light_titlebar


@unittest.skipUnless(NATIVE_RUN and sys.platform == "win32", "使用独立进程执行 test_native_ui.py --run")
class NativeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_platform()
        cls.app = QApplication([])
        cls.app.setStyle("Fusion")
        configure_fonts(cls.app)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "旅行照片.JPG"
        self.source.write_bytes(b"sample")
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.window.add_paths([self.source])
        self.window.show()
        self.window.activateWindow()
        set_light_titlebar(self.window)
        QTest.qWait(150)
        self.assertEqual(self.app.platformName(), "windows")

    def test_mouse_focus_loss_keeps_partial_filename_for_find(self):
        panel = self.window.preview_panel
        panel.table.setCurrentCell(0, 0)
        QTest.mouseClick(panel.original_name, Qt.MouseButton.LeftButton)
        panel.original_name.setSelection(0, 2)
        self.assertTrue(panel.original_name.hasFocus())
        QTest.mouseClick(panel.fill_find_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.rules_panel.find.text(), "旅行")
        self.assertEqual(panel.original_name.selectedText(), "旅行")
        self.assertTrue(self.window.rules_panel.find.hasFocus())
        self.assertEqual(panel.original_name.cursor().shape(), Qt.CursorShape.IBeamCursor)
        self.assertEqual(self.window.rules_panel.start.editor.cursor().shape(), Qt.CursorShape.IBeamCursor)

    def test_real_bold_faces_and_unobscured_numbering_at_normal_size(self):
        self.window.resize(1100, 650)
        self.app.processEvents()
        for label in self.window.findChildren(HeadingLabel):
            self.assertEqual(QFontInfo(label.font()).styleName(), "Bold", label.text())
        rules = self.window.rules_panel
        viewport = rules.rules_scroll.viewport()
        for point in (rules.numbering.rect().topLeft(), rules.numbering.rect().bottomRight()):
            self.assertTrue(viewport.rect().contains(rules.numbering.mapTo(viewport, point)))
        self.assertFalse(rules.rules_scroll.edges.isVisible())

    def test_rendering_backend_preserves_smooth_text(self):
        self.assertEqual(os.environ["QT_QPA_PLATFORM"], "windows:fontengine=freetype")

    def test_button_contents_fit_font_and_icon(self):
        for size in ((1100, 700), (810, 488)):
            self.window.resize(*size)
            self.app.processEvents()
            for button in self.window.findChildren(QPushButton):
                if not button.isVisible() or not button.text():
                    continue
                option = QStyleOptionButton()
                button.initStyleOption(option)
                contents = button.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, button)
                required = max(button.fontMetrics().height(), button.iconSize().height() if not button.icon().isNull() else 0)
                with self.subTest(size=size, button=button.text()):
                    self.assertGreaterEqual(contents.height(), required)

    def test_small_window_keeps_controls_visible_after_toggle_and_scroll(self):
        self.window.resize(810, 488)
        rules = self.window.rules_panel
        for enabled in (True, False, True):
            rules.numbering.setChecked(enabled)
            QTest.qWait(30)
        QTest.qWait(260)
        scroll = rules.rules_scroll
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        for widget in (rules.start, rules.digits):
            bottom = widget.mapTo(scroll.viewport(), widget.rect().bottomRight())
            self.assertTrue(scroll.viewport().rect().contains(bottom))
        bottom = self.window.execute_button.mapTo(self.window, self.window.execute_button.rect().bottomRight())
        self.assertTrue(self.window.rect().contains(bottom))
        self.assertTrue(rules.example.isVisible())
        self.assertTrue(scroll.edges.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_confirmation_defaults_and_details_are_readable(self):
        observed = {}
        def inspect_confirmation():
            box = self.app.activeModalWidget()
            observed["confirm"] = box.button(QMessageBox.StandardButton.Yes).text()
            observed["default"] = box.defaultButton() == box.button(QMessageBox.StandardButton.Cancel)
            QTest.keyClick(box, Qt.Key.Key_Return)
        QTimer.singleShot(50, inspect_confirmation)
        self.assertFalse(self.window.confirm_action("确认批量改名", "将改名 1 个文件", "不会覆盖已有文件", "确认改名"))
        self.assertEqual(observed, {"confirm": "确认改名", "default": True})
        box = AppMessageBox(self.window)
        box.setText("文件操作详情")
        box.setDetailedText("示例路径：照片.JPG\n模拟文件占用")
        box.show()
        self.addCleanup(box.close)
        self.app.processEvents()
        button = next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.ActionRole)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertTrue(box.findChild(QTextEdit).isVisible())
        self.assertEqual(button.text(), "收起详情")
        self.assertEqual(box.palette().color(QPalette.ColorRole.Window).name(), "#ffffff")
        self.assertEqual(box.palette().color(QPalette.ColorRole.WindowText).name(), "#17243b")

    def test_startup_recovery_uses_later_as_safe_default(self):
        observed = {}

        def inspect_confirmation():
            box = self.app.activeModalWidget()
            observed["later"] = box.button(QMessageBox.StandardButton.Cancel).text()
            observed["default"] = box.defaultButton() == box.button(QMessageBox.StandardButton.Cancel)
            QTest.keyClick(box, Qt.Key.Key_Escape)

        QTimer.singleShot(50, inspect_confirmation)
        self.assertFalse(self.window.confirm_action(
            "检测到上次未完成的改名", "已核对文件身份", "将再次检查目标名称",
            "恢复到改名前状态", cancel_text="稍后处理",
        ))
        self.assertEqual(observed, {"later": "稍后处理", "default": True})


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
