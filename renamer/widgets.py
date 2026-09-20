from PySide6.QtCore import QByteArray, QRectF, Qt, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QLinearGradient, QPalette
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractSpinBox, QCheckBox, QHBoxLayout, QComboBox, QPushButton,
    QSpinBox, QStyledItemDelegate, QStyle, QWidget, QSizePolicy, QScrollArea, QLineEdit, QMessageBox, QTextEdit,
)


STYLE = """
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 14px; color: #17243B; }
QMainWindow, QWidget#content { background: #F7F9FC; }
QLabel { background: transparent; }
QLabel#title { font-size: 21px; font-weight: 700; }
QLabel#section { font-size: 15px; font-weight: 600; }
QLabel#hint, QLabel#subtitle { color: #626D7D; font-size: 13px; }
QLabel#example { color: #2864F5; font-weight: 600; }
QFrame#sample { background: #F8FAFC; border: none; border-top: 1px solid #EDF0F5; border-radius: 0; }
QLabel#subtitle { font-size: 14px; }
QFrame#panel { background: white; border: 1px solid #E1E7F0; border-radius: 10px; }
QFrame#divider { background: #EDF0F5; border: none; min-height: 1px; max-height: 1px; }
QLineEdit, QSpinBox { background: #FBFCFE; border: 1px solid #D8E0EC; border-radius: 7px;
    min-height: 36px; padding: 0 11px; selection-background-color: #3867ED; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #3867ED; background: white; }
QWidget#rulesContent, QScrollArea#rulesScroll { background: white; border: none; }
QWidget#rulesContent QLineEdit { min-height: 34px; border-radius: 6px; }
QComboBox { background: #FBFCFE; border: 1px solid #D8E0EC; border-radius: 6px; min-height: 36px; padding-left: 10px; }
QComboBox:focus { border-color: #3867ED; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #E9F0FF; selection-color: #2864F5; }

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
        import sys
        if sys.platform == "win32":
            import ctypes
            light = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(int(self.winId())), 20, ctypes.byref(light), ctypes.sizeof(light))


class FilenameEdit(QLineEdit):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setReadOnly(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)

    def focusOutEvent(self, event):
        start, end = self.selectionStart(), self.selectionEnd()
        super().focusOutEvent(event)
        if start >= 0:
            self.setSelection(start, end - start)


class ScrollEdges(QWidget):
    def __init__(self, scroll):
        super().__init__(scroll.viewport())
        self.scroll = scroll
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        bar = self.scroll.verticalScrollBar()
        painter = QPainter(self)
        depth = min(24, self.height() // 4)
        for distance, edge, direction in (
            (bar.value() - bar.minimum(), 0, 1),
            (bar.maximum() - bar.value(), self.height(), -1),
        ):
            if distance <= 0 or depth <= 0:
                continue
            gradient = QLinearGradient(0, edge, 0, edge + direction * depth)
            opacity = min(1.0, distance / depth)
            gradient.setColorAt(0, QColor(255, 255, 255, round(255 * opacity)))
            gradient.setColorAt(0.35, QColor(255, 255, 255, round(210 * opacity)))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            painter.fillRect(QRectF(0, min(edge, edge + direction * depth), self.width(), depth), gradient)


class RulesScrollArea(QScrollArea):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.edges = ScrollEdges(self)
        self.verticalScrollBar().valueChanged.connect(self.update_edges)
        self.verticalScrollBar().rangeChanged.connect(self.update_edges)

    def update_edges(self, *args):
        self.edges.setGeometry(self.viewport().rect())
        self.edges.raise_()
        self.edges.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_edges()


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
        self.editor.setCursor(Qt.CursorShape.IBeamCursor)
        self.editor.setRange(0, 2_000_000_000)
        self.editor.setMinimumWidth(0)
        self.editor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.editor.setValue(1)
        self.editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor.setAccessibleName("起始编号")
        for button in (self.minus, self.plus):
            button.setFixedSize(26, 36)
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


class DigitSelector(QComboBox):
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setAccessibleName("编号位数")
        for number in range(1, 9):
            self.addItem(f"{number} 位", number)
        self.setCurrentIndex(2)
        self.currentIndexChanged.connect(lambda: self.valueChanged.emit(self.value()))

    def value(self):
        return self.currentData()

    def setValue(self, value):
        self.setCurrentIndex(max(1, min(8, value)) - 1)


class Collapsible(QWidget):
    def __init__(self):
        super().__init__()
        self.expanded = False
        self.setMaximumHeight(0)
        self.setMinimumHeight(0)
        self.setEnabled(False)
        self.animation = QPropertyAnimation(self, b"maximumHeight", self)
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def setExpanded(self, expanded):
        if expanded == self.expanded:
            return
        self.expanded = expanded
        self.setEnabled(expanded)
        self.animation.stop()
        self.animation.setStartValue(self.maximumHeight())
        self.animation.setEndValue(self.layout().sizeHint().height() if expanded else 0)
        self.animation.start()


class Toggle(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setAccessibleName("追加编号")
        self.setFixedSize(46, 30)
        self.keyboard_focus = False
        self._progress = 0.0
        self.animation = QPropertyAnimation(self, b"progress", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self.sync_state)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @Property(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = value
        self.update()

    def sync_state(self):
        target = float(self.isChecked())
        if self.animation.endValue() == target and self.animation.state() == QPropertyAnimation.State.Running:
            return
        self.animation.stop()
        self.animation.setStartValue(self.progress)
        self.animation.setEndValue(target)
        self.animation.start()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (Qt.FocusReason.TabFocusReason,
                                                 Qt.FocusReason.BacktabFocusReason,
                                                 Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        self.keyboard_focus = False
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        off, on = QColor("#CBD5E3"), QColor("#2864F5")
        painter.setBrush(QColor(*[round(a + (b - a) * self.progress) for a, b in
                                 zip(off.getRgb()[:3], on.getRgb()[:3])]))
        painter.drawRoundedRect(QRectF(3, 4, 40, 22), 11, 11)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(5 + 18 * self.progress, 6, 18, 18))
        if self.hasFocus() and self.keyboard_focus:
            painter.setPen(QColor("#2864F5"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0.5, 1.5, 45, 27), 13.5, 13.5)


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
