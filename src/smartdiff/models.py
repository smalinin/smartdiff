#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CompareState(str, Enum):
    EQUAL = "Equal"
    DIFFERENT = "Different"
    LEFT_YOUNGER = "Left younger"
    RIGHT_YOUNGER = "Right younger"
    LEFT_ONLY = "Left only"
    RIGHT_ONLY = "Right only"
    TYPE_MISMATCH = "Type mismatch"


@dataclass(frozen=True)
class CompareOptions:
    recurse_subdirectories: bool = True


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    kind: str
    state: CompareState
    left_path: Path | None
    right_path: Path | None
    left_size: int | None = None
    right_size: int | None = None
    left_mtime: float | None = None
    right_mtime: float | None = None
    left_hash: str | None = None
    right_hash: str | None = None
    is_binary: bool = False
    is_too_large: bool = False

    @property
    def suggested_action(self) -> str:
        if self.state == CompareState.EQUAL:
            return "Skip"
        if self.state in (CompareState.DIFFERENT, CompareState.LEFT_YOUNGER, CompareState.RIGHT_YOUNGER):
            if self.is_binary:
                return "Review binary metadata"
            if self.is_too_large:
                return "Review large file metadata"
            return "Review contents"
        if self.state == CompareState.LEFT_ONLY:
            return "Copy left to right"
        if self.state == CompareState.RIGHT_ONLY:
            return "Copy right to left"
        return "Review type mismatch"


@dataclass(frozen=True)
class CompareResult:
    left_root: Path
    right_root: Path
    entries: list[FileRecord]

    @property
    def is_directory_comparison(self) -> bool:
        return self.left_root.is_dir() and self.right_root.is_dir()

    @property
    def equal_count(self) -> int:
        return sum(1 for item in self.entries if item.state == CompareState.EQUAL)

    @property
    def action_count(self) -> int:
        return len(self.entries) - self.equal_count
