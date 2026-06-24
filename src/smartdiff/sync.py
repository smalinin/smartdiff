#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .models import CompareResult, CompareState


class SyncDirection(Enum):
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"


@dataclass(frozen=True)
class SyncResult:
    new_files_copied: int
    files_overwritten: int
    directories_created: int
    skipped_type_mismatch: int


def sync_directories(result: CompareResult, direction: SyncDirection) -> SyncResult:
    """Copy files from source side to target side based on comparison result.

    LEFT_TO_RIGHT: LeftOnly / LeftYounger / Different -> copy to right
    RIGHT_TO_LEFT: RightOnly / RightYounger / Different -> copy to left

    TypeMismatch entries and any entry whose ancestor is TypeMismatch are skipped.
    No files are ever deleted.
    """
    if not result.is_directory_comparison:
        raise ValueError("Synchronization is only available for directory comparisons.")

    type_mismatch_paths = {
        entry.relative_path
        for entry in result.entries
        if entry.state == CompareState.TYPE_MISMATCH
    }

    if direction == SyncDirection.LEFT_TO_RIGHT:
        source_root = result.left_root
        target_root = result.right_root
        sync_states = {CompareState.LEFT_ONLY, CompareState.LEFT_YOUNGER, CompareState.DIFFERENT}
    else:
        source_root = result.right_root
        target_root = result.left_root
        sync_states = {CompareState.RIGHT_ONLY, CompareState.RIGHT_YOUNGER, CompareState.DIFFERENT}

    new_files = 0
    overwritten = 0
    dirs_created = 0
    skipped = 0

    for entry in result.entries:
        if entry.state == CompareState.TYPE_MISMATCH:
            skipped += 1
            continue

        if entry.state not in sync_states:
            continue

        if _has_blocked_ancestor(entry.relative_path, type_mismatch_paths):
            skipped += 1
            continue

        rel = Path(entry.relative_path)
        source = source_root / rel
        target = target_root / rel

        if entry.kind == "Directory":
            if not source.is_dir():
                skipped += 1
                continue
            if target.exists() and not target.is_dir():
                skipped += 1
                continue
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                dirs_created += 1
            continue

        if not source.is_file() or target.is_dir():
            skipped += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        already_exists = target.exists()
        shutil.copy2(str(source), str(target))

        if already_exists:
            overwritten += 1
        else:
            new_files += 1

    return SyncResult(new_files, overwritten, dirs_created, skipped)


def _has_blocked_ancestor(relative_path: str, blocked: set[str]) -> bool:
    parts = relative_path.replace("\\", "/").split("/")
    for i in range(1, len(parts)):
        ancestor = "/".join(parts[:i])
        if ancestor in blocked:
            return True
    return False
