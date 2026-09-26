from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QMessageBox, QTextEdit

from .runtime import set_light_titlebar
from .theme import STYLE


class AppMessageBox(QMessageBox):
    def __init__(self, parent):
        super().__init__(parent)
        palette = self.palette()
        for role, color in (
            (QPalette.ColorRole.Window, "#FFFFFF"),
            (QPalette.ColorRole.WindowText, "#17243B"),
            (QPalette.ColorRole.Base, "#F7F9FC"),
            (QPalette.ColorRole.Text, "#17243B"),
            (QPalette.ColorRole.Button, "#FFFFFF"),
            (QPalette.ColorRole.ButtonText, "#17243B"),
        ):
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setStyleSheet(STYLE + """
            QMessageBox { background: white; }
            QMessageBox QLabel { color: #17243B; }
            QMessageBox QLabel#qt_msgbox_label { font-size: 16px; font-weight: 600; }
            QMessageBox QLabel#qt_msgbox_informativelabel { color: #626D7D; font-size: 13px; }
            QMessageBox QPushButton { min-width: 76px; }
            QMessageBox QTextEdit { background: #F7F9FC; color: #17243B;
                border: 1px solid #D8E0EC; border-radius: 6px; padding: 8px; }
        """)

    def setDetailedText(self, text):
        super().setDetailedText(text)
        for button in self.buttons():
            if self.buttonRole(button) == QMessageBox.ButtonRole.ActionRole:
                button.setText("展开详情")
                button.clicked.connect(lambda checked=False, button=button: button.setText(
                    "收起详情" if self.findChild(QTextEdit).isVisible() else "展开详情"))

    def showEvent(self, event):
        for button in self.buttons():
            button.style().unpolish(button)
            button.style().polish(button)
        super().showEvent(event)
        set_light_titlebar(self)


def confirm_action(parent, title, message, details, action, cancel_text="取消"):
    box = AppMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setInformativeText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
    confirm = box.button(QMessageBox.StandardButton.Yes)
    confirm.setText(action)
    confirm.setObjectName("primary")
    box.button(QMessageBox.StandardButton.Cancel).setText(cancel_text)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    box.setEscapeButton(QMessageBox.StandardButton.Cancel)
    return box.exec() == QMessageBox.StandardButton.Yes


def show_recovery_error(parent, details):
    box = AppMessageBox(parent)
    box.setWindowTitle("暂时无法安全恢复")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText("恢复记录或文件状态无法核实。")
    box.setInformativeText("应用不会自动改动这些文件。改名和撤销已暂停；排除冲突后重新打开应用可再次核验。")
    box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.button(QMessageBox.StandardButton.Ok).setText("知道了")
    box.exec()


def show_details(parent, result):
    if not result or not result.errors:
        return
    box = AppMessageBox(parent)
    box.setWindowTitle("文件操作详情")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(result.message)
    box.setInformativeText("展开详情查看完整路径与原因。处理后可刷新预览或重试恢复。")
    box.setDetailedText("\n\n".join(result.errors))
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.button(QMessageBox.StandardButton.Ok).setText("关闭")
    box.exec()
