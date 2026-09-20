from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ..core import Rules
from .controls import HeadingLabel, NumberStepper, DigitSelector, Toggle, Collapsible, RulesScrollArea
from .theme import line_icon


class RulesPanel(QFrame):
    rules_changed = Signal(object)

    def __init__(self):
        super().__init__(objectName="panel")
        self.setFixedWidth(306)
        panel_layout = QVBoxLayout(self)
        panel_layout.setContentsMargins(1, 1, 1, 1)
        panel_layout.setSpacing(0)
        rules = self._create_scroll()
        panel_layout.addLayout(self._create_heading())
        panel_layout.addWidget(self.rules_scroll, 1)
        self._add_text_rules(rules)
        self._add_numbering(rules)
        rules.addSpacing(24)
        rules.addStretch()
        rules.addWidget(self._create_sample())
        for field in (self.find, self.replacement, self.prefix, self.suffix):
            field.textChanged.connect(self._emit_rules)
        self.numbering.toggled.connect(self._emit_rules)
        self.start.valueChanged.connect(self._emit_rules)
        self.digits.valueChanged.connect(self._emit_rules)
        self._sync_numbering()

    def _create_scroll(self):
        rules_scroll = RulesScrollArea(objectName="rulesScroll")
        self.rules_scroll = rules_scroll
        rules_scroll.setWidgetResizable(True)
        rules_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rules_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rules_scroll.edges.hide()
        rules_content = QWidget(objectName="rulesContent")
        rules_scroll.setWidget(rules_content)
        rules = QVBoxLayout(rules_content)
        rules.setContentsMargins(0, 8, 0, 0)
        rules.setSpacing(0)
        return rules

    def _create_heading(self):
        rule_heading = QHBoxLayout()
        rule_heading.setContentsMargins(16, 16, 16, 16)
        rule_heading.addWidget(HeadingLabel("改名规则", objectName="rulesHeading"))
        rule_heading.addStretch()
        reset = QPushButton("重置", objectName="quiet")
        reset.setFixedHeight(26)
        reset.setIcon(line_icon("refresh"))
        reset.clicked.connect(self.reset)
        rule_heading.addWidget(reset)
        return rule_heading

    def _add_text_rules(self, rules):
        content = QWidget()
        rules.addWidget(content)
        rules = QVBoxLayout(content)
        rules.setContentsMargins(16, 0, 16, 0)
        rules.setSpacing(0)
        self.find = QLineEdit(placeholderText="要替换的文字")
        self.replacement = QLineEdit(placeholderText="留空则删除匹配文字")
        self.prefix = QLineEdit(placeholderText="例如：旅行_")
        self.suffix = QLineEdit(placeholderText="例如：_精选")
        rules.addWidget(HeadingLabel("查找与替换", objectName="groupTitle"))
        for title, field in [("查找", self.find), ("替换", self.replacement)]:
            rules.addSpacing(10)
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(title)
            label.setFixedWidth(44)
            label.setBuddy(field)
            row.addWidget(label)
            row.addWidget(field, 1)
            rules.addLayout(row)
        rules.addSpacing(9)
        helper = QLabel("替换留空时，删除匹配的文字", objectName="hint")
        helper.setMinimumHeight(21)
        rules.addWidget(helper)
        rules.addSpacing(16)
        rules.addWidget(QFrame(objectName="divider"))
        rules.addSpacing(12)
        rules.addWidget(HeadingLabel("前缀与后缀", objectName="groupTitle"))
        for title, field in [("前缀", self.prefix), ("后缀", self.suffix)]:
            rules.addSpacing(10)
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(title)
            label.setFixedWidth(44)
            label.setBuddy(field)
            row.addWidget(label)
            row.addWidget(field, 1)
            rules.addLayout(row)
        rules.addSpacing(16)
        rules.addWidget(QFrame(objectName="divider"))
        rules.addSpacing(12)

    def _add_numbering(self, rules):
        content = QWidget()
        rules.addWidget(content)
        rules = QVBoxLayout(content)
        rules.setContentsMargins(16, 0, 16, 0)
        rules.setSpacing(0)
        numbering_row = QHBoxLayout()
        numbering_labels = QVBoxLayout()
        numbering_labels.setSpacing(4)
        numbering_labels.addWidget(HeadingLabel("自动编号", objectName="groupTitle"))
        numbering_labels.addWidget(QLabel("在文件名末尾添加序号", objectName="hint"))
        numbering_row.addLayout(numbering_labels, 1)
        self.numbering = Toggle()
        numbering_row.addWidget(self.numbering)
        rules.addLayout(numbering_row)
        self.number_settings = Collapsible()
        settings_layout = QVBoxLayout(self.number_settings)
        settings_layout.setContentsMargins(0, 16, 0, 0)
        settings_layout.setSpacing(10)
        pair = QGridLayout()
        pair.setHorizontalSpacing(12)
        pair.setVerticalSpacing(6)
        self.start = NumberStepper()
        self.digits = DigitSelector()
        for col, (title, field) in enumerate([("起始编号", self.start), ("编号位数", self.digits)]):
            label = QLabel(title, objectName="hint")
            label.setBuddy(self.start.editor if col == 0 else field)
            pair.addWidget(label, 0, col)
            pair.addWidget(field, 1, col)
            pair.setColumnStretch(col, 1)
        settings_layout.addLayout(pair)
        settings_layout.addWidget(QLabel("按文件列表顺序递增，不足位数补零", objectName="hint"))
        rules.addWidget(self.number_settings)

    def _create_sample(self):
        sample_panel = QFrame(objectName="sample")
        sample_layout = QVBoxLayout(sample_panel)
        sample_layout.setContentsMargins(16, 14, 16, 14)
        sample_layout.setSpacing(6)
        sample_layout.addWidget(QLabel("命名预览", objectName="sampleTitle"))
        self.example = QLabel("", objectName="example")
        self.example.setWordWrap(True)
        self.example.setMaximumHeight(42)
        self.example.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sample_layout.addWidget(self.example)
        sample_layout.addWidget(QLabel("保留扩展名 · 仅在原目录改名", objectName="hint"))
        return sample_panel

    def rules(self) -> Rules:
        return Rules(self.find.text(), self.replacement.text(), self.prefix.text(), self.suffix.text(),
                     self.numbering.isChecked(), self.start.value(), self.digits.value())

    def set_rules(self, rules: Rules):
        fields = (self.find, self.replacement, self.prefix, self.suffix, self.numbering, self.start, self.digits)
        blockers = [QSignalBlocker(field) for field in fields]
        for field, value in zip(fields[:4], (rules.find, rules.replace, rules.prefix, rules.suffix)):
            field.setText(value)
        self.numbering.setChecked(rules.numbering)
        self.start.setValue(rules.start)
        self.digits.setValue(rules.digits)
        del blockers
        self._sync_numbering()

    def reset(self):
        self.set_rules(Rules())
        self.rules_changed.emit(self.rules())

    def fill_find(self, text: str):
        self.find.setText(text)
        self.find.setFocus()
        self.find.selectAll()

    def show_example(self, text: str):
        self.example.setText(text)
        self.example.setToolTip(text)

    def _emit_rules(self):
        self._sync_numbering()
        self.rules_changed.emit(self.rules())

    def _sync_numbering(self):
        enabled = self.numbering.isChecked()
        self.number_settings.setExpanded(enabled)
        self.numbering.sync_state()
        self.start.setEnabled(enabled)
        self.digits.setEnabled(enabled)
