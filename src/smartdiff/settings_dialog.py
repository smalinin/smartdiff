#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .app_settings import (
    AppSettings,
    MAX_EDITOR_FONT_SIZE,
    MIN_EDITOR_FONT_SIZE,
    SETTINGS_PATH,
    get_settings,
)
from .editor_font import editor_font


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(620, 640)
        settings = get_settings()

        self.editor_font_combo = QFontComboBox()
        self.editor_font_combo.setCurrentFont(editor_font())
        self.editor_font_combo.setCurrentText(QFontInfo(editor_font()).family())

        self.editor_font_size = QDoubleSpinBox()
        self.editor_font_size.setRange(MIN_EDITOR_FONT_SIZE, MAX_EDITOR_FONT_SIZE)
        self.editor_font_size.setDecimals(1)
        self.editor_font_size.setSingleStep(0.5)
        self.editor_font_size.setSuffix(" pt")
        self.editor_font_size.setValue(settings.editor_font_size)

        self.binary_extensions_edit = QPlainTextEdit()
        self.binary_extensions_edit.setPlainText(_format_list(settings.binary_extensions))
        self.binary_extensions_edit.setMinimumHeight(190)

        self.ignored_directories_edit = QPlainTextEdit()
        self.ignored_directories_edit.setPlainText(_format_list(settings.ignored_subdirectory_names))
        self.ignored_directories_edit.setMinimumHeight(120)

        self.max_file_size_mb = QSpinBox()
        self.max_file_size_mb.setRange(1, 4096)
        self.max_file_size_mb.setSuffix(" MB")
        self.max_file_size_mb.setValue(max(1, round(settings.max_text_diff_bytes / 1024 / 1024)))

        path_label = QLabel(str(SETTINGS_PATH))
        path_label.setTextInteractionFlags(
            path_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Editor font", self.editor_font_combo)
        form.addRow("Font size", self.editor_font_size)
        form.addRow("Binary extensions", self.binary_extensions_edit)
        form.addRow("Ignored directories", self.ignored_directories_edit)
        form.addRow("Max text diff size", self.max_file_size_mb)
        form.addRow("Settings file", path_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addLayout(form, 1)
        layout.addWidget(buttons)

    def settings(self) -> AppSettings:
        return AppSettings(
            binary_extensions=_parse_extensions(self.binary_extensions_edit.toPlainText()),
            ignored_subdirectory_names=_parse_names(self.ignored_directories_edit.toPlainText()),
            max_text_diff_bytes=self.max_file_size_mb.value() * 1024 * 1024,
            editor_font_family=self.editor_font_combo.currentFont().family(),
            editor_font_size=self.editor_font_size.value(),
        )


def _format_list(values: set[str]) -> str:
    return "\n".join(sorted(values))


def _parse_extensions(text: str) -> set[str]:
    result: set[str] = set()
    for line in text.splitlines():
        item = line.strip().casefold()
        if not item:
            continue
        if not item.startswith("."):
            item = f".{item}"
        result.add(item)
    return result


def _parse_names(text: str) -> set[str]:
    return {
        line.strip().casefold()
        for line in text.splitlines()
        if line.strip()
    }
