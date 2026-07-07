#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QRect, Qt
from PySide6.QtGui import QAction, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .app_info import APP_NAME, about_text
from .app_settings import save_settings
from .compare import compare_paths
from .diff_window import DiffPreviewPanel, DiffWindow
from .models import CompareOptions, CompareResult, CompareState, FileRecord
from .settings_dialog import SettingsDialog
from .sync import SyncDirection, sync_directories
from .theme import DARK_THEME, LIGHT_THEME, Theme

TREE_ITEM_KIND_ROLE = Qt.ItemDataRole.UserRole + 1
TREE_ITEM_PATH_ROLE = Qt.ItemDataRole.UserRole + 2


class _FileTree(QTreeWidget):
    """QTreeWidget with [+]/[-] expand/collapse indicators instead of arrows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._box_color = QColor("#2e5070")
        self._sign_color = QColor("#6a90bb")

    def set_branch_colors(self, box_color: str, sign_color: str) -> None:
        self._box_color = QColor(box_color)
        self._sign_color = QColor(sign_color)
        self.viewport().update()

    def drawBranches(self, painter: QPainter, rect: QRect, index) -> None:  # type: ignore[override]
        super().drawBranches(painter, rect, index)
        item = self.itemFromIndex(index)
        if item is None or item.childCount() == 0:
            return
        depth = 0
        parent = item.parent()
        while parent is not None:
            depth += 1
            parent = parent.parent()
        indent = self.indentation()
        cx = rect.x() + depth * indent + indent // 2
        cy = rect.y() + rect.height() // 2
        size = 11
        half = size // 2
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(self._box_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(cx - half, cy - half, size, size))
        painter.setPen(QPen(self._sign_color, 1))
        arm = half - 2
        painter.drawLine(cx - arm, cy, cx + arm, cy)
        if not item.isExpanded():
            painter.drawLine(cx, cy - arm, cx, cy + arm)
        painter.restore()


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        left_path: Path | None = None,
        right_path: Path | None = None,
        recurse_subdirectories: bool = True,
        auto_compare: bool = False,
    ) -> None:
        super().__init__()
        self.result: CompareResult | None = None
        self.recurse_subdirectories = recurse_subdirectories
        self.theme = DARK_THEME
        self.diff_windows: list[DiffWindow] = []
        self._collapsed_dir_paths: set[str] = set()
        self._last_compare_roots: tuple[str, str] | None = None

        self.left_input = QLineEdit(str(left_path or ""))
        self.right_input = QLineEdit(str(right_path or ""))
        self.only_changes = QCheckBox("Only changes")
        self.only_changes.setChecked(True)
        self.stats_label = QLabel("Total 0 | Equal 0 | Action req. 0")
        self.table = _FileTree()
        self.sync_lr_button = QPushButton("Sync L -> R")
        self.sync_rl_button = QPushButton("Sync L <- R")
        self.sync_lr_button.setObjectName("SyncButton")
        self.sync_rl_button.setObjectName("SyncButton")
        self.sync_lr_button.setEnabled(False)
        self.sync_rl_button.setEnabled(False)
        self.preview_panel = DiffPreviewPanel(self.theme)

        self._build_ui()
        self.apply_theme(self.theme)
        if auto_compare:
            self.compare()

    def _build_ui(self) -> None:
        self.setWindowTitle("SmartDiff")
        self.resize(1260, 820)
        self._build_menu()

        left_browse = QPushButton("Browse...")
        right_browse = QPushButton("Browse...")
        compare_button = QPushButton("Compare")
        compare_button.setObjectName("CompareButton")
        left_browse.clicked.connect(lambda: self._browse(self.left_input))
        right_browse.clicked.connect(lambda: self._browse(self.right_input))
        compare_button.clicked.connect(self.compare)
        self.sync_lr_button.clicked.connect(lambda: self._sync(SyncDirection.LEFT_TO_RIGHT))
        self.sync_rl_button.clicked.connect(lambda: self._sync(SyncDirection.RIGHT_TO_LEFT))
        self.only_changes.toggled.connect(self.populate_table)

        lbl_left = QLabel("Left")
        lbl_left.setObjectName("PathDirLabel")
        lbl_right = QLabel("Right")
        lbl_right.setObjectName("PathDirLabel")

        toolbar = QWidget()
        toolbar.setObjectName("ToolBar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(lbl_left)
        toolbar_layout.addWidget(self.left_input, 1)
        toolbar_layout.addWidget(left_browse)
        toolbar_layout.addSpacing(16)
        toolbar_layout.addWidget(lbl_right)
        toolbar_layout.addWidget(self.right_input, 1)
        toolbar_layout.addWidget(right_browse)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(compare_button)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.sync_lr_button)
        toolbar_layout.addWidget(self.sync_rl_button)

        self.stats_label.setObjectName("StatsLabel")
        stats_bar = QWidget()
        stats_bar.setObjectName("StatsBar")
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(12, 5, 12, 5)
        stats_layout.setSpacing(8)
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch(1)
        stats_layout.addWidget(self.only_changes)

        self.table.setColumnCount(6)
        self.table.setHeaderLabels(["Name", "Kind", "State", "Suggested action", "Left", "Right"])
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            self.table.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setRootIsDecorated(True)
        self.table.setUniformRowHeights(True)
        self.table.setIndentation(18)
        self.table.setToolTip("Double-click to open in a new diff window")
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.table.currentItemChanged.connect(self._on_selection_changed)
        self.table.itemExpanded.connect(self._on_item_expanded)
        self.table.itemCollapsed.connect(self._on_item_collapsed)

        vsplit = QSplitter(Qt.Orientation.Vertical)
        vsplit.addWidget(self.table)
        vsplit.addWidget(self.preview_panel)
        vsplit.setSizes([380, 300])
        vsplit.setCollapsible(1, True)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stats_bar)
        layout.addWidget(vsplit, 1)
        self.setCentralWidget(root)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        settings_action = QAction("Preferences...", self)
        exit_action = QAction("Exit", self)
        settings_action.triggered.connect(self._open_settings)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        options_menu = self.menuBar().addMenu("Options")
        self.recurse_action = QAction("Scan subdirectories", self, checkable=True)
        self.theme_action = QAction("Light theme", self, checkable=True)
        self.recurse_action.setChecked(self.recurse_subdirectories)
        self.recurse_action.toggled.connect(self._set_recurse)
        self.theme_action.toggled.connect(lambda enabled: self.apply_theme(LIGHT_THEME if enabled else DARK_THEME))
        options_menu.addAction(self.recurse_action)
        options_menu.addSeparator()
        options_menu.addAction(self.theme_action)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(self, f"About {APP_NAME}", about_text()))
        help_menu.addAction(about)

    def _browse(self, target: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose directory")
        if directory:
            target.setText(directory)

    def compare(self) -> None:
        left = Path(self.left_input.text()).expanduser()
        right = Path(self.right_input.text()).expanduser()
        if not left.exists() or not right.exists():
            QMessageBox.warning(self, "Path not found", "Both paths must exist.")
            return
        compare_roots = (str(left), str(right))
        if compare_roots != self._last_compare_roots:
            self._collapsed_dir_paths.clear()
            self._last_compare_roots = compare_roots
        self.result = compare_paths(left, right, CompareOptions(self.recurse_subdirectories))
        allow_sync = self.result.is_directory_comparison
        self.sync_lr_button.setEnabled(allow_sync)
        self.sync_rl_button.setEnabled(allow_sync)
        self.populate_table()

    def _sync(self, direction: SyncDirection) -> None:
        if self.result is None:
            return
        if not self.result.is_directory_comparison:
            QMessageBox.information(
                self,
                "Sync unavailable",
                "Synchronization is only available for directory comparisons.",
            )
            return
        label = "L -> R" if direction == SyncDirection.LEFT_TO_RIGHT else "L <- R"
        reply = QMessageBox.question(
            self,
            f"Sync {label}",
            f"This will copy/overwrite files ({label}).\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            sync_result = sync_directories(self.result, direction)
        except Exception as exc:
            QMessageBox.critical(self, "Sync failed", str(exc))
            return
        self.compare()
        parts = []
        if sync_result.new_files_copied:
            parts.append(f"{sync_result.new_files_copied} new file(s) copied")
        if sync_result.files_overwritten:
            parts.append(f"{sync_result.files_overwritten} file(s) overwritten")
        if sync_result.directories_created:
            parts.append(f"{sync_result.directories_created} dir(s) created")
        if sync_result.skipped_type_mismatch:
            parts.append(f"{sync_result.skipped_type_mismatch} skipped (type mismatch)")
        msg = ", ".join(parts) if parts else "Nothing to sync."
        QMessageBox.information(self, f"Sync {label} complete", msg)

    def populate_table(self) -> None:
        if self.result is None:
            return
        previous_record = self._current_record()
        previous_path = previous_record.relative_path if previous_record else None
        self.table.clear()
        is_dark = self.theme.name == "Dark"
        state_colors: dict[str, str] = {
            CompareState.DIFFERENT.value: "#f0b040" if is_dark else "#b06010",
            CompareState.LEFT_YOUNGER.value: "#55d4a0" if is_dark else "#0d7a55",
            CompareState.RIGHT_YOUNGER.value: "#d4a055" if is_dark else "#8a5a10",
            CompareState.LEFT_ONLY.value: "#55b3ff" if is_dark else "#1a6ab5",
            CompareState.RIGHT_ONLY.value: "#a080ff" if is_dark else "#6040b0",
            CompareState.EQUAL.value: "#3a6045" if is_dark else "#90a898",
            CompareState.TYPE_MISMATCH.value: "#ff7070" if is_dark else "#c03030",
        }
        action_colors: dict[str, str] = {
            "Copy left to right": "#55b3ff" if is_dark else "#1a6ab5",
            "Copy right to left": "#a080ff" if is_dark else "#6040b0",
            "Review contents": "#f0b040" if is_dark else "#b06010",
            "Review binary metadata": "#f0b040" if is_dark else "#b06010",
            "Review large file metadata": "#f0b040" if is_dark else "#b06010",
            "Review type mismatch": "#ff7070" if is_dark else "#c03030",
        }
        dim_color = QColor("#3a6045" if is_dark else "#90a898")
        dir_color = QColor("#6a90bb" if is_dark else "#4a6a85")

        show_only_changes = self.only_changes.isChecked()
        entries = [
            item
            for item in self.result.entries
            if not show_only_changes or item.state != CompareState.EQUAL
        ]

        dir_nodes: dict[str, QTreeWidgetItem] = {}
        file_nodes: dict[str, QTreeWidgetItem] = {}
        style = self.style()
        folder_icon = style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        file_icon = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)

        def get_or_create_dir(dir_path: str) -> QTreeWidgetItem:
            if dir_path in dir_nodes:
                return dir_nodes[dir_path]
            slash = dir_path.rfind("/")
            name = dir_path[slash + 1:]
            if slash < 0:
                node = QTreeWidgetItem(self.table)
            else:
                node = QTreeWidgetItem(get_or_create_dir(dir_path[:slash]))
            node.setText(0, name)
            node.setIcon(0, folder_icon)
            for col in range(6):
                node.setForeground(col, dir_color)
            node.setData(0, TREE_ITEM_KIND_ROLE, "dir")
            node.setData(0, TREE_ITEM_PATH_ROLE, dir_path)
            dir_nodes[dir_path] = node
            return node

        for record in entries:
            slash = record.relative_path.rfind("/")
            filename = record.relative_path[slash + 1:] if slash >= 0 else record.relative_path
            if slash < 0:
                file_item = QTreeWidgetItem(self.table)
            else:
                file_item = QTreeWidgetItem(get_or_create_dir(record.relative_path[:slash]))

            is_directory = _record_has_directory(record)
            file_item.setIcon(0, folder_icon if is_directory else file_icon)

            is_equal = record.state == CompareState.EQUAL
            values = [
                filename,
                record.kind,
                record.state.value,
                record.suggested_action,
                _format_side(record.left_size, record.left_mtime),
                _format_side(record.right_size, record.right_mtime),
            ]
            if is_directory:
                tooltip = "Directory metadata only. Open diff is not available."
            elif record.is_binary or record.is_too_large:
                tooltip = "Text diff is not available for this file"
            else:
                tooltip = "Double-click to open in a new diff window"

            file_item.setData(0, TREE_ITEM_KIND_ROLE, "dir" if is_directory else "file")
            for col, val in enumerate(values):
                file_item.setText(col, val)
                file_item.setToolTip(col, tooltip)
                if is_equal:
                    file_item.setForeground(col, dim_color)
                elif col == 2:
                    color = state_colors.get(val)
                    if color:
                        file_item.setForeground(col, QColor(color))
                elif col == 3:
                    color = action_colors.get(val)
                    if color:
                        file_item.setForeground(col, QColor(color))
            file_item.setData(0, Qt.ItemDataRole.UserRole, record)
            file_nodes[record.relative_path] = file_item

        _sort_tree_directories_first(self.table)
        self._apply_directory_expansion_state(dir_nodes)
        self._restore_or_clear_selection(previous_path, file_nodes)
        self.stats_label.setText(
            f"Total {len(self.result.entries)} | Equal {self.result.equal_count} | "
            f"Action req. {self.result.action_count}"
        )

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        record = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(record, FileRecord) or not record.left_path or not record.right_path:
            return
        if record.kind == "Directory":
            return
        if record.state == CompareState.TYPE_MISMATCH or record.is_binary or record.is_too_large:
            return
        window = DiffWindow(
            record.left_path,
            record.right_path,
            dark_theme=self.theme.name == "Dark",
        )
        window.theme_changed.connect(
            lambda dark_theme: self.apply_theme(DARK_THEME if dark_theme else LIGHT_THEME)
        )
        window.files_saved.connect(self._on_diff_window_saved)
        self.diff_windows.append(window)
        window.destroyed.connect(lambda: self._forget_window(window))
        window.show()

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        previous_blocked = self.theme_action.blockSignals(True)
        self.theme_action.setChecked(theme.name == "Light")
        self.theme_action.blockSignals(previous_blocked)
        is_dark = theme.name == "Dark"
        if is_dark:
            self.table.set_branch_colors(box_color="#2e5070", sign_color="#6a90bb")
        else:
            self.table.set_branch_colors(box_color="#8aaabf", sign_color="#3a6090")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.stylesheet)
        self.preview_panel.apply_theme(theme)
        self.populate_table()

    def _set_recurse(self, value: bool) -> None:
        self.recurse_subdirectories = value
        if self.result is not None:
            self.compare()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        save_settings(dialog.settings())
        if self.result is not None:
            self.compare()

    def _on_selection_changed(self, current: "QTreeWidgetItem | None", _previous: "QTreeWidgetItem | None") -> None:
        if current is None:
            self.preview_panel.clear()
            return
        record = current.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(record, FileRecord):
            self.preview_panel.clear()
            return
        is_directory = _record_has_directory(record)
        left_meta = _side_meta("Left", record.left_path, record.left_size, record.left_mtime, record.left_hash)
        right_meta = _side_meta("Right", record.right_path, record.right_size, record.right_mtime, record.right_hash)
        self.preview_panel.load(
            record.left_path,
            record.right_path,
            record.relative_path,
            f"State: {record.state.value}",
            left_meta,
            right_meta,
            is_directory=is_directory,
            is_binary=record.is_binary,
            is_too_large=record.is_too_large,
            binary_contents_equal=(
                record.is_binary
                and record.state == CompareState.EQUAL
                and record.left_hash is not None
                and record.left_hash == record.right_hash
            ),
        )

    def _forget_window(self, window: DiffWindow) -> None:
        if window in self.diff_windows:
            self.diff_windows.remove(window)

    def _tree_item_path(self, item: QTreeWidgetItem) -> str | None:
        path = item.data(0, TREE_ITEM_PATH_ROLE)
        return path if isinstance(path, str) else None

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        path = self._tree_item_path(item)
        if path is not None:
            self._collapsed_dir_paths.discard(path)

    def _on_item_collapsed(self, item: QTreeWidgetItem) -> None:
        path = self._tree_item_path(item)
        if path is not None:
            self._collapsed_dir_paths.add(path)

    def _apply_directory_expansion_state(self, dir_nodes: dict[str, QTreeWidgetItem]) -> None:
        with QSignalBlocker(self.table):
            self.table.expandAll()
            for path, item in dir_nodes.items():
                item.setExpanded(path not in self._collapsed_dir_paths)

    def _on_diff_window_saved(self) -> None:
        if self.result is not None:
            self.compare()

    def _current_record(self) -> FileRecord | None:
        item = self.table.currentItem()
        if item is None:
            return None
        record = item.data(0, Qt.ItemDataRole.UserRole)
        return record if isinstance(record, FileRecord) else None

    def _restore_or_clear_selection(
        self,
        previous_path: str | None,
        file_nodes: dict[str, QTreeWidgetItem],
    ) -> None:
        if previous_path is not None and previous_path in file_nodes:
            self.table.setCurrentItem(file_nodes[previous_path])
            self._on_selection_changed(file_nodes[previous_path], None)
        else:
            self.table.setCurrentItem(None)
            self.preview_panel.clear()


def _format_side(size: int | None, mtime: float | None) -> str:
    if size is None:
        return "-"
    parts = [_format_size(size)]
    if mtime:
        parts.append(_format_time(mtime))
    return "  |  ".join(parts)


def _record_has_directory(record: FileRecord) -> bool:
    return bool(
        (record.left_path is not None and record.left_path.is_dir())
        or (record.right_path is not None and record.right_path.is_dir())
    )


def _side_meta(
    label: str,
    path: Path | None,
    size: int | None,
    mtime: float | None,
    digest: str | None,
) -> str:
    if path is None:
        return ""
    parts = [label, "Directory" if path.is_dir() else _format_size(size)]
    if mtime:
        parts.append(_format_time(mtime))
    if digest:
        parts.append(f"SHA-256 {_format_hash(digest)}")
    return " | ".join(part for part in parts if part)


def _format_size(size: int | None) -> str:
    if size is None:
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size / 1024 / 1024:.2f} MB"


def _format_time(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    return dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _format_hash(value: str) -> str:
    return value[:12]


def _sort_tree_directories_first(tree: QTreeWidget) -> None:
    def item_key(item: QTreeWidgetItem) -> tuple[int, str]:
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        type_order = 0 if item_type == "dir" else 1
        return type_order, item.text(0).casefold()

    def sort_children(parent: QTreeWidgetItem) -> None:
        children = [parent.takeChild(0) for _ in range(parent.childCount())]
        for child in sorted(children, key=item_key):
            parent.addChild(child)
            sort_children(child)

    top_items = [tree.takeTopLevelItem(0) for _ in range(tree.topLevelItemCount())]
    for item in sorted(top_items, key=item_key):
        tree.addTopLevelItem(item)
        sort_children(item)
