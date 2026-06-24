#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import hashlib
from pathlib import Path

from .app_settings import get_settings


def known_binary_extensions() -> set[str]:
    return set(get_settings().binary_extensions)


def max_text_diff_bytes() -> int:
    return get_settings().max_text_diff_bytes


def is_known_binary_file(path: Path) -> bool:
    return path.suffix.casefold() in get_settings().binary_extensions


def is_too_large_for_text_diff(size: int) -> bool:
    return size > get_settings().max_text_diff_bytes


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
