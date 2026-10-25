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
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
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
from .editor_font import editor_font, editor_font_stylesheet


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreferencesDialog")
        self.setWindowTitle("Preferences")
        self.resize(720, 740)
        self.setMinimumWidth(620)
        settings = get_settings()

        self.editor_font_combo = QFontComboBox()
        self.editor_font_combo.setCurrentFont(editor_font())
        self.editor_font_combo.setCurrentText(QFontInfo(editor_font()).family())
        self.editor_font_combo.setMinimumHeight(32)
        self.editor_font_combo.setAccessibleName("Editor font")

        self.editor_font_size = QDoubleSpinBox()
        self.editor_font_size.setRange(MIN_EDITOR_FONT_SIZE, MAX_EDITOR_FONT_SIZE)
        self.editor_font_size.setDecimals(1)
        self.editor_font_size.setSingleStep(0.5)
        self.editor_font_size.setSuffix(" pt")
        self.editor_font_size.setValue(settings.editor_font_size)
        self.editor_font_size.setFixedWidth(112)
        self.editor_font_size.setMinimumHeight(32)
        self.editor_font_size.setAccessibleName("Font size")

        self.font_preview = QPlainTextEdit()
        self.font_preview.setObjectName("FontPreview")
        self.font_preview.setAccessibleName("Font preview")
        self.font_preview.setReadOnly(True)
        self.font_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.font_preview.setFixedHeight(104)
        self.font_preview.setPlainText(
            "The quick brown fox jumps over the lazy dog.\n"
            '\u0421\u044a\u0435\u0448\u044c \u0435\u0449\u0451 \u044d\u0442\u0438\u0445 \u043c\u044f\u0433\u043a\u0438\u0445 \u0444\u0440\u0430\u043d\u0446\u0443\u0437\u0441\u043a\u0438\u0445 \u0431\u0443\u043b\u043e\u043a.\n'
            "AaBbCc 0123456789  != ==  () [] {}"
        )
        self.font_preview_caption = _label("", "PreferencesHint")

        self.binary_extensions_edit = QPlainTextEdit()
        self.binary_extensions_edit.setPlainText(_format_list(settings.binary_extensions))
        self.binary_extensions_edit.setMinimumHeight(112)
        self.binary_extensions_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.binary_extensions_edit.setAccessibleName("Binary extensions")

        self.ignored_directories_edit = QPlainTextEdit()
        self.ignored_directories_edit.setPlainText(_format_list(settings.ignored_subdirectory_names))
        self.ignored_directories_edit.setMinimumHeight(112)
        self.ignored_directories_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.ignored_directories_edit.setAccessibleName("Ignored directories")

        self.max_file_size_mb = QSpinBox()
        self.max_file_size_mb.setRange(1, 4096)
        self.max_file_size_mb.setSuffix(" MB")
        self.max_file_size_mb.setValue(max(1, round(settings.max_text_diff_bytes / 1024 / 1024)))
        self.max_file_size_mb.setFixedWidth(112)
        self.max_file_size_mb.setMinimumHeight(32)
        self.max_file_size_mb.setAccessibleName("Max text diff size")

        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(_label("Customize the editor and directory comparisons.", "PreferencesHint"))

        appearance, appearance_layout = _card()
        appearance_layout.addWidget(_label("Editor appearance", "PreferencesSectionTitle"))
        font_controls = QHBoxLayout()
        font_controls.setSpacing(12)
        font_field = QVBoxLayout()
        font_field.setSpacing(5)
        font_label = QLabel("Font family")
        font_label.setBuddy(self.editor_font_combo)
        font_field.addWidget(font_label)
        font_field.addWidget(self.editor_font_combo)
        size_field = QVBoxLayout()
        size_field.setSpacing(5)
        size_label = QLabel("Size")
        size_label.setBuddy(self.editor_font_size)
        size_field.addWidget(size_label)
        size_field.addWidget(self.editor_font_size)
        font_controls.addLayout(font_field, 1)
        font_controls.addLayout(size_field)
        appearance_layout.addLayout(font_controls)
        preview_header = QHBoxLayout()
        preview_header.addWidget(_label("Preview", "PreferencesHint"))
        preview_header.addStretch()
        preview_header.addWidget(self.font_preview_caption)
        appearance_layout.addLayout(preview_header)
        appearance_layout.addWidget(self.font_preview)

        binary_card, binary_layout = _card()
        binary_layout.addWidget(_label("Binary extensions", "PreferencesSectionTitle"))
        binary_layout.addWidget(_label("One extension per line, e.g. .png or .zip.", "PreferencesHint"))
        binary_layout.addWidget(self.binary_extensions_edit, 1)
        ignored_card, ignored_layout = _card()
        ignored_layout.addWidget(_label("Ignored directories", "PreferencesSectionTitle"))
        ignored_layout.addWidget(_label("Folder names to skip in recursive scans.", "PreferencesHint"))
        ignored_layout.addWidget(self.ignored_directories_edit, 1)
        lists = QHBoxLayout()
        lists.setSpacing(12)
        lists.addWidget(binary_card, 1)
        lists.addWidget(ignored_card, 1)

        limits, limits_layout = _card()
        limit_row = QHBoxLayout()
        limit_description = QVBoxLayout()
        limit_description.setSpacing(4)
        limit_description.addWidget(_label("Text diff size limit", "PreferencesSectionTitle"))
        limit_description.addWidget(_label("Larger files are compared without a text diff.", "PreferencesHint"))
        limit_row.addLayout(limit_description, 1)
        limit_row.addWidget(self.max_file_size_mb)
        limits_layout.addLayout(limit_row)

        path_label = _label(str(SETTINGS_PATH), "PreferencesHint")
        path_label.setToolTip(f"Settings file: {SETTINGS_PATH}")
        path_label.setWordWrap(True)
        path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("PreferencesSaveButton")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer = QHBoxLayout()
        footer.setSpacing(16)
        footer.addWidget(path_label, 1)
        footer.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(appearance)
        layout.addLayout(lists, 1)
        layout.addWidget(limits)
        layout.addLayout(footer)

        self.editor_font_combo.currentFontChanged.connect(self._update_font_preview)
        self.editor_font_size.valueChanged.connect(self._update_font_preview)
        self._update_font_preview()

    def _update_font_preview(self) -> None:
        font = self.editor_font_combo.currentFont()
        font.setPointSizeF(self.editor_font_size.value())
        self.font_preview.setStyleSheet(
            "QPlainTextEdit#FontPreview { " + editor_font_stylesheet(font) + "}"
        )
        self.font_preview_caption.setText(
            f"{font.family()} \u00b7 {font.pointSizeF():g} pt"
        )
        self.font_preview.horizontalScrollBar().setValue(0)
        self.font_preview.verticalScrollBar().setValue(0)

    def settings(self) -> AppSettings:
        return AppSettings(
            binary_extensions=_parse_extensions(self.binary_extensions_edit.toPlainText()),
            ignored_subdirectory_names=_parse_names(self.ignored_directories_edit.toPlainText()),
            max_text_diff_bytes=self.max_file_size_mb.value() * 1024 * 1024,
            editor_font_family=self.editor_font_combo.currentFont().family(),
            editor_font_size=self.editor_font_size.value(),
        )


def _label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("PreferencesCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)
    return frame, layout


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
