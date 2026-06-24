#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    stylesheet: str
    editor_background: str
    editor_foreground: str
    line_added: str
    line_removed: str
    line_changed: str
    inline_changed: str
    find_all: str
    find_current: str


DARK_THEME = Theme(
    name="Dark",
    stylesheet="""
        QMainWindow { background: #0e1621; }
        QWidget { background: #0e1621; color: #d4e4f7; font-family: 'Segoe UI', Inter, system-ui, sans-serif; font-size: 9pt; }
        QMenuBar { background: #111d2c; color: #c8dff5; border-bottom: 1px solid #1c3347; padding: 1px 4px; spacing: 2px; }
        QMenuBar::item { padding: 4px 10px; border-radius: 4px; }
        QMenuBar::item:selected { background: #1a3550; }
        QMenu { background: #111d2c; color: #c8dff5; border: 1px solid #1c3347; border-radius: 8px; padding: 4px 0; }
        QMenu::item { padding: 5px 20px 5px 12px; border-radius: 4px; margin: 1px 4px; }
        QMenu::item:selected { background: #1a3550; }
        QMenu::item:disabled { color: #2e4d66; }
        QMenu::separator { height: 1px; background: #1c3347; margin: 4px 0; }
        QLineEdit { background: #0a111a; color: #b9d8f5; border: 1px solid #1c3347; border-radius: 6px; padding: 4px 8px; selection-background-color: #1e4f8c; }
        QLineEdit:focus { border-color: #2e6ab5; }
        QTreeWidget { background: #090f18; color: #c0d8f2; border: 1px solid #172537; alternate-background-color: #0b1522; }
        QTreeWidget::item:selected { background: #133050; }
        QTreeWidget::item:hover:!selected { background: #0d1e32; }
        QHeaderView::section { background: #0d1929; color: #6a90bb; border: 0; border-bottom: 1px solid #1c3347; padding: 6px 8px; font-weight: 600; font-size: 8pt; }
        QPushButton { background: #122337; color: #c0d8f2; border: 1px solid #1e3d5c; border-radius: 6px; padding: 5px 12px; font-weight: 500; }
        QPushButton:hover { background: #183049; border-color: #2e6090; }
        QPushButton:pressed { background: #0d1929; }
        QCheckBox { color: #b9d8f5; spacing: 6px; }
        QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #1e3d5c; border-radius: 3px; background: #122337; }
        QCheckBox::indicator:checked { background: #1e6fb5; border-color: #2e8be0; }
        QScrollBar:vertical { background: transparent; width: 8px; border-radius: 4px; }
        QScrollBar::handle:vertical { background: #1e3d5c; border-radius: 4px; min-height: 24px; margin: 1px; }
        QScrollBar::handle:vertical:hover { background: #2e6090; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        QScrollBar:horizontal { background: transparent; height: 8px; border-radius: 4px; }
        QScrollBar::handle:horizontal { background: #1e3d5c; border-radius: 4px; min-width: 24px; margin: 1px; }
        QScrollBar::handle:horizontal:hover { background: #2e6090; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        QPushButton#CopyActionButton { background: rgba(9, 15, 24, 210); border: 1px solid #1e4d8c; border-radius: 5px; min-width: 22px; min-height: 20px; font-size: 22px; font-weight: 900; color: #7cff8d; padding: -6px 0 1px 0; }
        QPushButton#CopyActionButton:hover { background: rgba(30, 77, 140, 55); border-color: #55b3ff; }
        QPushButton#DeleteActionButton { background: rgba(9, 15, 24, 210); border: 1px solid #8b1e1e; border-radius: 5px; min-width: 22px; min-height: 20px; font-size: 16px; font-weight: 700; color: #ff7070; padding: -2px 0 3px 0; }
        QPushButton#DeleteActionButton:hover { background: rgba(139, 30, 30, 45); border-color: #ff7070; }
        QPushButton#NavButton { background: #122337; color: #55b3ff; border: 1px solid #1e3d5c; border-radius: 5px; min-width: 22px; max-width: 22px; min-height: 22px; padding: 0 2px; font-size: 11px; font-weight: 600; }
        QPushButton#NavButton:hover { background: #183049; border-color: #2e6090; }
        QWidget#ActionPanel { background: #0c1825; border-left: 1px solid #162234; border-right: 1px solid #162234; }
        QWidget#DiffMinimap { background: #080f18; border-left: 1px solid #162234; }
        QWidget#TitleBar { background: #111d2c; }
        QWidget#TitleSeparator { background-color: #1a3050; }
        QLabel#PathLabel { color: #4e80a8; font-family: 'Cascadia Code', Consolas, monospace; font-size: 8.5pt; }
        QLabel#ActionTitle { color: #3a6080; font-size: 8pt; font-weight: 700; }
        QSplitter::handle { background: #162234; }
        QTreeWidget::item { padding: 3px 6px; }
        QTreeWidget::branch { background: #090f18; }
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings { border-image: none; image: none; }
        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings { border-image: none; image: none; }
        QWidget#ToolBar { background: #0d1c2e; border-bottom: 1px solid #1c3347; }
        QWidget#StatsBar { background: #090f18; border-bottom: 1px solid #162234; }
        QLabel#PathDirLabel { color: #4e80a8; font-weight: 600; }
        QLabel#StatsLabel { color: #6a90bb; font-size: 8.5pt; }
        QPushButton#CompareButton { background: #1a4d8c; color: #c8e4ff; border-color: #2e6ab5; font-weight: 600; }
        QPushButton#CompareButton:hover { background: #2060b0; border-color: #4090e0; }
        QPushButton#CompareButton:pressed { background: #153d72; }
        QPushButton#SyncButton { background: #1e4a30; color: #a0e8c0; border-color: #2a7048; font-weight: 600; }
        QPushButton#SyncButton:hover { background: #265c3c; border-color: #3a9060; }
        QPushButton#SyncButton:pressed { background: #163824; }
        QPushButton#SyncButton:disabled { background: #0f1e14; color: #3a5040; border-color: #1a3020; }
        QWidget#PreviewHeader { background: #0d1c2e; border-bottom: 1px solid #1c3347; }
        QLabel#PreviewFileLabel { color: #c8e4ff; font-weight: 700; font-size: 9.5pt; }
        QLabel#PreviewStateLabel { color: #6a90bb; font-size: 8.5pt; }
        QLabel#PreviewMetaLabel { color: #4a6e8a; font-size: 8pt; font-family: 'Cascadia Code', Consolas, monospace; }
        QLabel#PreviewCounterLabel { color: #4a6e8a; font-size: 8.5pt; min-width: 40px; }
    """,
    editor_background="#090f18",
    editor_foreground="#c8dff5",
    line_added="#1e5c38",
    line_removed="#7a2848",
    line_changed="#70641a",
    inline_changed="#2040a0",
    find_all="#4a2d80",
    find_current="#7a4e00",
)


LIGHT_THEME = Theme(
    name="Light",
    stylesheet="""
        QMainWindow { background: #f0f4f8; }
        QWidget { background: #f0f4f8; color: #1a2d42; font-family: 'Segoe UI', Inter, system-ui, sans-serif; font-size: 9pt; }
        QMenuBar { background: #e2ecf5; color: #1a2d42; border-bottom: 1px solid #c0d4e8; padding: 1px 4px; spacing: 2px; }
        QMenuBar::item { padding: 4px 10px; border-radius: 4px; }
        QMenuBar::item:selected { background: #d0e4f5; }
        QMenu { background: #f5f8fb; color: #1a2d42; border: 1px solid #c0d4e8; border-radius: 8px; padding: 4px 0; }
        QMenu::item { padding: 5px 20px 5px 12px; border-radius: 4px; margin: 1px 4px; }
        QMenu::item:selected { background: #d8ecfc; }
        QMenu::item:disabled { color: #a0b8cc; }
        QMenu::separator { height: 1px; background: #c0d4e8; margin: 4px 0; }
        QLineEdit { background: #ffffff; color: #1a2d42; border: 1px solid #c0d4e8; border-radius: 6px; padding: 4px 8px; selection-background-color: #a8d4f8; }
        QLineEdit:focus { border-color: #3a82d6; }
        QTreeWidget { background: #ffffff; color: #1a2d42; border: 1px solid #d0dce8; alternate-background-color: #f7fafd; }
        QTreeWidget::item:selected { background: #cce4fb; }
        QTreeWidget::item:hover:!selected { background: #eef5fc; }
        QHeaderView::section { background: #e8f0f8; color: #4a6a85; border: 0; border-bottom: 1px solid #c0d4e8; padding: 6px 8px; font-weight: 600; font-size: 8pt; }
        QPushButton { background: #ffffff; color: #1a2d42; border: 1px solid #c0d4e8; border-radius: 6px; padding: 5px 12px; font-weight: 500; }
        QPushButton:hover { background: #e4f0fd; border-color: #7ab0d8; }
        QPushButton:pressed { background: #d0e8f8; }
        QCheckBox { color: #1a2d42; spacing: 6px; }
        QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #b0c8d8; border-radius: 3px; background: #ffffff; }
        QCheckBox::indicator:checked { background: #3a82d6; border-color: #3a82d6; }
        QScrollBar:vertical { background: transparent; width: 8px; border-radius: 4px; }
        QScrollBar::handle:vertical { background: #b8ceda; border-radius: 4px; min-height: 24px; margin: 1px; }
        QScrollBar::handle:vertical:hover { background: #8aaabf; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        QScrollBar:horizontal { background: transparent; height: 8px; border-radius: 4px; }
        QScrollBar::handle:horizontal { background: #b8ceda; border-radius: 4px; min-width: 24px; margin: 1px; }
        QScrollBar::handle:horizontal:hover { background: #8aaabf; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
        QPushButton#CopyActionButton { background: rgba(255, 255, 255, 220); border: 1px solid #3a82d6; border-radius: 5px; min-width: 22px; min-height: 20px; font-size: 22px; font-weight: 900; color: #128a28; padding: -6px 0 1px 0; }
        QPushButton#CopyActionButton:hover { background: rgba(58, 130, 214, 25); border-color: #1a6ab5; }
        QPushButton#DeleteActionButton { background: rgba(255, 255, 255, 220); border: 1px solid #e05050; border-radius: 5px; min-width: 22px; min-height: 20px; font-size: 16px; font-weight: 700; color: #c03030; padding: -2px 0 3px 0; }
        QPushButton#DeleteActionButton:hover { background: rgba(224, 80, 80, 20); border-color: #c03030; }
        QPushButton#NavButton { background: #ffffff; color: #1a6ab5; border: 1px solid #c0d4e8; border-radius: 5px; min-width: 22px; max-width: 22px; min-height: 22px; padding: 0 2px; font-size: 11px; font-weight: 600; }
        QPushButton#NavButton:hover { background: #e4f0fd; border-color: #7ab0d8; }
        QWidget#ActionPanel { background: #e0eaf5; border-left: 1px solid #c0d4e8; border-right: 1px solid #c0d4e8; }
        QWidget#DiffMinimap { background: #eef4fa; border-left: 1px solid #c0d4e8; }
        QWidget#TitleBar { background: #e2ecf5; }
        QWidget#TitleSeparator { background-color: #b8d0e8; }
        QLabel#PathLabel { color: #5080a8; font-family: 'Cascadia Code', Consolas, monospace; font-size: 8.5pt; }
        QLabel#ActionTitle { color: #7090aa; font-size: 8pt; font-weight: 700; }
        QSplitter::handle { background: #c0d4e8; }
        QTreeWidget::item { padding: 3px 6px; }
        QTreeWidget::branch { background: #ffffff; }
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings { border-image: none; image: none; }
        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings { border-image: none; image: none; }
        QWidget#ToolBar { background: #e2ecf5; border-bottom: 1px solid #c0d4e8; }
        QWidget#StatsBar { background: #f5f8fb; border-bottom: 1px solid #d4e4f0; }
        QLabel#PathDirLabel { color: #3a6090; font-weight: 600; }
        QLabel#StatsLabel { color: #5a7a95; font-size: 8.5pt; }
        QPushButton#CompareButton { background: #3a82d6; color: #ffffff; border-color: #2a72c6; font-weight: 600; }
        QPushButton#CompareButton:hover { background: #2a72c6; border-color: #1a62b6; }
        QPushButton#CompareButton:pressed { background: #1a62b6; }
        QPushButton#SyncButton { background: #d4f0e0; color: #0d6030; border-color: #60b880; font-weight: 600; }
        QPushButton#SyncButton:hover { background: #bce8ce; border-color: #40a060; }
        QPushButton#SyncButton:pressed { background: #a8dcc0; }
        QPushButton#SyncButton:disabled { background: #eef5f0; color: #90b8a0; border-color: #c0d8c8; }
        QWidget#PreviewHeader { background: #e2ecf5; border-bottom: 1px solid #c0d4e8; }
        QLabel#PreviewFileLabel { color: #1a2d42; font-weight: 700; font-size: 9.5pt; }
        QLabel#PreviewStateLabel { color: #4a6a85; font-size: 8.5pt; }
        QLabel#PreviewMetaLabel { color: #7090aa; font-size: 8pt; font-family: 'Cascadia Code', Consolas, monospace; }
        QLabel#PreviewCounterLabel { color: #7090aa; font-size: 8.5pt; min-width: 40px; }
    """,
    editor_background="#ffffff",
    editor_foreground="#1a2d42",
    line_added="#d4f0dc",
    line_removed="#fcd8d8",
    line_changed="#fef3c0",
    inline_changed="#b8d4fc",
    find_all="#d8c8fc",
    find_current="#fcd8a0",
)
