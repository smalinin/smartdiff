#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_TEXT_DIFF_BYTES = 10 * 1024 * 1024

DEFAULT_BINARY_EXTENSIONS = {
    ".7z",
    ".a",
    ".apk",
    ".app",
    ".arj",
    ".avi",
    ".bak",
    ".bin",
    ".bmp",
    ".bz2",
    ".cab",
    ".class",
    ".cur",
    ".dat",
    ".db",
    ".dll",
    ".dmg",
    ".doc",
    ".docx",
    ".dylib",
    ".eot",
    ".exe",
    ".flac",
    ".gif",
    ".gz",
    ".heic",
    ".ico",
    ".iso",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lib",
    ".mdb",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".msi",
    ".o",
    ".obj",
    ".odg",
    ".odp",
    ".ods",
    ".odt",
    ".ogg",
    ".otf",
    ".p7z",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".pyc",
    ".rar",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".swf",
    ".tar",
    ".tgz",
    ".tif",
    ".tiff",
    ".ttf",
    ".wasm",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsm",
    ".xlsx",
    ".xz",
    ".zip",
}

DEFAULT_IGNORED_SUBDIRECTORY_NAMES = {
    ".cache",
    ".env",
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "env",
    "node_modules",
    "venv",
}

SETTINGS_PATH = Path.home() / ".smartdiff" / "settings.json"


@dataclass(frozen=True)
class AppSettings:
    binary_extensions: set[str]
    ignored_subdirectory_names: set[str]
    max_text_diff_bytes: int


_current_settings: AppSettings | None = None


def default_settings() -> AppSettings:
    return AppSettings(
        binary_extensions=set(DEFAULT_BINARY_EXTENSIONS),
        ignored_subdirectory_names=set(DEFAULT_IGNORED_SUBDIRECTORY_NAMES),
        max_text_diff_bytes=DEFAULT_MAX_TEXT_DIFF_BYTES,
    )


def get_settings() -> AppSettings:
    global _current_settings
    if _current_settings is None:
        _current_settings = load_settings()
    return _current_settings


def save_settings(settings: AppSettings) -> None:
    global _current_settings
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(_to_json(settings), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _current_settings = settings


def load_settings() -> AppSettings:
    defaults = default_settings()
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(raw, dict):
        return defaults

    return AppSettings(
        binary_extensions=_normalize_extensions(
            raw.get("binary_extensions"),
            defaults.binary_extensions,
        ),
        ignored_subdirectory_names=_normalize_names(
            raw.get("ignored_subdirectory_names"),
            defaults.ignored_subdirectory_names,
        ),
        max_text_diff_bytes=_normalize_max_size(
            raw.get("max_text_diff_bytes"),
            defaults.max_text_diff_bytes,
        ),
    )


def _to_json(settings: AppSettings) -> dict[str, Any]:
    return {
        "binary_extensions": sorted(settings.binary_extensions),
        "ignored_subdirectory_names": sorted(settings.ignored_subdirectory_names),
        "max_text_diff_bytes": settings.max_text_diff_bytes,
    }


def _normalize_extensions(value: Any, fallback: set[str]) -> set[str]:
    if not isinstance(value, list):
        return set(fallback)
    result = {
        _normalize_extension(item)
        for item in value
        if isinstance(item, str) and item.strip()
    }
    return result


def _normalize_extension(value: str) -> str:
    text = value.strip().casefold()
    if not text.startswith("."):
        text = f".{text}"
    return text


def _normalize_names(value: Any, fallback: set[str]) -> set[str]:
    if not isinstance(value, list):
        return set(fallback)
    result = {
        item.strip().casefold()
        for item in value
        if isinstance(item, str) and item.strip()
    }
    return result


def _normalize_max_size(value: Any, fallback: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    return fallback
