import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QThread, Qt, QTranslator
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QScrollArea, QSizePolicy,
)

from .core import Rules, build_preview, path_key
from .operations import RenameSession, Result


from .widgets import STYLE, NumberStepper, DigitSelector, Toggle, PreviewDelegate, line_icon


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
        self.setWindowTitle("Batch File Renamer")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "app.svg")))
        self.resize(1200, 790)
        self.setMinimumSize(980, 650)
        self.setStyleSheet(STYLE)
        self.paths, self.rows = [], []
        self.session = RenameSession()
        self.busy = False
        self.worker = None
        self.last_result = None
        self.content = QWidget(objectName="content")
        self.setCentralWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(22)
        heading = QHBoxLayout()
        heading.addWidget(QLabel("批量改名", objectName="title"))
        heading.addSpacing(8)
        heading.addWidget(QLabel("每一个新名字，都先预览", objectName="subtitle"))
        heading.addStretch()
        self.add_button = QPushButton("＋  添加文件", objectName="primary")
        self.add_button.clicked.connect(self.choose_files)
        heading.addWidget(self.add_button)
        layout.addLayout(heading)

        body = QHBoxLayout()
        body.setSpacing(18)
        rules_scroll = QScrollArea()
        rules_scroll.setWidgetResizable(True)
        rules_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rules_scroll.setFixedWidth(334)
        rules_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        panel = QFrame(objectName="panel")
        rules_scroll.setWidget(panel)
        rules = QVBoxLayout(panel)
        rules.setContentsMargins(20, 18, 20, 20)
        rules.setSpacing(9)
        rule_heading = QHBoxLayout()
        rule_heading.addWidget(QLabel("改名规则", objectName="section"))
        rule_heading.addStretch()
        reset = QPushButton("重置", objectName="quiet")
        reset.setIcon(line_icon("refresh"))
        reset.clicked.connect(self.reset_rules)
        rule_heading.addWidget(reset)
        rules.addLayout(rule_heading)
        self.find = QLineEdit(placeholderText="要替换的文字")
        self.replacement = QLineEdit(placeholderText="留空则删除匹配文字")
        self.prefix = QLineEdit(placeholderText="例如：旅行_")
        self.suffix = QLineEdit(placeholderText="例如：_精选")
        for title, field in [("查找", self.find), ("替换为", self.replacement)]:
            label = QLabel(title)
            label.setBuddy(field)
            rules.addWidget(label)
            rules.addWidget(field)
        pair = QGridLayout()
        pair.setHorizontalSpacing(12)
        for col, (title, field) in enumerate([("前缀（可选）", self.prefix), ("后缀（可选）", self.suffix)]):
            label = QLabel(title)
            label.setBuddy(field)
            pair.addWidget(label, 0, col)
            pair.addWidget(field, 1, col)
        rules.addLayout(pair)
        rules.addSpacing(4)
        rules.addWidget(QFrame(objectName="divider"))
        numbering_row = QHBoxLayout()
        numbering_row.addWidget(QLabel("追加编号"))
        numbering_row.addStretch()
        self.numbering = Toggle()
        numbering_row.addWidget(self.numbering)
        rules.addLayout(numbering_row)
        rules.addWidget(QLabel("在文件名末尾添加递增编号", objectName="hint"))
        self.start = NumberStepper()
        self.digits = DigitSelector()
        for title, field in [("起始值", self.start), ("编号位数", self.digits)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            row.addStretch()
            field.setFixedWidth(214)
            row.addWidget(field)
            rules.addLayout(row)
        self.example = QLabel("", objectName="hint")
        self.example.setWordWrap(True)
        rules.addWidget(self.example)
        rules.addStretch()
        rules.addSpacing(10)
        rules.addWidget(QLabel("保留扩展名（如 .jpg、.png）", objectName="hint"))
        rules.addWidget(QLabel("仅在原目录内改名", objectName="hint"))
        body.addWidget(rules_scroll)

        preview = QFrame(objectName="panel")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(1, 12, 1, 8)
        preview_layout.setSpacing(8)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(18, 0, 12, 2)
        toolbar.addWidget(QLabel("文件预览", objectName="section"))
        self.count = QLabel("", objectName="hint")
        toolbar.addWidget(self.count)
        toolbar.addStretch()
        refresh = QPushButton("刷新", objectName="quiet")
        refresh.setIcon(line_icon("refresh"))
        refresh.clicked.connect(self.refresh_preview)
        toolbar.addWidget(refresh)
        self.remove_button = QPushButton("移除选中", objectName="quiet")
        self.remove_button.setIcon(line_icon("trash"))
        self.remove_button.clicked.connect(self.remove_selected)
        toolbar.addWidget(self.remove_button)
        self.clear_button = QPushButton("清空", objectName="quiet")
        self.clear_button.setIcon(line_icon("trash"))
        self.clear_button.clicked.connect(lambda: self.set_paths([]))
        toolbar.addWidget(self.clear_button)
        preview_layout.addLayout(toolbar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["原文件名", "新文件名", "所在目录", "状态"])
        self.table.setColumnHidden(2, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.setItemDelegate(PreviewDelegate(self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(68)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 114)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        preview_layout.addWidget(self.table, 1)
        self.empty = QLabel("添加文件，预览每一个新名字", objectName="hint", parent=self.table.viewport())
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout = QVBoxLayout(self.table.viewport())
        empty_layout.addWidget(self.empty)
        self.empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        body.addWidget(preview, 1)
        layout.addLayout(body, 1)
        layout.addWidget(QFrame(objectName="divider"))
        footer = QHBoxLayout()
        status_group = QVBoxLayout()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        status_group.addWidget(self.status)
        status_group.addWidget(QLabel("撤销仅在本次打开期间有效", objectName="hint"))
        footer.addLayout(status_group, 1)
        self.details_button = QPushButton("错误详情", objectName="quiet")
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
        for field in (self.find, self.replacement, self.prefix, self.suffix):
            field.textChanged.connect(self.refresh_preview)
        self.numbering.toggled.connect(self.refresh_preview)
        self.start.valueChanged.connect(self.refresh_preview)
        self.digits.valueChanged.connect(self.refresh_preview)
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
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(row.source.parent))
                elif column == 1:
                    item.setData(Qt.ItemDataRole.UserRole, row.changed)
                elif column == 3:
                    item.setData(Qt.ItemDataRole.UserRole, bool(row.error))
                self.table.setItem(index, column, item)
        total = len(self.rows)
        conflicts = sum(bool(row.error) for row in self.rows)
        changed = sum(row.changed and not row.error for row in self.rows)
        self.count.setText(f"{total} 个文件")
        self.execute_button.setText(f"执行改名（{changed}）" if changed else "执行改名")
        sample = self.rows[0].target.name if self.rows and not self.rows[0].error else "文件名_001.jpg"
        self.example.setText(f"示例：{sample}")
        self.empty.setVisible(not total)
        self.status.setStyleSheet("color: #149447; font-weight: 600;" if changed and not conflicts else "color: #71809A;")
        if not total:
            self.status.setText("添加文件后，设置规则即可看到新名字。")
        elif conflicts:
            self.status.setText(f"有 {conflicts} 个文件需要处理，请查看状态列，修改规则或移除对应行。")
        elif changed:
            self.status.setText(f"{changed} 个文件可改名 · 无冲突")
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
        self.status.setStyleSheet("color: #149447;" if result.ok else "color: #B63B49;")
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
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BatchFileRenamer.Desktop")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    translator = QTranslator(app)
    if translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    window = MainWindow()
    window.show()
    if sys.platform == "win32":
        light_titlebar = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(int(window.winId())), 20,
                                                  ctypes.byref(light_titlebar), ctypes.sizeof(light_titlebar))
    return app.exec()
