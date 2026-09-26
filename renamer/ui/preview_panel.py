from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QStyledItemDelegate, QStyle, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ..core import Entry
from .controls import FilenameEdit, HeadingLabel
from .theme import line_icon


class PreviewTable(QTableWidget):
    files_dropped = Signal(list)
    order_changed = Signal(list)

    def __init__(self, rows, columns):
        super().__init__(rows, columns)
        self.drop_overlay = QLabel("松开鼠标，将文件添加到列表", parent=self.viewport(), objectName="dropOverlay")
        self.drop_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drop_overlay.hide()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.source() != self:
            self._show_drop_overlay()
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() and event.source() != self:
            self._show_drop_overlay()
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.drop_overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.drop_overlay.hide()
        if event.mimeData().hasUrls() and event.source() != self:
            paths = [url.toLocalFile() for url in event.mimeData().urls()
                     if url.isLocalFile() and Path(url.toLocalFile()).is_file()]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        before = self._ordered_paths()
        super().dropEvent(event)
        reordered = self._ordered_paths()
        if reordered != before:
            self.order_changed.emit(reordered)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.drop_overlay.setGeometry(self.viewport().rect().adjusted(8, 8, -8, -8))

    def _show_drop_overlay(self):
        self.drop_overlay.setGeometry(self.viewport().rect().adjusted(8, 8, -8, -8))
        self.drop_overlay.show()
        self.drop_overlay.raise_()

    def _ordered_paths(self):
        return [self.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
                for row in range(self.rowCount()) if self.item(row, 0)]


class PreviewPanel(QFrame):
    refresh_requested = Signal()
    remove_requested = Signal()
    clear_requested = Signal()
    find_requested = Signal(str)
    example_changed = Signal(str)

    def __init__(self):
        super().__init__(objectName="panel")
        self._rows: tuple[Entry, ...] = ()
        preview_layout = QVBoxLayout(self)
        preview_layout.setContentsMargins(1, 12, 1, 8)
        preview_layout.setSpacing(8)
        preview_layout.addLayout(self._create_toolbar())
        self._create_table()
        preview_layout.addWidget(self.table, 1)
        self._add_drop_hint(preview_layout)
        self._add_filename_controls(preview_layout)
        self._create_empty_state()

    def _create_toolbar(self):
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(18, 0, 12, 2)
        toolbar.addWidget(HeadingLabel("文件预览", objectName="section"))
        self.count = QLabel("", objectName="hint")
        toolbar.addWidget(self.count)
        toolbar.addStretch()
        refresh = QPushButton("刷新", objectName="quiet")
        refresh.setIcon(line_icon("refresh"))
        refresh.clicked.connect(self.refresh_requested.emit)
        toolbar.addWidget(refresh)
        self.remove_button = QPushButton("移除选中", objectName="quiet")
        self.remove_button.setIcon(line_icon("trash"))
        self.remove_button.clicked.connect(self.remove_requested.emit)
        toolbar.addWidget(self.remove_button)
        self.clear_button = QPushButton("清空", objectName="quiet")
        self.clear_button.setIcon(line_icon("trash"))
        self.clear_button.clicked.connect(self.clear_requested.emit)
        toolbar.addWidget(self.clear_button)
        return toolbar

    def _create_table(self):
        self.table = PreviewTable(0, 4)
        self.table.setHorizontalHeaderLabels(["原文件名", "新文件名", "所在目录", "状态"])
        self.table.setColumnHidden(2, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.viewport().setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.table.setDragDropOverwriteMode(False)
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
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.copy_name_action = QAction("复制原文件名", self.table)
        self.copy_name_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_name_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.copy_name_action.triggered.connect(self.copy_original_names)
        self.table.addAction(self.copy_name_action)

    def _add_drop_hint(self, preview_layout):
        hint = QHBoxLayout()
        hint.setContentsMargins(18, 0, 12, 0)
        hint.setSpacing(7)
        icon = QLabel("↓", objectName="dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.addWidget(icon)
        hint.addWidget(QLabel("拖入文件即可添加；拖动左侧手柄调整编号顺序", objectName="hint"))
        hint.addStretch()
        preview_layout.addLayout(hint)

    def _add_filename_controls(self, preview_layout):
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

    def _create_empty_state(self):
        self.empty = QLabel("添加文件，预览每一个新名字", objectName="hint", parent=self.table.viewport())
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout = QVBoxLayout(self.table.viewport())
        empty_layout.addWidget(self.empty)
        self.empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def render(self, rows: Sequence[Entry]) -> None:
        self._rows = tuple(rows)
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
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
                    item.setData(Qt.ItemDataRole.UserRole + 1, str(row.source))
                elif column == 1:
                    item.setData(Qt.ItemDataRole.UserRole, row.changed)
                elif column == 3:
                    item.setData(Qt.ItemDataRole.UserRole, bool(row.error))
                self.table.setItem(index, column, item)
        self.update_original_name()
        self.count.setText(f"{len(self._rows)} 个文件")
        self.empty.setVisible(not self._rows)
        self.clear_button.setEnabled(bool(self._rows))
        self._selection_changed()

    def update_original_name(self, *args):
        selected = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        row = self.table.currentRow()
        if row not in selected:
            row = selected[0] if selected else -1
        item = self.table.item(row, 0) if row >= 0 else None
        source = self._rows[row].source if item and row < len(self._rows) else None
        text = source.stem if source else ""
        if self._original_source != source or self.original_name.text() != text:
            self.original_name.setText(text)
            self.original_name.deselect()
            self._original_source = source
            self.name_feedback.setText("选取文件名中的文字，可直接填入查找")
        sample_row = row if source else 0
        sample = self._rows[sample_row].target.name if self._rows else "添加文件后显示预览"
        self.example_changed.emit(sample)

    def fill_find_from_selection(self):
        selected = self.original_name.selectedText()
        if not selected:
            self.name_feedback.setText("请先在文件名中选取要查找的文字")
            self.original_name.setFocus()
            return
        self.find_requested.emit(selected)
        self.name_feedback.setText("选中文字已填入查找")

    def copy_original_names(self):
        selected = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        if selected:
            QApplication.clipboard().setText("\n".join(self.table.item(row, 0).text() for row in selected))

    def selected_rows(self) -> set[int]:
        return {index.row() for index in self.table.selectionModel().selectedRows()}

    def _selection_changed(self):
        self.remove_button.setEnabled(bool(self.selected_rows()))


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
        if index.column() in (1, 3):
            painter.fillRect(rect.left(), rect.top(), 1, rect.height(), QColor("#E5EAF1"))
        text_rect = rect.adjusted(16, 0, -12, 0)
        text = str(index.data() or "")
        painter.setFont(option.font)
        if index.column() == 0:
            painter.setPen(QColor("#9AA6B8"))
            for x_offset in (8, 12):
                for y_offset in (-5, 0, 5):
                    painter.drawEllipse(rect.left() + x_offset, rect.center().y() + y_offset, 2, 2)
            self.file_icon.paint(painter, rect.left() + 23, rect.center().y() - 12, 24, 24)
            text_rect.adjust(42, 0, 0, 0)
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
