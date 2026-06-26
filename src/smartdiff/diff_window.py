#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QSize, Signal, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QPainter, QPainterPath, QPen, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from .theme import DARK_THEME, LIGHT_THEME, Theme


DIFF_FONT_FAMILY = "'Consolas', 'Cascadia Mono', 'Menlo', 'SF Mono', 'Liberation Mono', 'DejaVu Sans Mono', monospace"
DIFF_FONT_SIZE = "14px"
ACTION_PANEL_WIDTH = 112


@dataclass(frozen=True)
class DiffLineStyle:
    side: str
    line: int
    color: str


@dataclass(frozen=True)
class InlineStyle:
    side: str
    line: int
    start: int
    end: int


@dataclass(frozen=True)
class DiffBlock:
    tag: str
    left_start: int
    left_end: int
    right_start: int
    right_end: int


@dataclass(frozen=True)
class FindMatch:
    side: str
    start: int
    end: int


@dataclass(frozen=True)
class CursorSnapshot:
    position_logical_line: int | None
    position_display_line: int
    position_column: int
    anchor_logical_line: int | None
    anchor_display_line: int
    anchor_column: int
    had_selection: bool


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.line_number_background = QColor("#07111c")
        self.line_number_foreground = QColor("#3d6b93")

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(contents.left(), contents.top(), self.line_number_area_width(), contents.height())
        )

    def set_line_number_colors(self, background: str, foreground: str) -> None:
        self.line_number_background = QColor(background)
        self.line_number_foreground = QColor(foreground)
        self.line_number_area.update()

    def line_number_area_paint_event(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.line_number_background)
        painter.setPen(self.line_number_foreground)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1


class DiffGutter(QWidget):
    def __init__(self, owner: "DiffWindow") -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("ActionPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), _gutter_background_color(self.owner.theme))
        painter.setPen(Qt.PenStyle.NoPen)

        for block in self.owner.diff_blocks:
            band = self.owner._block_band(block)
            if band is None:
                continue
            left_top, left_bottom, right_top, right_bottom = band
            if max(left_bottom, right_bottom) < 0 or min(left_top, right_top) > self.height():
                continue
            painter.setBrush(_block_brush(block.tag, self.owner.theme))
            painter.setPen(QPen(_block_outline(block.tag, self.owner.theme), 1))
            painter.drawPath(_connector_path(self.width(), left_top, left_bottom, right_top, right_bottom))

        painter.setPen(QPen(_gutter_line_color(self.owner.theme), 1))
        painter.drawLine(0, 0, 0, self.height())
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())


class DiffMinimap(QWidget):
    def __init__(self, owner: "DiffWindow") -> None:
        super().__init__()
        self.owner = owner
        self.setObjectName("DiffMinimap")
        self.setFixedWidth(15)
        self.setMouseTracking(True)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), _minimap_background_color(self.owner.theme))

        total_lines = max(1, self.owner.right_edit.blockCount())
        for block in self.owner.diff_blocks:
            start = min(block.left_start, block.right_start)
            end = max(block.left_end, block.right_end, start + 1)
            top = self._line_to_y(start, total_lines)
            bottom = max(top + 2, self._line_to_y(end, total_lines))
            painter.fillRect(3, top, self.width() - 6, bottom - top, _minimap_block_color(block.tag, self.owner.theme))

        scroll_bar = self.owner.right_edit.verticalScrollBar()
        visible_top = scroll_bar.value()
        visible_bottom = min(total_lines, visible_top + scroll_bar.pageStep())
        viewport_top = self._line_to_y(visible_top, total_lines)
        viewport_bottom = max(viewport_top + 18, self._line_to_y(visible_bottom, total_lines))
        painter.setPen(QPen(_minimap_viewport_color(self.owner.theme), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, viewport_top, self.width() - 3, min(self.height() - viewport_top - 1, viewport_bottom - viewport_top), 2, 2)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        self._scroll_to_position(event.position().y())

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._scroll_to_position(event.position().y())

    def _line_to_y(self, line: int, total_lines: int) -> int:
        return round(max(0, min(line, total_lines)) / total_lines * max(1, self.height() - 1))

    def _scroll_to_position(self, y: float) -> None:
        total_lines = max(1, self.owner.right_edit.blockCount())
        scroll_bar = self.owner.right_edit.verticalScrollBar()
        target = round(max(0.0, min(y, float(self.height()))) / max(1, self.height()) * total_lines)
        target = max(0, target - scroll_bar.pageStep() // 2)
        self.owner._syncing_scroll = True
        self.owner.left_edit.verticalScrollBar().setValue(min(target, self.owner.left_edit.verticalScrollBar().maximum()))
        self.owner.right_edit.verticalScrollBar().setValue(min(target, scroll_bar.maximum()))
        self.owner._syncing_scroll = False
        self.owner._schedule_action_buttons_update()
        self.update()


class DiffPreviewPanel(QWidget):
    """Read-only side-by-side diff preview embedded in the main window."""

    def __init__(self, theme: Theme, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.line_styles: list[DiffLineStyle] = []
        self.inline_styles: list[InlineStyle] = []
        self.diff_blocks: list[DiffBlock] = []
        self.left_spacer_lines: set[int] = set()
        self.right_spacer_lines: set[int] = set()
        self.current_diff_index = -1
        self._syncing_scroll = False
        self._left_lines: list[str] = []
        self._right_lines: list[str] = []

        self.filename_label = QLabel("\u2014")
        self.filename_label.setObjectName("PreviewFileLabel")
        self.state_label = QLabel("")
        self.state_label.setObjectName("PreviewStateLabel")
        self.left_meta_label = QLabel("")
        self.left_meta_label.setObjectName("PreviewMetaLabel")
        self.right_meta_label = QLabel("")
        self.right_meta_label.setObjectName("PreviewMetaLabel")
        self.diff_counter_label = QLabel("0 / 0")
        self.diff_counter_label.setObjectName("PreviewCounterLabel")

        self.left_edit = CodeEditor()
        self.right_edit = CodeEditor()
        for edit in (self.left_edit, self.right_edit):
            edit.setReadOnly(True)
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            edit.setTabStopDistance(32)
            edit.setUndoRedoEnabled(False)
        self.left_edit.verticalScrollBar().valueChanged.connect(
            lambda _v: self._sync_scroll(self.left_edit)
        )
        self.right_edit.verticalScrollBar().valueChanged.connect(
            lambda _v: self._sync_scroll(self.right_edit)
        )

        self._build_ui()

    def _build_ui(self) -> None:
        prev_btn = QPushButton("\u25b2")
        next_btn = QPushButton("\u25bc")
        prev_btn.setObjectName("NavButton")
        next_btn.setObjectName("NavButton")
        prev_btn.setToolTip("Previous diff")
        next_btn.setToolTip("Next diff")
        prev_btn.clicked.connect(lambda: self._move_diff(-1))
        next_btn.clicked.connect(lambda: self._move_diff(1))

        # Row 1: filename + state  |  diff counter + nav buttons
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(10)
        row1.addWidget(self.filename_label)
        row1.addWidget(self.state_label)
        row1.addStretch(1)
        row1.addWidget(self.diff_counter_label)
        row1.addWidget(prev_btn)
        row1.addWidget(next_btn)

        # Row 2: left meta  |  right meta (aligned to match the two editors)
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(0)
        row2.addWidget(self.left_meta_label, 1)
        row2.addWidget(self.right_meta_label, 1)

        header = QWidget()
        header.setObjectName("PreviewHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 5, 10, 5)
        header_layout.setSpacing(3)
        header_layout.addLayout(row1)
        header_layout.addLayout(row2)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.left_edit)
        splitter.addWidget(self.right_edit)

        sep = QWidget()
        sep.setObjectName("TitleSeparator")
        sep.setFixedHeight(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sep)
        layout.addWidget(header)
        layout.addWidget(splitter, 1)

    def load(
        self,
        left_path: "Path | None",
        right_path: "Path | None",
        filename: str,
        state_text: str,
        left_meta: str,
        right_meta: str,
        *,
        is_directory: bool = False,
        is_binary: bool = False,
        is_too_large: bool = False,
    ) -> None:
        if is_directory or is_binary or is_too_large:
            self._show_metadata_only_message(
                filename,
                state_text,
                left_meta,
                right_meta,
                is_directory=is_directory,
                is_binary=is_binary,
            )
            return

        left_text = _safe_read(left_path)
        right_text = _safe_read(right_path)
        self._left_lines = left_text.splitlines()
        self._right_lines = right_text.splitlines()
        (
            left_display,
            right_display,
            self.left_spacer_lines,
            self.right_spacer_lines,
            self.line_styles,
            self.inline_styles,
            self.diff_blocks,
        ) = build_diff_view(
            self._left_lines,
            self._right_lines,
            ignore_whitespace=False,
            ignore_case=False,
            theme=self.theme,
        )
        self.left_edit.setPlainText("\n".join(left_display))
        self.right_edit.setPlainText("\n".join(right_display))
        self.filename_label.setText(filename)
        self.state_label.setText(state_text)
        self.left_meta_label.setText(left_meta)
        self.right_meta_label.setText(right_meta)
        self.current_diff_index = 0 if self.diff_blocks else -1
        self._update_diff_counter()
        self._apply_editor_theme()
        if self.diff_blocks:
            first_block = self.diff_blocks[0]
            QTimer.singleShot(0, lambda: self._scroll_to_diff(first_block))

    def _show_metadata_only_message(
        self,
        filename: str,
        state_text: str,
        left_meta: str,
        right_meta: str,
        *,
        is_directory: bool,
        is_binary: bool,
    ) -> None:
        if is_directory:
            message = "Directory. Text diff is not available."
        elif is_binary:
            message = "Binary file. Text diff is not available."
        else:
            message = "File is larger than 10 MB. Text diff is not available."
        self._left_lines = []
        self._right_lines = []
        self.left_spacer_lines = set()
        self.right_spacer_lines = set()
        self.line_styles = []
        self.inline_styles = []
        self.diff_blocks = []
        self.current_diff_index = -1
        self.left_edit.setPlainText(message)
        self.right_edit.setPlainText(message)
        self.filename_label.setText(filename)
        self.state_label.setText(state_text)
        self.left_meta_label.setText(left_meta)
        self.right_meta_label.setText(right_meta)
        self._update_diff_counter()
        self._apply_editor_theme()

    def clear(self) -> None:
        self.left_edit.setPlainText("")
        self.right_edit.setPlainText("")
        self.filename_label.setText("\u2014")
        self.state_label.setText("")
        self.left_meta_label.setText("")
        self.right_meta_label.setText("")
        self.diff_counter_label.setText("0 / 0")
        self.diff_blocks = []
        self.line_styles = []
        self.inline_styles = []
        self._left_lines = []
        self._right_lines = []

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        if self._left_lines or self._right_lines:
            (
                _,
                _,
                self.left_spacer_lines,
                self.right_spacer_lines,
                self.line_styles,
                self.inline_styles,
                self.diff_blocks,
            ) = build_diff_view(
                self._left_lines,
                self._right_lines,
                ignore_whitespace=False,
                ignore_case=False,
                theme=theme,
            )
        self._apply_editor_theme()

    def _apply_editor_theme(self) -> None:
        sel_color = "#1e3d6e" if self.theme.name == "Dark" else "#add6ff"
        editor_style = (
            f"QPlainTextEdit {{ background: {self.theme.editor_background}; "
            f"color: {self.theme.editor_foreground}; "
            f"font-family: {DIFF_FONT_FAMILY}; "
            f"font-size: {DIFF_FONT_SIZE}; "
            f"selection-background-color: {sel_color}; }}"
        )
        self.left_edit.setStyleSheet(editor_style)
        self.right_edit.setStyleSheet(editor_style)
        ln_bg = "#e4ecf4" if self.theme.name == "Light" else "#070e17"
        ln_fg = "#8aaac4" if self.theme.name == "Light" else "#2e5878"
        self.left_edit.set_line_number_colors(ln_bg, ln_fg)
        self.right_edit.set_line_number_colors(ln_bg, ln_fg)
        self._apply_selections()

    def _apply_selections(self) -> None:
        self.left_edit.setExtraSelections(self._selections_for("left"))
        self.right_edit.setExtraSelections(self._selections_for("right"))

    def _selections_for(self, side: str) -> list["QTextEdit.ExtraSelection"]:
        edit = self.left_edit if side == "left" else self.right_edit
        selections: list[QTextEdit.ExtraSelection] = []
        for style in self.line_styles:
            if style.side == side:
                selections.append(_line_selection(edit, style.line, style.color))
        for style in self.inline_styles:
            if style.side == side:
                selections.append(_range_selection(edit, style.line, style.start, style.end, self.theme.inline_changed))
        return selections

    def _sync_scroll(self, source: QPlainTextEdit) -> None:
        if self._syncing_scroll:
            return
        target = self.right_edit if source is self.left_edit else self.left_edit
        self._syncing_scroll = True
        target.verticalScrollBar().setValue(
            min(source.verticalScrollBar().value(), target.verticalScrollBar().maximum())
        )
        self._syncing_scroll = False

    def _move_diff(self, delta: int) -> None:
        if not self.diff_blocks:
            return
        if self.current_diff_index < 0:
            self.current_diff_index = 0 if delta >= 0 else len(self.diff_blocks) - 1
        else:
            self.current_diff_index = (self.current_diff_index + delta) % len(self.diff_blocks)
        self._scroll_to_diff(self.diff_blocks[self.current_diff_index])
        self._update_diff_counter()

    def _scroll_to_diff(self, block: DiffBlock) -> None:
        target_line = min(v for v in (block.left_start, block.right_start) if v >= 0)
        top_line = max(0, target_line - 3)
        self._syncing_scroll = True
        for edit in (self.left_edit, self.right_edit):
            edit.verticalScrollBar().setValue(min(top_line, edit.verticalScrollBar().maximum()))
        self._syncing_scroll = False

    def _update_diff_counter(self) -> None:
        if not self.diff_blocks:
            self.diff_counter_label.setText("0 / 0")
        else:
            self.diff_counter_label.setText(f"{self.current_diff_index + 1} / {len(self.diff_blocks)}")


def _safe_read(path: "Path | None") -> str:
    if path is None:
        return ""
    try:
        return _read_text(path)
    except OSError:
        return ""


class DiffWindow(QMainWindow):
    theme_changed = Signal(bool)
    files_saved = Signal()

    def __init__(
        self,
        left_path: Path,
        right_path: Path,
        *,
        ignore_whitespace: bool = False,
        ignore_case: bool = False,
        dark_theme: bool = True,
    ) -> None:
        super().__init__()
        self.left_path = left_path
        self.right_path = right_path
        self.ignore_whitespace = ignore_whitespace
        self.ignore_case = ignore_case
        self.theme = DARK_THEME if dark_theme else LIGHT_THEME
        self.active_side = "left"
        self.line_styles: list[DiffLineStyle] = []
        self.inline_styles: list[InlineStyle] = []
        self.diff_blocks: list[DiffBlock] = []
        self.left_spacer_lines: set[int] = set()
        self.right_spacer_lines: set[int] = set()
        self.find_query = ""
        self.find_matches: list[FindMatch] = []
        self.current_find_index = -1
        self.current_diff_index = -1
        self._loading = True
        self._syncing_scroll = False
        self._action_update_pending = False
        self.action_buttons: list[QPushButton] = []
        self._undo_stack: list[tuple[str, str]] = []
        self._redo_stack: list[tuple[str, str]] = []
        self._typing_snapshot_pending = False
        self._last_stable: tuple[str, str] = ("", "")

        self.left_edit = CodeEditor()
        self.right_edit = CodeEditor()
        self.status_label = QLabel()
        self.diff_counter_label = QLabel("0 / 0")
        self.action_panel = DiffGutter(self)
        self.minimap = DiffMinimap(self)
        self.recompare_timer = QTimer(self)
        self.recompare_timer.setSingleShot(True)
        self.recompare_timer.setInterval(1000)
        self.recompare_timer.timeout.connect(self.recompare)

        self._build_ui()
        self._load_files()
        self._loading = False
        self.recompare()
        self.apply_theme(self.theme)
        if self.diff_blocks:
            first_block = self.diff_blocks[0]
            QTimer.singleShot(0, lambda: self._scroll_to_diff(first_block))

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{self.left_path.name} - SmartDiff")
        self.resize(1380, 860)
        self._build_menu()

        self.left_edit.setObjectName("leftEditor")
        self.right_edit.setObjectName("rightEditor")
        for edit in (self.left_edit, self.right_edit):
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            edit.setTabStopDistance(32)
            edit.setUndoRedoEnabled(False)
            edit.installEventFilter(self)
            edit.textChanged.connect(self._on_text_changed)
            edit.verticalScrollBar().valueChanged.connect(lambda _value, source=edit: self._sync_scroll(source))
            edit.verticalScrollBar().valueChanged.connect(lambda _value: self._schedule_action_buttons_update())
            edit.verticalScrollBar().valueChanged.connect(lambda _value: self.minimap.update())

        self._build_action_panel()

        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 6, 8, 6)
        title_layout.setSpacing(0)
        left_title = QLabel(f"Left: {self.left_path}")
        left_title.setObjectName("PathLabel")
        right_title = QLabel(f"Right: {self.right_path}")
        right_title.setObjectName("PathLabel")
        right_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        center_title = QWidget()
        center_title.setMinimumWidth(self.action_panel.minimumWidth())
        center_title.setMaximumWidth(self.action_panel.maximumWidth())
        center_layout = QHBoxLayout(center_title)
        center_layout.setContentsMargins(0, 0, 0, 0)
        nav_panel = QWidget()
        nav_layout = QHBoxLayout(nav_panel)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)
        previous_diff = QPushButton("\u25b2")
        next_diff = QPushButton("\u25bc")
        previous_diff.setObjectName("NavButton")
        next_diff.setObjectName("NavButton")
        previous_diff.setToolTip("Previous diff")
        next_diff.setToolTip("Next diff")
        previous_diff.clicked.connect(lambda: self.move_diff(-1))
        next_diff.clicked.connect(lambda: self.move_diff(1))
        nav_layout.addWidget(self.diff_counter_label)
        nav_layout.addWidget(previous_diff)
        nav_layout.addWidget(next_diff)
        right_header = QWidget()
        right_header_layout = QHBoxLayout(right_header)
        right_header_layout.setContentsMargins(0, 0, 0, 0)
        right_header_layout.setSpacing(8)
        right_header_layout.addWidget(right_title, 1)
        right_header_layout.addWidget(nav_panel, 0, Qt.AlignmentFlag.AlignRight)

        title_layout.addWidget(left_title, 1)
        title_layout.addWidget(center_title)
        title_layout.addWidget(right_header, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        right_content = QWidget()
        right_content_layout = QHBoxLayout(right_content)
        right_content_layout.setContentsMargins(0, 0, 0, 0)
        right_content_layout.setSpacing(0)
        right_content_layout.addWidget(self.right_edit, 1)
        right_content_layout.addWidget(self.minimap)
        splitter.addWidget(self.left_edit)
        splitter.addWidget(self.action_panel)
        splitter.addWidget(right_content)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        splitter.setSizes([650, ACTION_PANEL_WIDTH, 650])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        title_sep = QWidget()
        title_sep.setObjectName("TitleSeparator")
        title_sep.setFixedHeight(1)
        layout.addWidget(title_bar)
        layout.addWidget(title_sep)
        layout.addSpacing(6)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _build_action_panel(self) -> None:
        self.action_panel.setObjectName("ActionPanel")
        self.action_panel.setFixedWidth(ACTION_PANEL_WIDTH)
        self.action_panel.setContentsMargins(0, 0, 0, 0)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        save_action = QAction("Save", self)
        reload_action = QAction("Reload Files", self)
        exit_action = QAction("Exit", self)
        save_action.setShortcut("Ctrl+S")
        reload_action.setShortcut("Ctrl+R")
        save_action.triggered.connect(self.save)
        reload_action.triggered.connect(self.reload_files)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(save_action)
        file_menu.addAction(reload_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu("Edit")
        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        find_action = QAction("Find", self)
        find_next = QAction("Find Next", self)
        find_prev = QAction("Find Previous", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.redo_action.setShortcut("Ctrl+Y")
        find_action.setShortcut("Ctrl+F")
        find_next.setShortcut("F3")
        find_prev.setShortcut("Shift+F3")
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.undo_action.triggered.connect(self.global_undo)
        self.redo_action.triggered.connect(self.global_redo)
        find_action.triggered.connect(self.find)
        find_next.triggered.connect(lambda: self.move_find(1))
        find_prev.triggered.connect(lambda: self.move_find(-1))
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(find_action)
        edit_menu.addAction(find_next)
        edit_menu.addAction(find_prev)

        options_menu = self.menuBar().addMenu("Options")
        self.ignore_whitespace_action = QAction("Ignore whitespace", self, checkable=True)
        self.ignore_case_action = QAction("Ignore case", self, checkable=True)
        self.theme_action = QAction("Light theme", self, checkable=True)
        self.ignore_whitespace_action.setChecked(self.ignore_whitespace)
        self.ignore_case_action.setChecked(self.ignore_case)
        self.theme_action.setChecked(self.theme.name == "Light")
        self.ignore_whitespace_action.toggled.connect(self._set_ignore_whitespace)
        self.ignore_case_action.toggled.connect(self._set_ignore_case)
        self.theme_action.toggled.connect(self._set_light_theme)
        options_menu.addAction(self.ignore_whitespace_action)
        options_menu.addAction(self.ignore_case_action)
        options_menu.addSeparator()
        options_menu.addAction(self.theme_action)

        help_menu = self.menuBar().addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "About SmartDiff",
                "SmartDiff\nPython 3.12 + PySide6 diff viewer.",
            )
        )
        help_menu.addAction(about_action)

    def _load_files(self) -> None:
        self.left_original = _read_text(self.left_path).replace("\r\n", "\n").replace("\r", "\n")
        self.right_original = _read_text(self.right_path).replace("\r\n", "\n").replace("\r", "\n")
        self.left_edit.setPlainText(self.left_original)
        self.right_edit.setPlainText(self.right_original)
        self.left_edit.document().setModified(False)
        self.right_edit.document().setModified(False)

    def reload_files(self) -> None:
        if self._has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                "Reload Files",
                "All unsaved changes will be lost. Reload anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_actions()
        self._loading = True
        self._load_files()
        self._loading = False
        self.recompare()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.left_edit and event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            self.active_side = "left"
        elif watched is self.right_edit and event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            self.active_side = "right"
        return super().eventFilter(watched, event)

    def _on_text_changed(self) -> None:
        if not self._loading:
            if not self._typing_snapshot_pending:
                self._typing_snapshot_pending = True
                self._undo_stack.append(self._last_stable)
                self._redo_stack.clear()
                self._update_undo_redo_actions()
            self.recompare_timer.start()

    def recompare(self) -> None:
        left_lines = self._logical_lines("left")
        right_lines = self._logical_lines("right")
        left_modified = "\n".join(left_lines) != self.left_original
        right_modified = "\n".join(right_lines) != self.right_original
        (
            left_display,
            right_display,
            self.left_spacer_lines,
            self.right_spacer_lines,
            self.line_styles,
            self.inline_styles,
            self.diff_blocks,
        ) = build_diff_view(
            left_lines,
            right_lines,
            ignore_whitespace=self.ignore_whitespace,
            ignore_case=self.ignore_case,
            theme=self.theme,
        )
        self._set_display_texts(left_display, right_display, left_modified, right_modified)
        self.status_label.setText("")
        self._normalize_current_diff_index()
        self._update_diff_counter()
        if self.find_query:
            self._refresh_find_matches(keep_current=True)
        self._apply_selections()
        self._schedule_action_buttons_update()
        self.minimap.update()
        self._typing_snapshot_pending = False
        self._last_stable = (self._logical_text("left"), self._logical_text("right"))

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        previous_blocked = self.theme_action.blockSignals(True)
        self.theme_action.setChecked(theme.name == "Light")
        self.theme_action.blockSignals(previous_blocked)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.stylesheet)
        sel_color = "#1e3d6e" if theme.name == "Dark" else "#add6ff"
        editor_style = (
            f"QPlainTextEdit {{ background: {theme.editor_background}; "
            f"color: {theme.editor_foreground}; "
            f"font-family: {DIFF_FONT_FAMILY}; "
            f"font-size: {DIFF_FONT_SIZE}; "
            f"selection-background-color: {sel_color}; }}"
        )
        self.left_edit.setStyleSheet(editor_style)
        self.right_edit.setStyleSheet(editor_style)
        self.minimap.update()
        line_number_background = "#e4ecf4" if theme.name == "Light" else "#070e17"
        line_number_foreground = "#8aaac4" if theme.name == "Light" else "#2e5878"
        self.left_edit.set_line_number_colors(line_number_background, line_number_foreground)
        self.right_edit.set_line_number_colors(line_number_background, line_number_foreground)
        self.recompare()
        self.theme_changed.emit(theme.name == "Dark")

    def _apply_selections(self) -> None:
        self.left_edit.setExtraSelections(self._selections_for("left"))
        self.right_edit.setExtraSelections(self._selections_for("right"))

    def _sync_scroll(self, source: QPlainTextEdit) -> None:
        if self._syncing_scroll:
            return

        target = self.right_edit if source is self.left_edit else self.left_edit
        source_bar = source.verticalScrollBar()
        target_bar = target.verticalScrollBar()
        target_value = min(source_bar.value(), target_bar.maximum())

        self._syncing_scroll = True
        target_bar.setValue(target_value)
        self._syncing_scroll = False

    def _schedule_action_buttons_update(self) -> None:
        if self._action_update_pending:
            return
        self._action_update_pending = True
        QTimer.singleShot(0, self._update_action_buttons)

    def _update_action_buttons(self) -> None:
        self._action_update_pending = False
        for button in self.action_buttons:
            button.deleteLater()
        self.action_buttons.clear()

        if self.action_panel.width() <= 0 or self.action_panel.height() <= 0:
            return
        if not self.diff_blocks:
            self.action_panel.update()
            self.minimap.update()
            return

        occupied: list[tuple[int, int]] = []
        for block in self.diff_blocks:
            y = self._block_y(block)
            if y is None or y > self.action_panel.height() - 24:
                continue

            y = max(2, y)
            y = self._avoid_button_overlap(y, occupied)
            occupied.append((y, y + 22))

            columns = _button_columns(self.action_panel.width())
            buttons: list[QPushButton] = []
            show_delete_buttons = _block_is_one_sided(block)
            if show_delete_buttons and _block_has_side_lines(block, "left"):
                left_delete = _action_button("x", _delete_tooltip(block, "left"), self.action_panel, "DeleteActionButton")
                left_delete.clicked.connect(lambda _checked=False, item=block: self.delete_diff_block(item, "left"))
                left_delete.setGeometry(columns[0], y, 20, 20)
                buttons.append(left_delete)

            if _block_has_side_lines(block, "left"):
                copy_right = _action_button("\u00bb", _block_tooltip(block, "left", "right"), self.action_panel, "CopyActionButton")
                copy_right.clicked.connect(lambda _checked=False, item=block: self.copy_diff_block(item, "left", "right"))
                copy_right.setGeometry(columns[1], y, 20, 20)
                buttons.append(copy_right)

            if _block_has_side_lines(block, "right"):
                copy_left = _action_button("\u00ab", _block_tooltip(block, "right", "left"), self.action_panel, "CopyActionButton")
                copy_left.clicked.connect(lambda _checked=False, item=block: self.copy_diff_block(item, "right", "left"))
                copy_left.setGeometry(columns[2], y, 20, 20)
                buttons.append(copy_left)

            if show_delete_buttons and _block_has_side_lines(block, "right"):
                right_delete = _action_button("x", _delete_tooltip(block, "right"), self.action_panel, "DeleteActionButton")
                right_delete.clicked.connect(lambda _checked=False, item=block: self.delete_diff_block(item, "right"))
                right_delete.setGeometry(columns[3], y, 20, 20)
                buttons.append(right_delete)

            for button in buttons:
                button.show()
            self.action_buttons.extend(buttons)
        self.action_panel.update()

    def _block_y(self, block: DiffBlock) -> int | None:
        left_range = self._line_range_y(self.left_edit, block.left_start, block.left_end)
        right_range = self._line_range_y(self.right_edit, block.right_start, block.right_end)
        left_y = _range_center(left_range)
        right_y = _range_center(right_range)
        values = [value for value in (left_y, right_y) if value is not None]
        if not values:
            return None
        return round(sum(values) / len(values)) - 10

    def _block_band(self, block: DiffBlock) -> tuple[int, int, int, int] | None:
        left_range = self._line_range_y(self.left_edit, block.left_start, block.left_end)
        right_range = self._line_range_y(self.right_edit, block.right_start, block.right_end)
        if left_range is None and right_range is None:
            return None
        if left_range is None:
            left_range = right_range
        if right_range is None:
            right_range = left_range
        if left_range is None or right_range is None:
            return None
        return left_range[0], left_range[1], right_range[0], right_range[1]

    def _line_range_y(self, edit: QPlainTextEdit, start: int, end: int) -> tuple[int, int] | None:
        if start >= end:
            return self._line_boundary_y(edit, start)

        first = edit.document().findBlockByNumber(start)
        last = edit.document().findBlockByNumber(end - 1)
        if not first.isValid() or not last.isValid():
            return None

        first_geometry = edit.blockBoundingGeometry(first).translated(edit.contentOffset())
        last_geometry = edit.blockBoundingGeometry(last).translated(edit.contentOffset())
        top = int(first_geometry.top())
        bottom = int(last_geometry.bottom())
        if bottom < 0 or top > edit.viewport().height():
            return None

        global_position = edit.viewport().mapToGlobal(QPoint(0, top))
        mapped_top = self.action_panel.mapFromGlobal(global_position).y()
        return mapped_top, mapped_top + max(16, bottom - top)

    def _line_boundary_y(self, edit: QPlainTextEdit, line: int) -> tuple[int, int] | None:
        line = max(0, min(line, edit.document().blockCount() - 1))
        block = edit.document().findBlockByNumber(line)
        if not block.isValid():
            return None
        geometry = edit.blockBoundingGeometry(block).translated(edit.contentOffset())
        y = int(geometry.top())
        if y < -24 or y > edit.viewport().height() + 24:
            return None
        global_position = edit.viewport().mapToGlobal(QPoint(0, y))
        mapped_y = self.action_panel.mapFromGlobal(global_position).y()
        return mapped_y - 1, mapped_y + 1

    def _avoid_button_overlap(self, y: int, occupied: list[tuple[int, int]]) -> int:
        result = y
        for start, end in occupied:
            if start - 20 <= result <= end + 2:
                result = end + 3
        return min(result, max(24, self.action_panel.height() - 24))

    def _selections_for(self, side: str) -> list[QTextEdit.ExtraSelection]:
        edit = self.left_edit if side == "left" else self.right_edit
        selections: list[QTextEdit.ExtraSelection] = []
        for style in self.line_styles:
            if style.side == side:
                selections.append(_line_selection(edit, style.line, style.color))
        for style in self.inline_styles:
            if style.side == side:
                selections.append(_range_selection(edit, style.line, style.start, style.end, self.theme.inline_changed))
        for match_index, match in enumerate(self.find_matches):
            if match.side == side:
                color = self.theme.find_current if match_index == self.current_find_index else self.theme.find_all
                selections.append(_absolute_selection(edit, match.start, match.end, color))
        return selections

    def find(self) -> None:
        query, ok = QInputDialog.getText(self, "Find", f"Find in {self.active_side}:")
        if ok:
            self.find_query = query
            self._refresh_find_matches(keep_current=False)
            self.move_find(0)

    def move_find(self, delta: int) -> None:
        if not self.find_matches:
            self._apply_selections()
            return
        if self.current_find_index < 0:
            self.current_find_index = 0
        else:
            self.current_find_index = (self.current_find_index + delta) % len(self.find_matches)
        match = self.find_matches[self.current_find_index]
        edit = self.left_edit if match.side == "left" else self.right_edit
        self.active_side = match.side
        cursor = edit.textCursor()
        cursor.setPosition(match.start)
        cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
        edit.setTextCursor(cursor)
        edit.centerCursor()
        edit.setFocus()
        self._apply_selections()

    def move_diff(self, delta: int) -> None:
        if not self.diff_blocks:
            self.current_diff_index = -1
            self._update_diff_counter()
            return
        if self.current_diff_index < 0:
            self.current_diff_index = 0 if delta >= 0 else len(self.diff_blocks) - 1
        else:
            self.current_diff_index = (self.current_diff_index + delta) % len(self.diff_blocks)
        self._scroll_to_diff(self.diff_blocks[self.current_diff_index])
        self._update_diff_counter()

    def _scroll_to_diff(self, block: DiffBlock) -> None:
        target_line = min(
            value
            for value in (block.left_start, block.right_start)
            if value >= 0
        )
        top_line = max(0, target_line - 3)
        self._syncing_scroll = True
        self.left_edit.verticalScrollBar().setValue(min(top_line, self.left_edit.verticalScrollBar().maximum()))
        self.right_edit.verticalScrollBar().setValue(min(top_line, self.right_edit.verticalScrollBar().maximum()))
        self._syncing_scroll = False
        self._schedule_action_buttons_update()

    def _normalize_current_diff_index(self) -> None:
        if not self.diff_blocks:
            self.current_diff_index = -1
        elif self.current_diff_index < 0:
            self.current_diff_index = 0
        else:
            self.current_diff_index = min(self.current_diff_index, len(self.diff_blocks) - 1)

    def _update_diff_counter(self) -> None:
        if not self.diff_blocks:
            self.diff_counter_label.setText("0 / 0")
            return
        self.diff_counter_label.setText(f"{self.current_diff_index + 1} / {len(self.diff_blocks)}")

    def _refresh_find_matches(self, *, keep_current: bool) -> None:
        previous = self.current_find_index if keep_current else -1
        self.find_matches = []
        if self.find_query:
            text = self._active_edit().toPlainText()
            start = 0
            while True:
                index = text.find(self.find_query, start)
                if index < 0:
                    break
                self.find_matches.append(FindMatch(self.active_side, index, index + len(self.find_query)))
                start = index + max(1, len(self.find_query))
        self.current_find_index = min(previous, len(self.find_matches) - 1)
        self.status_label.setText(f"{len(self.find_matches)} match(es)" if self.find_query else self.status_label.text())

    def _active_edit(self) -> QPlainTextEdit:
        return self.left_edit if self.active_side == "left" else self.right_edit

    def _logical_lines(self, side: str) -> list[str]:
        edit = self.left_edit if side == "left" else self.right_edit
        spacers = self.left_spacer_lines if side == "left" else self.right_spacer_lines
        return [line for index, line in enumerate(edit.toPlainText().split("\n")) if index not in spacers]

    def _logical_text(self, side: str) -> str:
        return "\n".join(self._logical_lines(side))

    def _set_display_texts(
        self,
        left_lines: list[str],
        right_lines: list[str],
        left_modified: bool,
        right_modified: bool,
    ) -> None:
        left_text = "\n".join(left_lines)
        right_text = "\n".join(right_lines)
        left_scroll = self.left_edit.verticalScrollBar().value()
        right_scroll = self.right_edit.verticalScrollBar().value()

        self._loading = True
        if self.left_edit.toPlainText() != left_text:
            self._replace_text("left", self.left_edit, left_text)
        if self.right_edit.toPlainText() != right_text:
            self._replace_text("right", self.right_edit, right_text)
        self._loading = False

        self.left_edit.document().setModified(left_modified)
        self.right_edit.document().setModified(right_modified)
        self.left_edit.verticalScrollBar().setValue(min(left_scroll, self.left_edit.verticalScrollBar().maximum()))
        self.right_edit.verticalScrollBar().setValue(min(right_scroll, self.right_edit.verticalScrollBar().maximum()))

    def _replace_text(self, side: str, edit: QPlainTextEdit, new_text: str) -> None:
        snapshot = self._capture_cursor_snapshot(side, edit.textCursor())

        cursor = edit.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()

        self._restore_cursor_snapshot(side, edit, snapshot)

    def _capture_cursor_snapshot(self, side: str, cursor: QTextCursor) -> CursorSnapshot:
        anchor_cursor = QTextCursor(cursor)
        anchor_cursor.setPosition(cursor.anchor())
        return CursorSnapshot(
            position_logical_line=self._display_line_to_logical(side, cursor.blockNumber()),
            position_display_line=cursor.blockNumber(),
            position_column=cursor.positionInBlock(),
            anchor_logical_line=self._display_line_to_logical(side, anchor_cursor.blockNumber()),
            anchor_display_line=anchor_cursor.blockNumber(),
            anchor_column=anchor_cursor.positionInBlock(),
            had_selection=cursor.hasSelection(),
        )

    def _restore_cursor_snapshot(self, side: str, edit: QPlainTextEdit, snapshot: CursorSnapshot) -> None:
        restored_cursor = edit.textCursor()
        anchor_position = self._cursor_position_from_snapshot(
            side,
            edit,
            snapshot.anchor_logical_line,
            snapshot.anchor_display_line,
            snapshot.anchor_column,
        )
        position = self._cursor_position_from_snapshot(
            side,
            edit,
            snapshot.position_logical_line,
            snapshot.position_display_line,
            snapshot.position_column,
        )
        restored_cursor.setPosition(anchor_position)
        restored_cursor.setPosition(
            position,
            QTextCursor.MoveMode.KeepAnchor if snapshot.had_selection else QTextCursor.MoveMode.MoveAnchor,
        )
        edit.setTextCursor(restored_cursor)

    def _cursor_position_from_snapshot(
        self,
        side: str,
        edit: QPlainTextEdit,
        logical_line: int | None,
        display_line: int,
        column: int,
    ) -> int:
        if logical_line is None:
            target_line = min(display_line, max(0, edit.document().blockCount() - 1))
        else:
            target_line = self._logical_line_to_display(side, logical_line)
        block = edit.document().findBlockByNumber(target_line)
        if not block.isValid():
            return 0
        return block.position() + min(column, len(block.text()))

    def _display_line_to_logical(self, side: str, display_line: int) -> int | None:
        spacers = self.left_spacer_lines if side == "left" else self.right_spacer_lines
        if display_line in spacers:
            return None
        return sum(1 for index in range(display_line) if index not in spacers)

    def _logical_line_to_display(self, side: str, logical_line: int) -> int:
        edit = self.left_edit if side == "left" else self.right_edit
        spacers = self.left_spacer_lines if side == "left" else self.right_spacer_lines
        current_logical = 0
        last_non_spacer = 0
        for display_line in range(edit.document().blockCount()):
            if display_line in spacers:
                continue
            last_non_spacer = display_line
            if current_logical == logical_line:
                return display_line
            current_logical += 1
        return last_non_spacer

    def _display_range_to_logical(self, side: str, start: int, end: int) -> tuple[int, int]:
        spacers = self.left_spacer_lines if side == "left" else self.right_spacer_lines
        logical_start = sum(1 for index in range(start) if index not in spacers)
        logical_end = logical_start + sum(1 for index in range(start, end) if index not in spacers)
        return logical_start, logical_end

    def copy_current_line(self, source_side: str, target_side: str) -> None:
        self._push_undo_snapshot()
        source_edit = self.left_edit if source_side == "left" else self.right_edit
        line_number = source_edit.textCursor().blockNumber()
        source_lines = self._logical_lines(source_side)
        target_lines = self._logical_lines(target_side)
        source_index, source_end = self._display_range_to_logical(source_side, line_number, line_number + 1)
        target_index, target_end = self._display_range_to_logical(target_side, line_number, line_number + 1)
        if source_index >= source_end or source_index >= len(source_lines):
            return
        while len(target_lines) < target_index:
            target_lines.append("")
        target_lines[target_index:target_end] = [source_lines[source_index]]
        if target_side == "left":
            self._render_logical_lines(target_lines, self._logical_lines("right"))
        else:
            self._render_logical_lines(self._logical_lines("left"), target_lines)

    def copy_current_block(self, source_side: str, target_side: str) -> None:
        self._push_undo_snapshot()
        source_edit = self.left_edit if source_side == "left" else self.right_edit
        target_edit = self.left_edit if target_side == "left" else self.right_edit
        source_line = source_edit.textCursor().blockNumber()
        block = self._changed_block_for(source_side, source_line)
        if block is None:
            self.copy_current_line(source_side, target_side)
            return

        start, end = block
        source_lines = source_edit.toPlainText().splitlines()
        target_lines = target_edit.toPlainText().splitlines()
        if start >= len(source_lines):
            return

        while len(target_lines) < start:
            target_lines.append("")
        while len(target_lines) < end:
            target_lines.append("")

        target_lines[start:end] = source_lines[start:min(end, len(source_lines))]
        self._replace_text(target_side, target_edit, "\n".join(target_lines))
        target_edit.document().setModified(True)
        self.recompare()

    def copy_diff_block(self, block: DiffBlock, source_side: str, target_side: str) -> None:
        self._push_undo_snapshot()
        source_start, source_end = _block_range(block, source_side)
        target_start, target_end = _block_range(block, target_side)
        source_logical_start, source_logical_end = self._display_range_to_logical(source_side, source_start, source_end)
        target_logical_start, target_logical_end = self._display_range_to_logical(target_side, target_start, target_end)

        source_lines = self._logical_lines(source_side)
        target_lines = self._logical_lines(target_side)
        replacement = source_lines[source_logical_start:source_logical_end]

        while len(target_lines) < target_logical_start:
            target_lines.append("")
        target_lines[target_logical_start:target_logical_end] = replacement
        if target_side == "left":
            self._render_logical_lines(target_lines, self._logical_lines("right"))
        else:
            self._render_logical_lines(self._logical_lines("left"), target_lines)

    def delete_diff_block(self, block: DiffBlock, side: str) -> None:
        self._push_undo_snapshot()
        start, end = _block_range(block, side)
        logical_start, logical_end = self._display_range_to_logical(side, start, end)
        if logical_start >= logical_end:
            return

        lines = self._logical_lines(side)
        del lines[logical_start:logical_end]
        if side == "left":
            self._render_logical_lines(lines, self._logical_lines("right"))
        else:
            self._render_logical_lines(self._logical_lines("left"), lines)

    def _changed_block_for(self, side: str, line: int) -> tuple[int, int] | None:
        changed_lines = sorted(style.line for style in self.line_styles if style.side == side)
        if line not in changed_lines:
            nearest = min(changed_lines, key=lambda item: abs(item - line), default=None)
            if nearest is None:
                return None
            line = nearest

        start = line
        while start - 1 in changed_lines:
            start -= 1

        end = line + 1
        while end in changed_lines:
            end += 1

        return start, end

    def save(self) -> None:
        self.left_path.write_text(self._logical_text("left"), encoding="utf-8")
        self.right_path.write_text(self._logical_text("right"), encoding="utf-8")
        self.left_original = self._logical_text("left")
        self.right_original = self._logical_text("right")
        self.left_edit.document().setModified(False)
        self.right_edit.document().setModified(False)
        self.status_label.setText("Saved")
        self.files_saved.emit()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if self._has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                "Unsaved changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Save:
                self.save()
            elif answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()

    def _has_unsaved_changes(self) -> bool:
        return (
            self._logical_text("left") != self.left_original
            or self._logical_text("right") != self.right_original
        )

    def _push_undo_snapshot(self) -> None:
        self._undo_stack.append((self._logical_text("left"), self._logical_text("right")))
        self._redo_stack.clear()
        self._typing_snapshot_pending = False
        self._update_undo_redo_actions()

    def global_undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append((self._logical_text("left"), self._logical_text("right")))
        left_text, right_text = self._undo_stack.pop()
        self._apply_snapshot(left_text, right_text)
        self._update_undo_redo_actions()

    def global_redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append((self._logical_text("left"), self._logical_text("right")))
        left_text, right_text = self._redo_stack.pop()
        self._apply_snapshot(left_text, right_text)
        self._update_undo_redo_actions()

    def _apply_snapshot(self, left_text: str, right_text: str) -> None:
        self._typing_snapshot_pending = False
        self._render_logical_lines(left_text.split("\n"), right_text.split("\n"))
        self._last_stable = (left_text, right_text)

    def _update_undo_redo_actions(self) -> None:
        self.undo_action.setEnabled(bool(self._undo_stack))
        self.redo_action.setEnabled(bool(self._redo_stack))

    def _render_logical_lines(self, left_lines: list[str], right_lines: list[str]) -> None:
        (
            left_display,
            right_display,
            self.left_spacer_lines,
            self.right_spacer_lines,
            self.line_styles,
            self.inline_styles,
            self.diff_blocks,
        ) = build_diff_view(
            left_lines,
            right_lines,
            ignore_whitespace=self.ignore_whitespace,
            ignore_case=self.ignore_case,
            theme=self.theme,
        )
        self._set_display_texts(
            left_display,
            right_display,
            "\n".join(left_lines) != self.left_original,
            "\n".join(right_lines) != self.right_original,
        )
        self._apply_selections()
        self._normalize_current_diff_index()
        self._update_diff_counter()
        self._schedule_action_buttons_update()
        self.minimap.update()
        self.action_panel.update()
        self._last_stable = ("\n".join(left_lines), "\n".join(right_lines))
        self._typing_snapshot_pending = False

    def _set_ignore_whitespace(self, value: bool) -> None:
        self.ignore_whitespace = value
        self.recompare()

    def _set_ignore_case(self, value: bool) -> None:
        self.ignore_case = value
        self.recompare()

    def _set_light_theme(self, value: bool) -> None:
        self.apply_theme(LIGHT_THEME if value else DARK_THEME)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._schedule_action_buttons_update()


def build_diff_view(
    left_lines: list[str],
    right_lines: list[str],
    *,
    ignore_whitespace: bool,
    ignore_case: bool,
    theme: Theme,
) -> tuple[
    list[str],
    list[str],
    set[int],
    set[int],
    list[DiffLineStyle],
    list[InlineStyle],
    list[DiffBlock],
]:
    normalized_left = [_normalize(line, ignore_whitespace, ignore_case) for line in left_lines]
    normalized_right = [_normalize(line, ignore_whitespace, ignore_case) for line in right_lines]
    matcher = difflib.SequenceMatcher(None, normalized_left, normalized_right, autojunk=False)
    left_display: list[str] = []
    right_display: list[str] = []
    left_spacers: set[int] = set()
    right_spacers: set[int] = set()
    line_styles: list[DiffLineStyle] = []
    inline_styles: list[InlineStyle] = []
    diff_blocks: list[DiffBlock] = []

    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            left_display.extend(left_lines[left_start:left_end])
            right_display.extend(right_lines[right_start:right_end])
            continue

        display_start = len(left_display)
        block_left_start = display_start
        block_left_end = display_start
        block_right_start = display_start
        block_right_end = display_start

        if tag == "delete":
            for left_index in range(left_start, left_end):
                display_index = len(left_display)
                left_display.append(left_lines[left_index])
                right_display.append("")
                right_spacers.add(display_index)
                line_styles.append(DiffLineStyle("left", display_index, theme.line_removed))
            block_left_end = len(left_display)
        elif tag == "insert":
            for right_index in range(right_start, right_end):
                display_index = len(left_display)
                left_display.append("")
                right_display.append(right_lines[right_index])
                left_spacers.add(display_index)
                line_styles.append(DiffLineStyle("right", display_index, theme.line_added))
            block_right_end = len(right_display)
        elif tag == "replace":
            left_count = left_end - left_start
            right_count = right_end - right_start
            block_left_end = display_start + left_count
            block_right_end = display_start + right_count
            display_count = max(left_count, right_count)
            for offset in range(display_count):
                display_index = len(left_display)
                has_left = offset < left_count
                has_right = offset < right_count
                left_text = left_lines[left_start + offset] if has_left else ""
                right_text = right_lines[right_start + offset] if has_right else ""
                left_display.append(left_text)
                right_display.append(right_text)
                if not has_left:
                    left_spacers.add(display_index)
                    line_styles.append(DiffLineStyle("right", display_index, theme.line_added))
                elif not has_right:
                    right_spacers.add(display_index)
                    line_styles.append(DiffLineStyle("left", display_index, theme.line_removed))
                else:
                    line_styles.append(DiffLineStyle("left", display_index, theme.line_changed))
                    line_styles.append(DiffLineStyle("right", display_index, theme.line_changed))
                    inline_styles.extend(_inline_diff(left_text, right_text, display_index, display_index))

        diff_blocks.append(DiffBlock(tag, block_left_start, block_left_end, block_right_start, block_right_end))

    return left_display, right_display, left_spacers, right_spacers, line_styles, inline_styles, diff_blocks


def _inline_diff(left: str, right: str, left_line: int, right_line: int) -> list[InlineStyle]:
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    result: list[InlineStyle] = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if left_start != left_end:
            result.append(InlineStyle("left", left_line, left_start, left_end))
        if right_start != right_end:
            result.append(InlineStyle("right", right_line, right_start, right_end))
    return result


def _normalize(line: str, ignore_whitespace: bool, ignore_case: bool) -> str:
    if ignore_whitespace:
        line = "".join(line.split())
    if ignore_case:
        line = line.casefold()
    return line


def _line_selection(edit: QPlainTextEdit, line: int, color: str) -> QTextEdit.ExtraSelection:
    selection = QTextEdit.ExtraSelection()
    selection.cursor = QTextCursor(edit.document().findBlockByNumber(line))
    selection.format.setBackground(QColor(color))
    selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
    return selection


def _range_selection(edit: QPlainTextEdit, line: int, start: int, end: int, color: str) -> QTextEdit.ExtraSelection:
    block = edit.document().findBlockByNumber(line)
    return _absolute_selection(edit, block.position() + start, block.position() + end, color)


def _absolute_selection(edit: QPlainTextEdit, start: int, end: int, color: str) -> QTextEdit.ExtraSelection:
    selection = QTextEdit.ExtraSelection()
    cursor = QTextCursor(edit.document())
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    selection.cursor = cursor
    fmt = QTextCharFormat()
    fmt.setBackground(QColor(color))
    selection.format = fmt
    return selection


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _action_button(
    text: str,
    tooltip: str,
    parent: QWidget | None = None,
    object_name: str = "ActionButton",
) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName(object_name)
    button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedSize(22, 22)
    return button


def _button_columns(width: int) -> list[int]:
    button_width = 20
    total = button_width * 4
    spacing = max(4, (width - total) // 5)
    mid_extra = 4
    x0 = spacing
    x1 = x0 + button_width + spacing
    x2 = x1 + button_width + spacing + mid_extra
    x3 = x2 + button_width + spacing
    return [x0, x1, x2, x3]


def _block_has_side_lines(block: DiffBlock, side: str) -> bool:
    start, end = _block_range(block, side)
    return start < end


def _block_is_one_sided(block: DiffBlock) -> bool:
    return _block_has_side_lines(block, "left") != _block_has_side_lines(block, "right")


def _range_center(value: tuple[int, int] | None) -> int | None:
    if value is None:
        return None
    return round((value[0] + value[1]) / 2)


def _connector_path(
    width: int,
    left_top: int,
    left_bottom: int,
    right_top: int,
    right_bottom: int,
) -> QPainterPath:
    inset = 4
    left_x = inset
    right_x = max(inset + 8, width - inset)
    curve = max(18, width * 0.42)
    path = QPainterPath()
    path.moveTo(QPointF(left_x, left_top))
    path.cubicTo(QPointF(curve, left_top), QPointF(width - curve, right_top), QPointF(right_x, right_top))
    path.lineTo(QPointF(right_x, right_bottom))
    path.cubicTo(QPointF(width - curve, right_bottom), QPointF(curve, left_bottom), QPointF(left_x, left_bottom))
    path.closeSubpath()
    return path


def _block_brush(tag: str, theme: Theme) -> QColor:
    light = theme.name == "Light"
    if tag == "insert":
        color = QColor("#86efac" if light else "#16a34a")
        color.setAlpha(150 if light else 132)
        return color
    if tag == "delete":
        color = QColor("#fca5a5" if light else "#dc2626")
        color.setAlpha(150 if light else 132)
        return color
    color = QColor("#c4b5fd" if light else "#7c3aed")
    color.setAlpha(138 if light else 118)
    return color


def _block_outline(tag: str, theme: Theme) -> QColor:
    light = theme.name == "Light"
    if tag == "insert":
        color = QColor("#22c55e" if light else "#4ade80")
    elif tag == "delete":
        color = QColor("#ef4444" if light else "#f87171")
    else:
        color = QColor("#8b5cf6" if light else "#a78bfa")
    color.setAlpha(185 if light else 160)
    return color


def _gutter_line_color(theme: Theme) -> QColor:
    return QColor("#b0c8de" if theme.name == "Light" else "#162234")


def _gutter_background_color(theme: Theme) -> QColor:
    return QColor("#e0eaf5" if theme.name == "Light" else "#0c1825")


def _minimap_background_color(theme: Theme) -> QColor:
    return QColor("#eef4fa" if theme.name == "Light" else "#080f18")


def _minimap_viewport_color(theme: Theme) -> QColor:
    return QColor("#90aabf" if theme.name == "Light" else "#1e3d5c")


def _minimap_block_color(tag: str, theme: Theme) -> QColor:
    light = theme.name == "Light"
    if tag == "insert":
        color = QColor("#22c55e" if light else "#4ade80")
    elif tag == "delete":
        color = QColor("#ef4444" if light else "#f87171")
    else:
        color = QColor("#eab308" if light else "#facc15")
    color.setAlpha(210 if light else 185)
    return color


def _block_range(block: DiffBlock, side: str) -> tuple[int, int]:
    if side == "left":
        return block.left_start, block.left_end
    return block.right_start, block.right_end


def _block_tooltip(block: DiffBlock, source_side: str, target_side: str) -> str:
    source_start, source_end = _block_range(block, source_side)
    return (
        f"Copy {source_side} block lines {source_start + 1}-{max(source_start + 1, source_end)} "
        f"to {target_side}"
    )


def _delete_tooltip(block: DiffBlock, side: str) -> str:
    start, end = _block_range(block, side)
    return f"Delete {side} block lines {start + 1}-{max(start + 1, end)}"
