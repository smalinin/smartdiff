from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from smartdiff.compare import compare_paths
from smartdiff.diff_window import DiffPreviewPanel, DiffWindow, _range_selection
from smartdiff.models import CompareOptions, CompareState
from smartdiff.sync import SyncDirection, sync_directories
from smartdiff.text_file import read_text_file, write_text_file
from smartdiff.theme import DARK_THEME


class TemporaryFilesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="smartdiff-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class FileTests(TemporaryFilesTestCase):
    def test_supported_encodings_and_newlines_round_trip(self):
        for encoding, bom in (
            ("utf-8", b""), ("utf-8", b"\xef\xbb\xbf"),
            ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff"),
        ):
            for newline in ("\n", "\r\n", "\r"):
                with self.subTest(encoding=encoding, newline=newline):
                    path = self.root / "text.txt"
                    original = bom + ("a" + newline + "\u0411" + newline).encode(encoding)
                    path.write_bytes(original)
                    loaded = read_text_file(path)
                    self.assertTrue(loaded.format.lossless)
                    write_text_file(path, loaded.text, loaded.format, expected_data=loaded.data)
                    self.assertEqual(path.read_bytes(), original)

    def test_lossy_decoding_cannot_be_saved(self):
        for original in (
            "\u041f\u0440\u0438\u0432\u0435\u0442, \u043c\u0438\u0440!".encode("cp1251"),
            b"\xef\xbb\xbfbroken\xff", b"\xff\xfea",
        ):
            with self.subTest(original=original):
                path = self.root / "legacy.ini"
                path.write_bytes(original)
                loaded = read_text_file(path)
                self.assertFalse(loaded.format.lossless)
                with self.assertRaises(ValueError):
                    write_text_file(path, loaded.text, loaded.format)
                self.assertEqual(path.read_bytes(), original)

    def test_literal_replacement_character_is_valid_utf8(self):
        path = self.root / "text.txt"
        path.write_bytes("\ufffd".encode("utf-8"))
        loaded = read_text_file(path)
        self.assertTrue(loaded.format.lossless)
        write_text_file(path, loaded.text, loaded.format)
        self.assertEqual(path.read_bytes(), "\ufffd".encode("utf-8"))

    def test_write_rejects_external_change(self):
        path = self.root / "text.txt"
        path.write_bytes(b"original")
        loaded = read_text_file(path)
        path.write_bytes(b"external")
        with self.assertRaises(ValueError):
            write_text_file(path, "edit", loaded.format, expected_data=loaded.data)
        self.assertEqual(path.read_bytes(), b"external")

    def test_failed_atomic_replace_preserves_original_and_removes_temp_file(self):
        path = self.root / "text.txt"
        path.write_bytes(b"original")
        loaded = read_text_file(path)
        with patch("smartdiff.text_file.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                write_text_file(path, "edit", loaded.format, expected_data=loaded.data)
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_comparison_detects_same_size_change_with_restored_timestamp(self):
        left = self.root / "left.txt"
        right = self.root / "right.txt"
        left.write_bytes(b"aaaa")
        right.write_bytes(b"aaaa")
        for path in (left, right):
            os.utime(path, (4000, 4000))
        self.assertEqual(compare_paths(left, right, CompareOptions()).entries[0].state, CompareState.EQUAL)
        right.write_bytes(b"bbbb")
        os.utime(right, (4000, 4000))
        self.assertEqual(compare_paths(left, right, CompareOptions()).entries[0].state, CompareState.DIFFERENT)

    def make_sync_pair(self, direction, root=None):
        root = root or self.root
        left = root / "L"
        right = root / "R"
        left.mkdir()
        right.mkdir()
        source, target = (left, right) if direction == SyncDirection.LEFT_TO_RIGHT else (right, left)
        source = source / "data.txt"
        target = target / "data.txt"
        source.write_bytes(b"source")
        target.write_bytes(b"older!")
        os.utime(source, (2000, 2000))
        os.utime(target, (1000, 1000))
        return left, right, source, target

    def test_sync_skips_external_changes_on_either_side_in_both_directions(self):
        for direction in SyncDirection:
            for changed_side in ("source", "target"):
                with self.subTest(direction=direction, changed_side=changed_side):
                    with tempfile.TemporaryDirectory(dir=self.root) as subdir:
                        left, right, source, target = self.make_sync_pair(direction, Path(subdir))
                        result = compare_paths(left, right, CompareOptions())
                        changed = source if changed_side == "source" else target
                        changed.write_bytes(b"newer external contents")
                        target_before = target.read_bytes()
                        synced = sync_directories(result, direction)
                        self.assertEqual(synced.conflicting_paths, ("data.txt",))
                        self.assertEqual(synced.files_overwritten, 0)
                        self.assertEqual(target.read_bytes(), target_before)

    def test_sync_detects_change_even_when_size_and_timestamp_are_preserved(self):
        left, right, source, target = self.make_sync_pair(SyncDirection.LEFT_TO_RIGHT)
        result = compare_paths(left, right, CompareOptions())
        before = target.stat()
        target.write_bytes(b"change")
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        synced = sync_directories(result, SyncDirection.LEFT_TO_RIGHT)
        self.assertEqual(synced.skipped_conflicts, 1)
        self.assertEqual(target.read_bytes(), b"change")

    def test_sync_does_not_overwrite_newly_created_target(self):
        left, right, source, target = self.make_sync_pair(SyncDirection.LEFT_TO_RIGHT)
        target.unlink()
        result = compare_paths(left, right, CompareOptions())
        target.write_bytes(b"new file")
        synced = sync_directories(result, SyncDirection.LEFT_TO_RIGHT)
        self.assertEqual(synced.skipped_conflicts, 1)
        self.assertEqual(target.read_bytes(), b"new file")

    def test_sync_copies_unchanged_source_and_target_in_both_directions(self):
        for direction in SyncDirection:
            with self.subTest(direction=direction):
                with tempfile.TemporaryDirectory(dir=self.root) as subdir:
                    left, right, source, target = self.make_sync_pair(direction, Path(subdir))
                    (source.parent / "nested").mkdir()
                    (source.parent / "nested" / "new.txt").write_bytes(b"nested")
                    result = compare_paths(left, right, CompareOptions())
                    synced = sync_directories(result, direction)
                    self.assertEqual(synced.skipped_conflicts, 0)
                    self.assertEqual(synced.files_overwritten, 1)
                    self.assertEqual(synced.new_files_copied, 1)
                    self.assertEqual(target.read_bytes(), source.read_bytes())
                    self.assertEqual((target.parent / "nested" / "new.txt").read_bytes(), b"nested")


class EditorTests(TemporaryFilesTestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self, left=b"left\n", right=b"right\n"):
        left_path = self.root / "left.txt"
        right_path = self.root / "right.txt"
        left_path.write_bytes(left)
        right_path.write_bytes(right)
        window = DiffWindow(left_path, right_path)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.recompare_timer.stop)
        return window

    def test_save_preserves_unedited_side_and_its_external_changes(self):
        window = self.make_window()
        window.right_path.write_bytes(b"external update")
        before = window.right_path.stat().st_mtime_ns
        window.left_edit.insertPlainText("edit-")
        self.assertTrue(window.save())
        self.assertEqual(window.left_path.read_bytes(), b"edit-left\n")
        self.assertEqual(window.right_path.read_bytes(), b"external update")
        self.assertEqual(window.right_path.stat().st_mtime_ns, before)
        self.assertFalse(window._has_unsaved_changes())

    def test_save_without_edits_does_not_write_either_side(self):
        window = self.make_window()
        with patch("smartdiff.diff_window.write_text_file") as write:
            self.assertTrue(window.save())
        write.assert_not_called()

    def test_conflict_on_second_side_prevents_writing_first_side(self):
        window = self.make_window()
        window.left_edit.insertPlainText("edit-")
        window.right_edit.insertPlainText("edit-")
        window.right_path.write_bytes(b"external")
        with patch("smartdiff.diff_window.QMessageBox.critical") as message:
            self.assertFalse(window.save())
        message.assert_called_once()
        self.assertEqual(window.left_path.read_bytes(), b"left\n")
        self.assertEqual(window.right_path.read_bytes(), b"external")
        self.assertTrue(window._has_unsaved_changes())

    def test_deleted_edited_file_is_not_silently_recreated(self):
        window = self.make_window()
        window.left_edit.insertPlainText("edit-")
        window.left_path.unlink()
        with patch("smartdiff.diff_window.QMessageBox.critical"):
            self.assertFalse(window.save())
        self.assertFalse(window.left_path.exists())

    def test_repeated_saves_update_disk_snapshot(self):
        window = self.make_window()
        for prefix in ("first-", "second-"):
            window.left_edit.insertPlainText(prefix)
            self.assertTrue(window.save())
            self.assertEqual(window.left_original_data, window.left_path.read_bytes())
        self.assertFalse(window._has_unsaved_changes())

    def test_unsupported_side_is_read_only_and_other_side_can_save(self):
        original = "\u041f\u0440\u0438\u0432\u0435\u0442, \u043c\u0438\u0440!".encode("cp1251")
        window = self.make_window(right=original)
        self.assertTrue(window.right_edit.isReadOnly())
        self.assertFalse(window.left_edit.isReadOnly())
        window.left_edit.insertPlainText("edit-")
        self.assertTrue(window.save())
        self.assertEqual(window.right_path.read_bytes(), original)

    def test_lossy_side_cannot_be_used_in_merge_actions(self):
        original = b"legacy\xff"
        window = self.make_window(right=original)
        before = (window.left_edit.toPlainText(), window.right_edit.toPlainText())
        block = window.diff_blocks[0]
        window.copy_current_line("left", "right")
        window.copy_current_block("left", "right")
        window.copy_diff_block(block, "left", "right")
        window.copy_diff_block(block, "right", "left")
        window.delete_diff_block(block, "right")
        self.assertEqual((window.left_edit.toPlainText(), window.right_edit.toPlainText()), before)

    def test_partial_save_failure_keeps_unsaved_side_dirty(self):
        window = self.make_window()
        window.left_edit.insertPlainText("edit-")
        window.right_edit.insertPlainText("edit-")
        original_write = write_text_file

        def write(path, *args, **kwargs):
            if path == window.right_path:
                raise PermissionError("locked")
            return original_write(path, *args, **kwargs)

        with patch("smartdiff.diff_window.write_text_file", side_effect=write), \
             patch("smartdiff.diff_window.QMessageBox.critical"):
            self.assertFalse(window.save())
        self.assertEqual(window.left_path.read_bytes(), b"edit-left\n")
        self.assertEqual(window.right_path.read_bytes(), b"right\n")
        self.assertFalse(window.left_edit.document().isModified())
        self.assertTrue(window.right_edit.document().isModified())
        self.assertTrue(window.save())
        self.assertEqual(window.right_path.read_bytes(), b"edit-right\n")

    def test_close_and_reload_stop_when_save_fails(self):
        window = self.make_window()
        window.left_edit.insertPlainText("edit-")
        with patch.object(window, "_show_unsaved_changes_dialog", return_value="save"), \
             patch.object(window, "save", return_value=False), \
             patch.object(window, "_load_files") as load:
            event = QCloseEvent()
            window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            window.reload_files()
            load.assert_not_called()
        self.assertTrue(window._has_unsaved_changes())

    def test_find_navigates_all_matches_after_emoji(self):
        text = "\U0001f600abc\n\U0001f600abc"
        window = self.make_window(left=text.encode("utf-8"))
        window.find_query = "abc"
        window._refresh_find_matches(keep_current=False)
        self.assertEqual(len(window.find_matches), 2)
        for delta in (0, 1, -1):
            window.move_find(delta)
            self.assertEqual(window.left_edit.textCursor().selectedText(), "abc")

    def test_find_can_select_supplementary_character(self):
        window = self.make_window(left="a\U0001f600b\U0001f600".encode("utf-8"))
        window.find_query = "\U0001f600"
        window._refresh_find_matches(keep_current=False)
        for delta in (0, 1):
            window.move_find(delta)
            self.assertEqual(window.left_edit.textCursor().selectedText(), "\U0001f600")

    def test_inline_highlight_after_emoji_selects_changed_character(self):
        window = self.make_window(left="\U0001f600abc".encode("utf-8"), right="\U0001f600axc".encode("utf-8"))
        for side, expected in (("left", "b"), ("right", "x")):
            style = next(style for style in window.inline_styles if style.side == side)
            selection = _range_selection(getattr(window, f"{side}_edit"), style.line, style.start, style.end, "#ffffff")
            self.assertEqual(selection.cursor.selectedText(), expected)

    def test_cursor_snapshot_preserves_position_after_emoji(self):
        window = self.make_window(left="\U0001f600abc".encode("utf-8"))
        cursor = window.left_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        window.left_edit.setTextCursor(cursor)
        snapshot = window._capture_cursor_snapshot(cursor)
        window._restore_cursor_snapshot(window.left_edit, snapshot)
        self.assertEqual(window.left_edit.textCursor().position(), 5)

    def test_preview_and_editor_agree_on_trailing_newlines(self):
        for left, right in ((b"alpha\n", b"alpha"), (b"", b"\n"), (b"alpha\r\n", b"alpha"), (b"alpha\r", b"alpha")):
            with self.subTest(left=left, right=right):
                window = self.make_window(left=left, right=right)
                preview = DiffPreviewPanel(DARK_THEME)
                self.addCleanup(preview.deleteLater)
                preview.load(window.left_path, window.right_path, "test", "Different", "", "")
                self.assertTrue(window.diff_blocks)
                self.assertEqual(preview.diff_blocks, window.diff_blocks)


if __name__ == "__main__":
    unittest.main()
