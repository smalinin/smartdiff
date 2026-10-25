from __future__ import annotations

import json

from PySide6.QtGui import QFont

from .app_settings import get_settings


DEFAULT_EDITOR_FONT_FAMILIES = (
    "Consolas", "Cascadia Mono", "Menlo", "SF Mono",
    "Liberation Mono", "DejaVu Sans Mono", "monospace",
)


def editor_font() -> QFont:
    settings = get_settings()
    font = QFont()
    font.setFamilies(
        [settings.editor_font_family]
        if settings.editor_font_family else list(DEFAULT_EDITOR_FONT_FAMILIES)
    )
    font.setPointSizeF(settings.editor_font_size)
    return font


def editor_font_stylesheet(font: QFont | None = None) -> str:
    if font is None:
        font = editor_font()
    families = ", ".join(json.dumps(family, ensure_ascii=False) for family in font.families())
    return f"font-family: {families}; font-size: {font.pointSizeF():g}pt; "
