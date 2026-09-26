from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QVBoxLayout, QWidget, QSizePolicy,
)

from ..core import Rules
from ..operations import Result
from ..workspace import Workspace
from .dialogs import confirm_action, show_details, show_recovery_error
from .controls import HeadingLabel
from .rules_panel import RulesPanel
from .preview_panel import PreviewPanel
from .runtime import fit_to_available_area
from .tasks import Worker
from .theme import STYLE, APP_ICON


class MainWindow(QMainWindow):
    def __init__(self, workspace: Workspace | None = None):
        super().__init__()
        self.setWindowTitle("Batch File Renamer")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setAcceptDrops(True)
        self.setMinimumSize(760, 420)
        self.setStyleSheet(STYLE)
        self.workspace = workspace if workspace is not None else Workspace()
        self.busy = False
        self.worker: Worker | None = None
        self._build_content()
        self._connect_panels()
        self.refresh_preview()
        screen = QApplication.screenAt(QCursor.pos()) or self.screen()
        self.fit_to_available_area(screen.availableGeometry())

    def _build_content(self):
        self.content = QWidget(objectName="content")
        self.setCentralWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(14)
        layout.addLayout(self._create_heading())
        body = QHBoxLayout()
        body.setSpacing(14)
        self.rules_panel = RulesPanel()
        self.preview_panel = PreviewPanel()
        body.addWidget(self.rules_panel)
        body.addWidget(self.preview_panel, 1)
        layout.addLayout(body, 1)
        layout.addWidget(QFrame(objectName="divider"))
        layout.addLayout(self._create_footer())

    def _create_heading(self):
        heading = QHBoxLayout()
        heading.addWidget(HeadingLabel("批量改名", objectName="title"))
        heading.addSpacing(8)
        self.subtitle = QLabel("每一个新名字，都先预览", objectName="subtitle")
        heading.addWidget(self.subtitle)
        heading.addStretch()
        self.add_button = QPushButton("＋  添加文件", objectName="primary")
        self.add_button.clicked.connect(self.choose_files)
        heading.addWidget(self.add_button)
        return heading

    def _create_footer(self):
        footer = QHBoxLayout()
        status_group = QVBoxLayout()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        status_group.addWidget(self.status)
        self.history_hint = QLabel("", objectName="hint")
        status_group.addWidget(self.history_hint)
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
        return footer

    def _connect_panels(self):
        self.rules_panel.rules_changed.connect(self.change_rules)
        self.preview_panel.refresh_requested.connect(self.refresh_preview)
        self.preview_panel.remove_requested.connect(self.remove_selected)
        self.preview_panel.clear_requested.connect(lambda: self.set_paths([]))
        self.preview_panel.table.files_dropped.connect(self.add_paths)
        self.preview_panel.table.order_changed.connect(self.reorder_paths)
        self.preview_panel.find_requested.connect(self.rules_panel.fill_find)
        self.preview_panel.example_changed.connect(self.rules_panel.show_example)

    def fit_to_available_area(self, area):
        fit_to_available_area(self, area)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "rules_panel"):
            compact = self.width() <= 830
            self.rules_panel.setFixedWidth(280 if compact else 306)
            self.subtitle.setVisible(not compact)

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择需要改名的文件", "", "所有文件 (*)")
        self.add_paths(files)

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() and Path(url.toLocalFile()).is_file() for url in event.mimeData().urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()
                 if url.isLocalFile() and Path(url.toLocalFile()).is_file()]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def add_paths(self, paths: Iterable[str | Path]) -> None:
        self.workspace.add_paths(paths)
        self.render_preview()

    def set_paths(self, paths: Iterable[Path]) -> None:
        self.workspace.set_paths(paths)
        self.render_preview()

    def reorder_paths(self, paths: Iterable[str | Path]) -> None:
        self.workspace.reorder_paths(paths)
        self.render_preview()

    def remove_selected(self):
        self.workspace.remove_rows(self.preview_panel.selected_rows())
        self.render_preview()

    def reset_rules(self):
        self.rules_panel.reset()

    def change_rules(self, rules: Rules) -> None:
        self.workspace.set_rules(rules)
        self.render_preview()

    def refresh_preview(self):
        self.workspace.refresh()
        self.render_preview()

    def render_preview(self):
        self.preview_panel.render(self.workspace.rows)
        total = len(self.workspace.rows)
        conflicts = sum(bool(row.error) for row in self.workspace.rows)
        changed = sum(row.changed and not row.error for row in self.workspace.rows)
        self.execute_button.setText(f"执行改名（{changed}）" if changed else "执行改名")
        self.status.setStyleSheet("color: #149447; font-weight: 600;" if changed and not conflicts else "color: #71809A;")
        if not total:
            self.status.setText("添加文件后，设置规则即可看到新名字。")
        elif conflicts:
            self.status.setText(f"有 {conflicts} 个文件需要处理，请查看状态列，修改规则或移除对应行。")
        elif changed:
            self.status.setText(f"{changed} 个文件可改名 · 无冲突")
        else:
            self.status.setText("当前规则没有改变文件名。可以设置替换、前后缀或追加编号。")
        if self.workspace.session.recovery_error:
            self.status.setText("恢复状态无法核实，改名和撤销已暂停。")
            self.status.setStyleSheet("color: #B63B49; font-weight: 600;")
        elif self.workspace.session.recovery_action:
            self.status.setText("检测到未完成操作，可继续处理或稍后处理。")
            self.status.setStyleSheet("color: #A56300; font-weight: 600;")
        self.update_buttons()

    def update_buttons(self):
        session = self.workspace.session
        blocked = session.has_recovery
        self.execute_button.setEnabled(not self.busy and not blocked and any(r.changed for r in self.workspace.rows)
                                       and not any(r.error for r in self.workspace.rows))
        self.undo_button.setEnabled(not self.busy and not blocked and bool(session.history))
        action = session.recovery_action
        can_continue = bool(action and not session.recovery_error)
        self.recover_button.setVisible(can_continue)
        self.recover_button.setText("继续撤销" if action == "undo" else "继续恢复")
        self.recover_button.setEnabled(not self.busy and can_continue)
        has_details = bool((self.workspace.last_result and self.workspace.last_result.errors)
                           or session.recovery_error)
        self.details_button.setVisible(has_details)
        if session.recovery_error:
            self.history_hint.setText("恢复状态无法核实，改名与撤销已暂停。")
        elif action:
            self.history_hint.setText("存在未完成操作；稍后处理后，重新打开仍可继续。")
        elif session.store is not None:
            self.history_hint.setText("最近一次改名记录会保留，重新打开后仍可撤销。")
        else:
            self.history_hint.setText("撤销记录仅在本次打开期间有效。")

    def confirm_action(self, title, message, details, action, cancel_text="取消"):
        return confirm_action(self, title, message, details, action, cancel_text)

    def prompt_startup_recovery(self):
        session = self.workspace.session
        if session.recovery_error:
            self.workspace.last_result = Result(False, "暂时无法安全恢复", [session.recovery_error])
            self.update_buttons()
            show_recovery_error(self, session.recovery_error)
            return
        action = session.recovery_action
        if not action:
            return
        moves = session.active["moves"] if session.active else session.pending
        if action == "undo":
            title = "上次撤销尚未完成"
            message = "程序上次在撤销过程中退出。继续后会按原来的撤销操作处理尚未完成的文件。"
            detail = "继续前会再次检查文件身份和目标占用。"
            confirm_label = "继续撤销"
            callback = session.undo
        else:
            title = "检测到上次未完成的改名"
            message = "程序检测到上次批量改名尚未完成。确认后会再次核验文件身份和目标占用，并恢复已完成的部分。"
            detail = (f"待处理 {len(moves)} 个文件\n"
                      "不会覆盖已存在的文件。")
            confirm_label = "恢复到改名前状态"
            callback = session.recover
        if self.confirm_action(title, message, detail, confirm_label, cancel_text="稍后处理"):
            self.start_operation(callback, action)

    def request_execute(self):
        if not self.execute_button.isEnabled():
            return
        count = sum(row.changed for row in self.workspace.rows)
        if self.confirm_action("确认批量改名", f"将按预览改名 {count} 个文件",
                               "不会覆盖已有文件。\n成功后仍可撤销最近一批。", "确认改名"):
            rows = list(self.workspace.rows)
            session = self.workspace.session
            self.start_operation(lambda: session.execute(rows), "execute")

    def request_undo(self):
        if self.confirm_action("确认撤销", f"恢复上次改名的 {len(self.workspace.session.history)} 个文件？",
                               "范围包含已从列表移除的文件。", "确认撤销"):
            self.start_operation(self.workspace.session.undo, "undo")

    def request_recovery(self):
        session = self.workspace.session
        action = session.recovery_action
        moves = session.active["moves"] if session.active else session.pending
        if action == "undo":
            title = "确认继续撤销"
            message = f"继续撤销剩余的 {len(moves)} 个文件？"
            detail = "应用会再次检查文件身份和目标占用。"
            label = "继续撤销"
            callback = session.undo
        else:
            title = "确认恢复"
            message = f"尝试恢复 {len(moves)} 个文件？"
            detail = "请先处理错误详情中的文件占用或外部修改。"
            label = "开始恢复"
            callback = session.recover
        if action and self.confirm_action(title, message, detail, label):
            self.start_operation(callback, action)

    def start_operation(self, operation: Callable[[], Result], action: str) -> None:
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
        self.workspace.apply_result(result, self.action)
        self.busy = False
        self.content.setEnabled(True)
        self.rules_panel.set_rules(self.workspace.rules)
        self.render_preview()
        self.status.setText(result.message)
        self.status.setStyleSheet("color: #149447;" if result.ok else "color: #B63B49;")
        if result.errors:
            self.show_details()

    def show_details(self):
        show_details(self, self.workspace.last_result)

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            return
        session = self.workspace.session
        if session.has_recovery and not session.recovery_error:
            if not self.confirm_action("仍有操作待处理", "仍要关闭程序？",
                                       "待处理记录会保留在本机，下次打开后仍可继续。",
                                       "仍然关闭", cancel_text="继续处理"):
                event.ignore()
                return
        event.accept()
