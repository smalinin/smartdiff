#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import sys
from importlib import metadata

APP_NAME = "SmartDiff"
FALLBACK_VERSION = "0.2.0"


def app_version() -> str:
    try:
        return metadata.version("smartdiff")
    except metadata.PackageNotFoundError:
        return FALLBACK_VERSION


def about_text() -> str:
    return f"{APP_NAME} {app_version()}\nPython {sys.version_info.major}.{sys.version_info.minor} + PySide6 diff viewer."
