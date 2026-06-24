#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

import filecmp
import os
from pathlib import Path

from .binary_files import file_sha256, is_known_binary_file, is_too_large_for_text_diff
from .models import CompareOptions, CompareResult, CompareState, FileRecord
from .scan_rules import should_skip_subdirectory


def compare_paths(left: Path, right: Path, options: CompareOptions) -> CompareResult:
    left = left.resolve()
    right = right.resolve()

    if left.is_file() and right.is_file():
        return CompareResult(left, right, [_compare_file_pair(left.name, left, right)])

    if left.is_dir() and right.is_dir():
        return compare_directories(left, right, options)

    return CompareResult(
        left,
        right,
        [
            FileRecord(
                relative_path=left.name or right.name,
                kind="Mixed",
                state=CompareState.TYPE_MISMATCH,
                left_path=left if left.exists() else None,
                right_path=right if right.exists() else None,
            )
        ],
    )


def compare_directories(left_root: Path, right_root: Path, options: CompareOptions) -> CompareResult:
    left_items = _scan_entries(left_root, options.recurse_subdirectories)
    right_items = _scan_entries(right_root, options.recurse_subdirectories)
    all_paths = sorted(set(left_items) | set(right_items), key=str.casefold)
    entries: list[FileRecord] = []

    for relative_path in all_paths:
        left_path = left_items.get(relative_path)
        right_path = right_items.get(relative_path)
        if left_path is None and right_path is not None:
            entries.append(_single_side_record(relative_path, None, right_path, CompareState.RIGHT_ONLY))
        elif right_path is None and left_path is not None:
            entries.append(_single_side_record(relative_path, left_path, None, CompareState.LEFT_ONLY))
        elif left_path is not None and right_path is not None:
            if left_path.is_dir() != right_path.is_dir():
                entries.append(_type_mismatch_record(relative_path, left_path, right_path))
            elif left_path.is_dir():
                entries.append(_directory_record(relative_path, left_path, right_path, CompareState.EQUAL))
            else:
                entries.append(_compare_file_pair(relative_path, left_path, right_path))

    return CompareResult(left_root, right_root, entries)


def _scan_entries(root: Path, recurse: bool) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not recurse:
        for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if path.is_file() or path.is_dir():
                result[path.relative_to(root).as_posix()] = path
        return result

    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = [
            name for name in directory_names
            if not should_skip_subdirectory(name)
        ]
        directory_names.sort(key=str.casefold)
        current_path = Path(current_root)
        for directory_name in directory_names:
            path = current_path / directory_name
            result[path.relative_to(root).as_posix()] = path
        for file_name in sorted(file_names, key=str.casefold):
            path = current_path / file_name
            if path.is_file():
                result[path.relative_to(root).as_posix()] = path
    return result


def _compare_file_pair(relative_path: str, left: Path, right: Path) -> FileRecord:
    left_stat = left.stat()
    right_stat = right.stat()
    is_binary = is_known_binary_file(left) or is_known_binary_file(right)
    is_too_large = (
        not is_binary
        and (
            is_too_large_for_text_diff(left_stat.st_size)
            or is_too_large_for_text_diff(right_stat.st_size)
        )
    )
    metadata_only = is_binary or is_too_large
    left_hash = file_sha256(left) if metadata_only else None
    right_hash = file_sha256(right) if metadata_only else None
    same_size = left_stat.st_size == right_stat.st_size
    same_hash = left_hash == right_hash
    delta = left_stat.st_mtime - right_stat.st_mtime

    if metadata_only and same_size and same_hash and abs(delta) < 2:
        state = CompareState.EQUAL
    elif not metadata_only and same_size and filecmp.cmp(left, right, shallow=False):
        state = CompareState.EQUAL
    else:
        if abs(delta) < 2:
            state = CompareState.DIFFERENT
        elif delta > 0:
            state = CompareState.LEFT_YOUNGER
        else:
            state = CompareState.RIGHT_YOUNGER

    return FileRecord(
        relative_path=relative_path,
        kind=_record_kind(is_binary, is_too_large),
        state=state,
        left_path=left,
        right_path=right,
        left_size=left_stat.st_size,
        right_size=right_stat.st_size,
        left_mtime=left_stat.st_mtime,
        right_mtime=right_stat.st_mtime,
        left_hash=left_hash,
        right_hash=right_hash,
        is_binary=is_binary,
        is_too_large=is_too_large,
    )


def _single_side_record(
    relative_path: str,
    left: Path | None,
    right: Path | None,
    state: CompareState,
) -> FileRecord:
    path = left or right
    if path and path.is_dir():
        return _directory_record(relative_path, left, right, state)
    stat = path.stat() if path else None
    is_binary = is_known_binary_file(path) if path else False
    is_too_large = bool(path and stat and not is_binary and is_too_large_for_text_diff(stat.st_size))
    metadata_only = is_binary or is_too_large
    digest = file_sha256(path) if path and metadata_only else None
    return FileRecord(
        relative_path=relative_path,
        kind=_record_kind(is_binary, is_too_large),
        state=state,
        left_path=left,
        right_path=right,
        left_size=stat.st_size if left and stat else None,
        right_size=stat.st_size if right and stat else None,
        left_mtime=stat.st_mtime if left and stat else None,
        right_mtime=stat.st_mtime if right and stat else None,
        left_hash=digest if left else None,
        right_hash=digest if right else None,
        is_binary=is_binary,
        is_too_large=is_too_large,
    )


def _directory_record(
    relative_path: str,
    left: Path | None,
    right: Path | None,
    state: CompareState,
) -> FileRecord:
    left_stat = left.stat() if left else None
    right_stat = right.stat() if right else None
    return FileRecord(
        relative_path=relative_path,
        kind="Directory",
        state=state,
        left_path=left,
        right_path=right,
        left_mtime=left_stat.st_mtime if left_stat else None,
        right_mtime=right_stat.st_mtime if right_stat else None,
    )


def _type_mismatch_record(relative_path: str, left: Path, right: Path) -> FileRecord:
    left_stat = left.stat()
    right_stat = right.stat()
    left_size = left_stat.st_size if left.is_file() else None
    right_size = right_stat.st_size if right.is_file() else None
    return FileRecord(
        relative_path=relative_path,
        kind="Mixed",
        state=CompareState.TYPE_MISMATCH,
        left_path=left,
        right_path=right,
        left_size=left_size,
        right_size=right_size,
        left_mtime=left_stat.st_mtime,
        right_mtime=right_stat.st_mtime,
    )


def _record_kind(is_binary: bool, is_too_large: bool) -> str:
    if is_binary:
        return "Binary"
    if is_too_large:
        return "Large file"
    return "File"
