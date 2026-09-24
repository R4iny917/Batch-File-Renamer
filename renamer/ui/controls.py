from PySide6.QtCore import QRectF, Qt, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractSpinBox, QCheckBox, QHBoxLayout, QComboBox, QPushButton,
    QSpinBox, QWidget, QSizePolicy, QScrollArea, QLineEdit, QLabel,
)


class HeadingLabel(QLabel):
    def __init__(self, text, **kwargs):
        super().__init__(text, **kwargs)
        self.setFont(QFontDatabase.font("Microsoft YaHei", "Bold", 10))


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
        self.setFixedSize(36, 21)
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
        off, on = QColor("#BCC5D1"), QColor("#2864F5")
        painter.setBrush(QColor(*[round(a + (b - a) * self.progress) for a, b in
                                 zip(off.getRgb()[:3], on.getRgb()[:3])]))
        painter.drawRoundedRect(QRectF(0, 0, 36, 21), 10.5, 10.5)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(3 + 15 * self.progress, 3, 15, 15))
        if self.hasFocus() and self.keyboard_focus:
            painter.setPen(QColor("#2864F5"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0.5, 0.5, 35, 20), 10, 10)
