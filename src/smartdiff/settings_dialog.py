#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .app_settings import AppSettings, SETTINGS_PATH, get_settings


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(620, 560)
        settings = get_settings()

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
