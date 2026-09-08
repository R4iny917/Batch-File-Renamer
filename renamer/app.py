import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QThread, Qt, QTranslator
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .core import Rules, build_preview, path_key
from .operations import RenameSession, Result


STYLE = """
QMainWindow, QWidget#content { background: #F2F5F7; color: #182D3B; }
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; }
QLabel { color: #182D3B; background: transparent; }
QLabel#title { font-size: 27px; font-weight: 700; }
QLabel#subtitle, QLabel#hint { color: #637783; }
QLabel#section { font-weight: 700; font-size: 14px; }
QLabel#status { padding: 12px 14px; background: #E1ECEF; border-radius: 6px; }
QFrame#rules { background: #FFFFFF; border: 1px solid #D6E0E5; border-radius: 8px; }
QLineEdit, QSpinBox { background: #FAFCFD; color: #182D3B; border: 1px solid #BCCBD4;
    border-radius: 5px; min-height: 30px; padding: 2px 9px; selection-background-color: #136F7A; }
QLineEdit:focus, QSpinBox:focus { border: 2px solid #136F7A; }
QPushButton { background: #FFFFFF; color: #243D4B; border: 1px solid #BCCBD4;
    border-radius: 5px; padding: 9px 17px; font-weight: 600; }
QPushButton:hover { background: #EAF1F4; border-color: #738F9F; }
QPushButton:focus { border: 2px solid #136F7A; }
QPushButton:disabled { color: #94A2AA; background: #EDF1F3; border-color: #D8E0E5; }
QPushButton#primary { background: #136F7A; color: #FFFFFF; border-color: #136F7A; }
QPushButton#primary:hover { background: #0E5861; }
QPushButton#primary:disabled { background: #ACBFC3; border-color: #ACBFC3; color: #F5F8F9; }
QPushButton#recovery { color: #A13337; border-color: #C98689; }
QTableWidget { background: #FFFFFF; alternate-background-color: #F8FAFB; color: #182D3B;
    border: 1px solid #D6E0E5; border-radius: 6px; gridline-color: #E8EEF1;
    selection-background-color: #D1E7EC; selection-color: #123B46; }
QHeaderView::section { background: #E7EEF2; color: #3C5564; border: none;
    border-bottom: 1px solid #CEDAE1; padding: 12px 10px; font-weight: 600; }
QCheckBox { color: #243D4B; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QToolTip { background: #FFFFFF; color: #182D3B; border: 1px solid #BCCBD4; padding: 6px; }
"""


class Worker(QThread):
    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
        self.result = None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as exc:
            self.result = Result(False, "操作发生异常，请检查文件实际状态", [repr(exc)])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批量改名工具")
        self.resize(1120, 780)
        self.setMinimumSize(880, 660)
        self.setStyleSheet(STYLE)
        self.paths = []
        self.rows = []
        self.session = RenameSession()
        self.busy = False
        self.worker = None
        self.last_result = None
        self.content = QWidget(objectName="content")
        self.setCentralWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(16)

        heading = QHBoxLayout()
        text = QVBoxLayout()
        text.addWidget(QLabel("批量改名", objectName="title"))
        text.addWidget(QLabel("先看清每一个新名字，再统一改名。", objectName="subtitle"))
        heading.addLayout(text)
        heading.addStretch()
        self.add_button = QPushButton("添加文件")
        self.add_button.clicked.connect(self.choose_files)
        heading.addWidget(self.add_button)
        layout.addLayout(heading)

        panel = QFrame(objectName="rules")
        grid = QGridLayout(panel)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.addWidget(QLabel("改名规则", objectName="section"), 0, 0, 1, 4)
        self.find = QLineEdit(placeholderText="要替换的文字")
        self.replacement = QLineEdit(placeholderText="留空则删除匹配文字")
        self.prefix = QLineEdit(placeholderText="例如：旅行_")
        self.suffix = QLineEdit(placeholderText="例如：_精选")
        for column, (label, field) in enumerate([
            ("查找", self.find), ("替换为", self.replacement),
            ("前缀", self.prefix), ("后缀", self.suffix),
        ]):
            caption = QLabel(label)
            caption.setBuddy(field)
            grid.addWidget(caption, 1, column)
            grid.addWidget(field, 2, column)
            grid.setColumnStretch(column, 1)
            field.textChanged.connect(self.refresh_preview)
        number_line = QHBoxLayout()
        number_line.setSpacing(12)
        self.numbering = QCheckBox("追加编号")
        self.start = QSpinBox()
        self.start.setRange(0, 2_000_000_000)
        self.start.setValue(1)
        self.start.setFixedWidth(120)
        self.start.setAccessibleName("起始编号")
        self.digits = QSpinBox()
        self.digits.setRange(1, 8)
        self.digits.setValue(3)
        self.digits.setFixedWidth(80)
        self.digits.setAccessibleName("编号最少位数")
        number_line.addWidget(self.numbering)
        number_line.addWidget(QLabel("起始值"))
        number_line.addWidget(self.start)
        number_line.addWidget(QLabel("位数"))
        number_line.addWidget(self.digits)
        number_line.addWidget(QLabel("例：文件名_001.jpg", objectName="hint"))
        number_line.addStretch()
        reset = QPushButton("重置规则")
        reset.clicked.connect(self.reset_rules)
        number_line.addWidget(reset)
        grid.addLayout(number_line, 3, 0, 1, 4)
        hint = QLabel("按表格顺序编号 · 保留最后一个扩展名 · 仅在原目录内改名", objectName="hint")
        grid.addWidget(hint, 4, 0, 1, 4)
        self.numbering.toggled.connect(self.refresh_preview)
        self.start.valueChanged.connect(self.refresh_preview)
        self.digits.valueChanged.connect(self.refresh_preview)
        layout.addWidget(panel)

        table_actions = QHBoxLayout()
        self.count = QLabel("文件预览", objectName="section")
        table_actions.addWidget(self.count)
        table_actions.addStretch()
        refresh = QPushButton("刷新预览")
        refresh.clicked.connect(self.refresh_preview)
        table_actions.addWidget(refresh)
        self.remove_button = QPushButton("移除选中")
        self.remove_button.clicked.connect(self.remove_selected)
        table_actions.addWidget(self.remove_button)
        self.clear_button = QPushButton("清空列表")
        self.clear_button.clicked.connect(lambda: self.set_paths([]))
        table_actions.addWidget(self.clear_button)
        layout.addLayout(table_actions)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["原文件名", "新文件名", "所在目录", "状态"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        header = self.table.horizontalHeader()
        for column in (0, 1, 2):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 170)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        layout.addWidget(self.table, 1)
        self.empty = QLabel("列表还是空的。点击右上角“添加文件”，开始预览。", objectName="hint")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.status = QLabel("添加文件后，设置规则即可看到新名字。", objectName="status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("撤销仅在本次打开期间有效", objectName="hint"))
        footer.addStretch()
        self.details_button = QPushButton("查看错误详情")
        self.details_button.clicked.connect(self.show_details)
        footer.addWidget(self.details_button)
        self.recover_button = QPushButton("重试恢复", objectName="recovery")
        self.recover_button.clicked.connect(self.request_recovery)
        footer.addWidget(self.recover_button)
        self.undo_button = QPushButton("撤销上次改名")
        self.undo_button.clicked.connect(self.request_undo)
        footer.addWidget(self.undo_button)
        self.execute_button = QPushButton("执行改名", objectName="primary")
        self.execute_button.clicked.connect(self.request_execute)
        footer.addWidget(self.execute_button)
        layout.addLayout(footer)
        self.refresh_preview()

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择需要改名的文件", "", "所有文件 (*)")
        self.add_paths(files)

    def add_paths(self, paths):
        seen = {path_key(path) for path in self.paths}
        for supplied in paths:
            path = Path(supplied).absolute()
            path = path.parent.resolve() / path.name
            if path_key(path) not in seen:
                seen.add(path_key(path))
                self.paths.append(path)
        self.refresh_preview()

    def set_paths(self, paths):
        self.paths = paths
        self.refresh_preview()

    def remove_selected(self):
        selected = {index.row() for index in self.table.selectionModel().selectedRows()}
        self.set_paths([p for i, p in enumerate(self.paths) if i not in selected])

    def reset_rules(self):
        fields = [self.find, self.replacement, self.prefix, self.suffix, self.numbering, self.start, self.digits]
        for field in fields:
            field.blockSignals(True)
        for field in fields[:4]:
            field.clear()
        self.numbering.setChecked(False)
        self.start.setValue(1)
        self.digits.setValue(3)
        for field in fields:
            field.blockSignals(False)
        self.refresh_preview()

    def refresh_preview(self):
        rules = Rules(self.find.text(), self.replacement.text(), self.prefix.text(), self.suffix.text(),
                      self.numbering.isChecked(), self.start.value(), self.digits.value())
        self.rows = build_preview(self.paths, rules)
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            state = row.error or ("待改名" if row.changed else "无需修改")
            for column, value in enumerate([row.source.name, row.target.name, str(row.source.parent), state]):
                item = QTableWidgetItem(value)
                item.setToolTip(value if column >= 2 else str(row.source if column == 0 else row.target))
                if column == 1 and row.changed:
                    item.setForeground(QColor("#136F7A"))
                    item.setBackground(QColor("#EDF7F7"))
                if column == 3 and row.error:
                    item.setForeground(QColor("#B03840"))
                self.table.setItem(index, column, item)
        total = len(self.rows)
        conflicts = sum(bool(row.error) for row in self.rows)
        changed = sum(row.changed and not row.error for row in self.rows)
        self.count.setText(f"文件预览   {total} 个文件 · {changed} 个待改名 · {conflicts} 个错误")
        self.empty.setVisible(not total)
        if not total:
            self.status.setText("添加文件后，设置规则即可看到新名字。")
        elif conflicts:
            self.status.setText(f"有 {conflicts} 个文件需要处理，请查看状态列，修改规则或移除对应行。")
        elif changed:
            self.status.setText(f"预览已更新。确认右侧的新名字后，可执行 {changed} 个文件的改名。")
        else:
            self.status.setText("当前规则没有改变文件名。可以设置替换、前后缀或追加编号。")
        self.start.setEnabled(self.numbering.isChecked())
        self.digits.setEnabled(self.numbering.isChecked())
        self.update_buttons()

    def update_buttons(self):
        if not hasattr(self, "execute_button"):
            return
        pending = bool(self.session.pending)
        self.execute_button.setEnabled(not self.busy and not pending and any(r.changed for r in self.rows)
                                       and not any(r.error for r in self.rows))
        self.undo_button.setEnabled(not self.busy and not pending and bool(self.session.history))
        self.recover_button.setVisible(pending)
        self.recover_button.setEnabled(not self.busy)
        self.details_button.setVisible(bool(self.last_result and self.last_result.errors))
        self.remove_button.setEnabled(bool(self.table.selectionModel().selectedRows()))
        self.clear_button.setEnabled(bool(self.paths))

    def request_execute(self):
        if not self.execute_button.isEnabled():
            return
        count = sum(row.changed for row in self.rows)
        answer = QMessageBox.question(self, "确认批量改名", f"按当前预览改名 {count} 个文件？\n\n不会覆盖已有文件。成功后可在本次打开期间撤销。",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            rows = list(self.rows)
            self.start_operation(lambda: self.session.execute(rows), "execute")

    def request_undo(self):
        answer = QMessageBox.question(self, "确认撤销", f"恢复上次改名的 {len(self.session.history)} 个文件？\n范围包含已从列表移除的文件。",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.start_operation(self.session.undo, "undo")

    def request_recovery(self):
        answer = QMessageBox.question(self, "确认恢复", f"尝试恢复 {len(self.session.pending)} 个未恢复的文件？\n请先处理错误详情中的文件占用或外部修改。",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.start_operation(self.session.recover, "recover")

    def start_operation(self, operation, action):
        if self.busy:
            return
        self.busy = True
        self.action = action
        self.content.setEnabled(False)
        self.status.setText("正在检查并处理文件，请稍候…")
        self.worker = Worker(operation, self)
        self.worker.finished.connect(self.finish_operation)
        self.worker.start()

    def finish_operation(self):
        result = self.worker.result
        self.worker.deleteLater()
        self.worker = None
        self.last_result = result
        mapping = {path_key(move.source): move.target for move in result.moves}
        self.paths = [mapping.get(path_key(path), path) for path in self.paths]
        self.busy = False
        self.content.setEnabled(True)
        if result.ok and self.action == "execute" and result.moves:
            self.reset_rules()
        else:
            self.refresh_preview()
        self.status.setText(result.message)
        self.update_buttons()
        if result.errors:
            self.show_details()

    def show_details(self):
        if not self.last_result or not self.last_result.errors:
            return
        box = QMessageBox(self)
        box.setWindowTitle("文件操作详情")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(self.last_result.message)
        box.setInformativeText("展开详情查看完整路径与原因。处理后可刷新预览或重试恢复。")
        box.setDetailedText("\n\n".join(self.last_result.errors))
        box.exec()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            return
        if self.session.pending:
            answer = QMessageBox.question(self, "仍有文件未恢复", "关闭后会丢失本次恢复记录。建议先查看错误详情并完成恢复。\n仍要关闭吗？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    translator = QTranslator(app)
    if translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    window = MainWindow()
    window.show()
    return app.exec()
