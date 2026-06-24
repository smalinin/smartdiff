#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

from .app_settings import get_settings


def ignored_subdirectory_names() -> set[str]:
    return set(get_settings().ignored_subdirectory_names)


def should_skip_subdirectory(name: str) -> bool:
    return name.casefold() in get_settings().ignored_subdirectory_names
