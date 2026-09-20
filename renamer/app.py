import os
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QThread, Qt, QTranslator
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QSizePolicy,
)

from .core import Rules, build_preview, path_key
from .operations import RenameSession, Result


from .widgets import STYLE, NumberStepper, DigitSelector, Toggle, Collapsible, PreviewDelegate, RulesScrollArea, FilenameEdit, AppMessageBox, line_icon


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
        self.setMinimumSize(760, 420)
        self.setStyleSheet(STYLE)
        self.paths, self.rows = [], []
        self.session = RenameSession()
        self.busy = False
        self.worker = None
        self.last_result = None
        self.content = QWidget(objectName="content")
        self.setCentralWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(14)
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
        body.setSpacing(14)
        panel = QFrame(objectName="panel")
        panel.setFixedWidth(306)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 10, 0, 0)
        panel_layout.setSpacing(8)
        rules_scroll = RulesScrollArea(objectName="rulesScroll")
        self.rules_scroll = rules_scroll
        rules_scroll.setWidgetResizable(True)
        rules_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rules_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rules_content = QWidget(objectName="rulesContent")
        rules_scroll.setWidget(rules_content)
        rules = QVBoxLayout(rules_content)
        rules.setContentsMargins(16, 8, 16, 12)
        rules.setSpacing(8)
        rule_heading = QHBoxLayout()
        rule_heading.setContentsMargins(16, 0, 10, 0)
        rule_heading.addWidget(QLabel("改名规则", objectName="section"))
        rule_heading.addStretch()
        reset = QPushButton("重置", objectName="quiet")
        reset.setIcon(line_icon("refresh"))
        reset.clicked.connect(self.reset_rules)
        rule_heading.addWidget(reset)
        panel_layout.addLayout(rule_heading)
        panel_layout.addWidget(rules_scroll, 1)
        self.find = QLineEdit(placeholderText="要替换的文字")
        self.replacement = QLineEdit(placeholderText="留空则删除匹配文字")
        self.prefix = QLineEdit(placeholderText="例如：旅行_")
        self.suffix = QLineEdit(placeholderText="例如：_精选")
        rules.addWidget(QLabel("查找与替换", objectName="hint"))
        for title, field in [("查找", self.find), ("替换", self.replacement)]:
            row = QHBoxLayout()
            label = QLabel(title)
            label.setFixedWidth(44)
            label.setBuddy(field)
            row.addWidget(label)
            row.addWidget(field, 1)
            rules.addLayout(row)
        helper = QLabel("替换留空时，删除匹配的文字", objectName="hint")
        rules.addWidget(helper)
        rules.addSpacing(4)
        rules.addWidget(QFrame(objectName="divider"))
        rules.addWidget(QLabel("前缀与后缀", objectName="hint"))
        for title, field in [("前缀", self.prefix), ("后缀", self.suffix)]:
            row = QHBoxLayout()
            label = QLabel(title)
            label.setFixedWidth(44)
            label.setBuddy(field)
            row.addWidget(label)
            row.addWidget(field, 1)
            rules.addLayout(row)
        rules.addSpacing(4)
        rules.addWidget(QFrame(objectName="divider"))
        numbering_row = QHBoxLayout()
        numbering_labels = QVBoxLayout()
        numbering_labels.setSpacing(4)
        numbering_labels.addWidget(QLabel("自动编号"))
        numbering_labels.addWidget(QLabel("在文件名末尾添加序号", objectName="hint"))
        numbering_row.addLayout(numbering_labels, 1)
        self.numbering = Toggle()
        numbering_row.addWidget(self.numbering)
        rules.addLayout(numbering_row)
        self.number_settings = Collapsible()
        settings_layout = QVBoxLayout(self.number_settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
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
        rules.addStretch()
        sample_panel = QFrame(objectName="sample")
        sample_layout = QVBoxLayout(sample_panel)
        sample_layout.setContentsMargins(16, 12, 16, 12)
        sample_layout.setSpacing(6)
        sample_layout.addWidget(QLabel("命名预览", objectName="hint"))
        self.example = QLabel("", objectName="example")
        self.example.setWordWrap(True)
        self.example.setMaximumHeight(42)
        self.example.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sample_layout.addWidget(self.example)
        sample_layout.addWidget(QLabel("保留扩展名 · 仅在原目录改名", objectName="hint"))
        panel_layout.addWidget(sample_panel)
        body.addWidget(panel)

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
        self.copy_name_action = QAction("复制原文件名", self.table)
        self.copy_name_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_name_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.copy_name_action.triggered.connect(self.copy_original_names)
        self.table.addAction(self.copy_name_action)
        preview_layout.addWidget(self.table, 1)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(18, 0, 12, 0)
        name_row.addWidget(QLabel("文件名"))
        self.original_name = FilenameEdit(placeholderText="选取部分文字，再填入查找")
        self.original_name.setAccessibleName("可复制的原文件名")
        name_row.addWidget(self.original_name, 1)
        self.fill_find_button = QPushButton("填入查找")
        self.fill_find_button.clicked.connect(self.fill_find_from_selection)
        name_row.addWidget(self.fill_find_button)
        preview_layout.addLayout(name_row)
        self.name_feedback = QLabel("选取文件名中的文字，可直接填入查找", objectName="hint")
        self.name_feedback.setWordWrap(True)
        self.name_feedback.setContentsMargins(18, 0, 12, 0)
        preview_layout.addWidget(self.name_feedback)
        self._original_source = None
        self.table.itemSelectionChanged.connect(self.update_original_name)
        self.table.currentCellChanged.connect(self.update_original_name)
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

        screen = QApplication.screenAt(QCursor.pos()) or self.screen()
        self.fit_to_available_area(screen.availableGeometry())

    def fit_to_available_area(self, area):
        frame_width = max(0, self.frameGeometry().width() - self.width())
        frame_height = max(40, self.frameGeometry().height() - self.height())
        width = min(1100, int(area.width() * 0.9), area.width() - frame_width - 32)
        height = min(700, int(area.height() * 0.88) - frame_height)
        self.resize(width, height)
        self.move(area.x() + (area.width() - self.width() - frame_width) // 2,
                  area.y() + (area.height() - self.height() - frame_height) // 2)

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

    def update_original_name(self, *args):
        selected = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        row = self.table.currentRow()
        if row not in selected:
            row = selected[0] if selected else -1
        item = self.table.item(row, 0) if row >= 0 else None
        source = self.rows[row].source if item and row < len(self.rows) else None
        text = source.stem if source else ""
        if self._original_source != source or self.original_name.text() != text:
            self.original_name.setText(text)
            self.original_name.deselect()
            self._original_source = source
            self.name_feedback.setText("选取文件名中的文字，可直接填入查找")
        sample_row = row if source else 0
        sample = self.rows[sample_row].target.name if self.rows else "添加文件后显示预览"
        self.example.setText(sample)
        self.example.setToolTip(sample)

    def fill_find_from_selection(self):
        selected = self.original_name.selectedText()
        if not selected:
            self.name_feedback.setText("请先在文件名中选取要查找的文字")
            self.original_name.setFocus()
            return
        self.find.setText(selected)
        self.find.setFocus()
        self.find.selectAll()
        self.name_feedback.setText("选中文字已填入查找")

    def copy_original_names(self):
        selected = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        if selected:
            QApplication.clipboard().setText("\n".join(self.table.item(row, 0).text() for row in selected))

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
        self.update_original_name()
        total = len(self.rows)
        conflicts = sum(bool(row.error) for row in self.rows)
        changed = sum(row.changed and not row.error for row in self.rows)
        self.count.setText(f"{total} 个文件")
        self.execute_button.setText(f"执行改名（{changed}）" if changed else "执行改名")
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
        self.number_settings.setExpanded(self.numbering.isChecked())
        self.numbering.sync_state()
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

    def confirm_action(self, title, message, details, action):
        box = AppMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setInformativeText(details)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirm = box.button(QMessageBox.StandardButton.Yes)
        confirm.setText(action)
        confirm.setObjectName("primary")
        box.button(QMessageBox.StandardButton.Cancel).setText("取消")
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def request_execute(self):
        if not self.execute_button.isEnabled():
            return
        count = sum(row.changed for row in self.rows)
        if self.confirm_action("确认批量改名", f"将按预览改名 {count} 个文件",
                               "不会覆盖已有文件。\n成功后可在本次打开期间撤销。", "确认改名"):
            rows = list(self.rows)
            self.start_operation(lambda: self.session.execute(rows), "execute")

    def request_undo(self):
        if self.confirm_action("确认撤销", f"恢复上次改名的 {len(self.session.history)} 个文件？",
                               "范围包含已从列表移除的文件。", "确认撤销"):
            self.start_operation(self.session.undo, "undo")

    def request_recovery(self):
        if self.confirm_action("确认恢复", f"尝试恢复 {len(self.session.pending)} 个文件？",
                               "请先处理错误详情中的文件占用或外部修改。", "开始恢复"):
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
        box = AppMessageBox(self)
        box.setWindowTitle("文件操作详情")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(self.last_result.message)
        box.setInformativeText("展开详情查看完整路径与原因。处理后可刷新预览或重试恢复。")
        box.setDetailedText("\n\n".join(self.last_result.errors))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.button(QMessageBox.StandardButton.Ok).setText("关闭")
        box.exec()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            return
        if self.session.pending:
            if not self.confirm_action("仍有文件未恢复", "仍要关闭程序？",
                                       "关闭后会丢失本次恢复记录。\n建议先查看错误详情并完成恢复。", "仍然关闭"):
                event.ignore()
                return
        event.accept()


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BatchFileRenamer.Desktop")
        os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=freetype")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    translator = QTranslator(app)
    if translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    window = MainWindow()
    window.show()
    window.fit_to_available_area(window.screen().availableGeometry())
    window.windowHandle().screenChanged.connect(
        lambda screen: window.fit_to_available_area(screen.availableGeometry()))
    if sys.platform == "win32":
        light_titlebar = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(int(window.winId())), 20,
                                                  ctypes.byref(light_titlebar), ctypes.sizeof(light_titlebar))
    return app.exec()
