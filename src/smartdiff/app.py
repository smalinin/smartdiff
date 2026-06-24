#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .compare import compare_paths
from .diff_window import DiffWindow
from .main_window import MainWindow
from .models import CompareOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SmartDiff")
    parser.add_argument("--d", action="store_true", help="Do not scan subdirectories")
    parser.add_argument("paths", nargs="*", help="Two files or two directories")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = QApplication(sys.argv)
    recurse = not args.d
    paths = [Path(value).expanduser() for value in args.paths]
    windows = []

    if len(paths) == 2 and paths[0].is_file() and paths[1].is_file():
        result = compare_paths(paths[0], paths[1], CompareOptions(recurse))
        record = result.entries[0]
        if record.is_binary or record.is_too_large:
            title = "Binary comparison" if record.is_binary else "Large file comparison"
            QMessageBox.information(
                None,
                title,
                f"{record.relative_path}\n"
                f"State: {record.state.value}\n"
                "File was compared by size, timestamp, and SHA-256.",
            )
            return 0
        window = DiffWindow(paths[0], paths[1])
        windows.append(window)
        window.show()
    elif len(paths) == 2:
        if not paths[0].exists() or not paths[1].exists():
            QMessageBox.warning(None, "Path not found", "Both paths must exist.")
            return 2
        if paths[0].is_dir() and paths[1].is_dir():
            window = MainWindow(
                left_path=paths[0],
                right_path=paths[1],
                recurse_subdirectories=recurse,
                auto_compare=True,
            )
            windows.append(window)
            window.show()
        else:
            result = compare_paths(paths[0], paths[1], CompareOptions(recurse))
            QMessageBox.information(None, "Comparison", f"{len(result.entries)} item(s) compared.")
            return 0
    elif len(paths) == 0:
        window = MainWindow(recurse_subdirectories=recurse)
        windows.append(window)
        window.show()
    else:
        QMessageBox.warning(None, "Arguments", "Pass either zero paths or exactly two paths.")
        return 2

    return app.exec()
