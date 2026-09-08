from PySide6.QtCore import QByteArray, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractSpinBox, QCheckBox, QHBoxLayout, QMenu, QPushButton,
    QSpinBox, QStyledItemDelegate, QStyle, QWidget,
)


STYLE = """
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #17243B; }
QMainWindow, QWidget#content { background: #F7F9FC; }
QLabel { background: transparent; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLabel#section { font-size: 19px; font-weight: 600; }
QLabel#hint, QLabel#subtitle { color: #7C889B; }
QLabel#subtitle { font-size: 14px; }
QFrame#panel { background: white; border: 1px solid #E1E7F0; border-radius: 10px; }
QFrame#divider { background: #EDF0F5; border: none; max-height: 1px; }
QLineEdit, QSpinBox { background: #FBFCFE; border: 1px solid #D8E0EC; border-radius: 7px;
    min-height: 36px; padding: 0 11px; selection-background-color: #3867ED; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #3867ED; background: white; }
QPushButton { background: white; border: 1px solid #D8E0EC; border-radius: 7px;
    padding: 10px 15px; font-weight: 500; }
QPushButton:hover { background: #F0F5FF; border-color: #B6C9F8; }
QPushButton:focus { border: 1px solid #3867ED; }
QPushButton:disabled { color: #A4AFBF; background: #F4F6F9; border-color: #E5EAF1; }
QPushButton#primary { background: #2864F5; color: white; border: 1px solid #2864F5; font-weight: 600; }
QPushButton#primary:hover { background: #2055DC; }
QPushButton#primary:disabled { background: #A4BAEB; border-color: #A4BAEB; color: white; }
QPushButton#quiet { background: transparent; border: 1px solid transparent; color: #647792; padding: 7px 9px; }
QPushButton#quiet:hover { background: #F0F5FF; color: #2864F5; }
QPushButton#quiet:disabled { color: #B4BFCC; }
QPushButton#recovery { color: #B63B49; }
QWidget#stepper, QWidget#segments { background: #F5F7FB; border: 1px solid #E1E7F0; border-radius: 7px; }
QWidget#stepper QSpinBox { border: none; background: white; border-radius: 0; padding: 0 2px; }
QPushButton#step { font-size: 20px; border: none; background: transparent; padding: 0; }
QPushButton#segment { border: 1px solid transparent; background: transparent; padding: 8px 9px; }
QPushButton#segment:checked { color: #2864F5; border: 1px solid #7FA2FB; background: #E9F0FF; }
QTableWidget { background: white; border: none; selection-background-color: #EDF3FF; selection-color: #17243B; }
QHeaderView::section { background: #F7F9FC; color: #71809A; border: none; padding: 14px 12px; font-weight: 600; }
QScrollBar:vertical { background: #F7F9FC; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #CCD5E3; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: white; border: 1px solid #D8E0EC; padding: 5px; }
QMenu::item { padding: 8px 24px; }
QMenu::item:selected { background: #E9F0FF; }
QToolTip { background: white; color: #17243B; border: 1px solid #D8E0EC; padding: 6px; }
"""


class NumberStepper(QWidget):
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__(objectName="stepper")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.minus = QPushButton("−", objectName="step")
        self.plus = QPushButton("+", objectName="step")
        self.minus.setAccessibleName("减小起始值")
        self.plus.setAccessibleName("增大起始值")
        self.editor = QSpinBox()
        self.editor.setRange(0, 2_000_000_000)
        self.editor.setValue(1)
        self.editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor.setAccessibleName("起始编号")
        for button in (self.minus, self.plus):
            button.setFixedSize(34, 38)
            button.setAutoRepeat(True)
        layout.addWidget(self.minus)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.plus)
        self.minus.clicked.connect(self.editor.stepDown)
        self.plus.clicked.connect(self.editor.stepUp)
        self.editor.valueChanged.connect(self.valueChanged.emit)

    def value(self):
        return self.editor.value()

    def setValue(self, value):
        self.editor.setValue(value)


class DigitSelector(QWidget):
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__(objectName="segments")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._value = 3
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.buttons = {}
        for number in (2, 3, 4):
            button = QPushButton(f"{number} 位", objectName="segment")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, n=number: self.setValue(n))
            self.buttons[number] = button
            layout.addWidget(button, 1)
        self.more = QPushButton("更多", objectName="segment")
        self.more.setCheckable(True)
        menu = QMenu(self.more)
        for number in (1, 5, 6, 7, 8):
            menu.addAction(f"{number} 位", lambda n=number: self.setValue(n))
        self.more.setMenu(menu)
        layout.addWidget(self.more, 1)
        self.setValue(3)

    def value(self):
        return self._value

    def setValue(self, value):
        value = max(1, min(8, value))
        changed = value != self._value
        self._value = value
        for number, button in self.buttons.items():
            button.setChecked(number == value)
        self.more.setChecked(value not in self.buttons)
        self.more.setText(f"{value} 位" if value not in self.buttons else "更多")
        if changed:
            self.valueChanged.emit(value)


class Toggle(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setAccessibleName("追加编号")
        self.setFixedSize(46, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2864F5" if self.isChecked() else "#CBD5E3"))
        painter.drawRoundedRect(QRectF(1, 3, 44, 24), 12, 12)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(24 if self.isChecked() else 4, 6, 18, 18))
        if self.hasFocus():
            painter.setPen(QColor("#2864F5"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0, 1, 45, 26), 13, 13)


def line_icon(name):
    paths = {
        "refresh": 'M20 7v5h-5M19 12a7 7 0 1 0-2 5',
        "trash": 'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7',
        "file": 'M6 2h8l5 5v15H6zM14 2v6h5',
    }
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{paths[name]}" fill="none" stroke="#71809A" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)


class PreviewDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
        self.file_icon = line_icon("file")

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.fillRect(rect, QColor("#EDF3FF" if selected else "#FFFFFF"))
        painter.setPen(QColor("#EEF1F6"))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        text_rect = rect.adjusted(16, 0, -12, 0)
        text = str(index.data() or "")
        painter.setFont(option.font)
        if index.column() == 0:
            self.file_icon.paint(painter, rect.left() + 13, rect.center().y() - 12, 24, 24)
            text_rect.adjust(32, 0, 0, 0)
            painter.setPen(QColor("#17243B"))
            painter.drawText(text_rect.adjusted(0, 0, 0, -19), Qt.AlignmentFlag.AlignVCenter,
                             option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()))
            painter.setPen(QColor("#8996AB"))
            small = QFont(option.font)
            small.setPointSizeF(max(8, small.pointSizeF() - 1))
            painter.setFont(small)
            path = str(index.data(Qt.ItemDataRole.UserRole) or "")
            painter.drawText(text_rect.adjusted(0, 23, 0, 0), Qt.AlignmentFlag.AlignVCenter,
                             painter.fontMetrics().elidedText(path, Qt.TextElideMode.ElideMiddle, text_rect.width()))
        elif index.column() == 3:
            error = bool(index.data(Qt.ItemDataRole.UserRole))
            badge = QRectF(text_rect.left(), rect.center().y() - 14, min(82, text_rect.width()), 28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFF0F0" if error else "#EDF4FF"))
            painter.drawRoundedRect(badge, 7, 7)
            painter.setPen(QColor("#B63B49" if error else "#2864F5"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "需处理" if error else text)
        else:
            painter.setPen(QColor("#2864F5" if index.data(Qt.ItemDataRole.UserRole) else "#71809A"))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter,
                             option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()))
        painter.restore()
