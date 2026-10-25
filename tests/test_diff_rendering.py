from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from smartdiff.diff_window import DiffPreviewPanel, DiffWindow
from smartdiff.theme import DARK_THEME, LIGHT_THEME


class DiffRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="smartdiff-render-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def dispose(self, widget):
        if isinstance(widget, DiffWindow):
            widget.recompare_timer.stop()
        widget.hide()
        widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def make_window(self, left, right, size=(1000, 500), theme=DARK_THEME):
        lp = self.root / "l.txt"
        rp = self.root / "r.txt"
        lp.write_text(left, encoding="utf-8")
        rp.write_text(right, encoding="utf-8")
        window = DiffWindow(lp, rp, dark_theme=theme == DARK_THEME)
        self.addCleanup(self.dispose, window)
        window.resize(*size)
        window.show()
        QTest.qWait(20)
        return window

    def refresh(self, window):
        self.app.processEvents()
        window._update_action_buttons()
        self.app.processEvents()

    def assert_buttons_fit(self, window):
        top, bottom = window._gutter_viewport_range()
        for button in window.action_buttons:
            rect = button.geometry()
            self.assertGreaterEqual(rect.top(), top)
            self.assertLess(rect.bottom(), bottom)
            self.assertGreaterEqual(rect.left(), 0)
            self.assertLess(rect.right(), window.action_panel.width())
        for index, button in enumerate(window.action_buttons):
            for other in window.action_buttons[index + 1:]:
                self.assertFalse(button.geometry().intersects(other.geometry()))

    @staticmethod
    def deleted_prefix(count=20, total=150):
        left = []
        right = []
        for index in range(total):
            left.append(f"anchor{index}")
            right.append(f"anchor{index}")
            if index < count:
                left.append(f"removed{index}")
        return "\n".join(left), "\n".join(right)

    def test_no_buttons_or_connectors_for_one_sided_blocks_above_viewport(self):
        left, right = self.deleted_prefix()
        for left, right in ((left, right), (right, left)):
            with self.subTest(left_has_deletions=len(left) > len(right)):
                window = self.make_window(left, right)
                window.left_edit.verticalScrollBar().setValue(900)
                self.refresh(window)
                self.assertTrue(all(window._block_band(block) is None for block in window.diff_blocks))
                self.assertEqual(window.action_buttons, [])

    def test_no_buttons_for_one_sided_blocks_below_viewport(self):
        prefix = "\n".join(f"anchor{i}" for i in range(100)) + "\n"
        window = self.make_window(prefix + "removed\ntail", prefix + "tail")
        window.left_edit.verticalScrollBar().setValue(0)
        self.refresh(window)
        self.assertEqual(window.action_buttons, [])
        self.assertTrue(all(window._block_band(block) is None for block in window.diff_blocks))

    def test_large_visible_blocks_keep_actions_at_top_middle_and_end(self):
        changed = "anchor0\n" + "\n".join(f"removed{i}" for i in range(200)) + "\nanchor1\n"
        short = "anchor0\nanchor1\n"
        for left, right in ((changed, short), (short, changed)):
            with self.subTest(left_has_deletions=len(left) > len(right)):
                window = self.make_window(left, right)
                for offset in (0, 600, window.left_edit.verticalScrollBar().maximum()):
                    window.left_edit.verticalScrollBar().setValue(offset)
                    self.refresh(window)
                    self.assertIsNotNone(window._block_band(window.diff_blocks[0]))
                    self.assertEqual(len(window.action_buttons), 2)
                    self.assert_buttons_fit(window)

    def test_partially_visible_bottom_block_keeps_its_buttons(self):
        left = [f"anchor{i}" for i in range(100)]
        right = left.copy()
        left[30] = "old"
        right[30] = "new"
        window = self.make_window("\n".join(left), "\n".join(right), size=(1000, 300))
        block = window.left_edit.document().findBlockByNumber(30)
        top = window.left_edit.cursorRect(QTextCursor(block)).top() + window.left_edit.verticalScrollBar().value()
        offset = top - window.left_edit.viewport().height() + 5
        window.left_edit.verticalScrollBar().setValue(offset)
        self.refresh(window)
        self.assertIsNotNone(window._block_band(window.diff_blocks[0]))
        self.assertEqual(len(window.action_buttons), 2)
        self.assert_buttons_fit(window)

    def test_dense_rows_never_overlap_or_leave_viewport_after_resize(self):
        left = "\n".join(f"anchor{i}" if i % 2 == 0 else f"old{i}" for i in range(100))
        right = "\n".join(f"anchor{i}" if i % 2 == 0 else f"new{i}" for i in range(100))
        window = self.make_window(left, right)
        for theme in (DARK_THEME, LIGHT_THEME):
            window.apply_theme(theme)
            # At this font size there are more visible differences than full button rows can fit.
            for edit in (window.left_edit, window.right_edit):
                edit.setStyleSheet("QTextEdit { font-size: 7px; }")
            window.recompare()
            for height in (500, 240, 350):
                window.resize(1000, height)
                QTest.qWait(10)
                window.left_edit.verticalScrollBar().setValue(15)
                self.refresh(window)
                self.assertTrue(window.action_buttons)
                self.assert_buttons_fit(window)

    def test_navigation_uses_same_visual_position_for_insertions_and_deletions(self):
        long = "anchor0\n" + "\n".join(f"removed{i}" for i in range(60)) + "\nanchor1\ntail\n"
        short = "anchor0\nanchor1\ntail\n"
        for left, right in ((long, short), (short, long)):
            with self.subTest(left_has_deletions=len(left) > len(right)):
                window = self.make_window(left, right)
                self.assertEqual(window.left_edit.verticalScrollBar().value(), 0)
                self.assertEqual(window.right_edit.verticalScrollBar().value(), 0)
                self.assert_buttons_fit(window)

    def test_navigation_after_prior_insertions_keeps_target_visible_and_aligned(self):
        left = []
        right = []
        for index in range(100):
            left.append(f"anchor{index}")
            right.append(f"anchor{index}")
            if index == 5:
                right.extend(f"inserted{item}" for item in range(30))
            if index == 60:
                left.append("old")
                right.append("new")
        window = self.make_window("\n".join(left), "\n".join(right))
        for index in (1, 0, 1):
            window.current_diff_index = index
            window.move_diff(0)
            self.refresh(window)
            self.assertEqual(window.left_edit.verticalScrollBar().value(), window.right_edit.verticalScrollBar().value())
            block = window.diff_blocks[index]
            self.assertIsNotNone(window._block_band(block))
            self.assertTrue(window.action_buttons)
            if block.tag == "replace":
                band = window._block_band(block)
                self.assertEqual(band[0], band[2])
            self.assert_buttons_fit(window)

    def test_preview_navigation_uses_shared_visual_position(self):
        long = "anchor0\n" + "\n".join(f"removed{i}" for i in range(60)) + "\nanchor1\n"
        short = "anchor0\nanchor1\n"
        window = self.make_window(long, short)
        preview = DiffPreviewPanel(DARK_THEME)
        self.addCleanup(self.dispose, preview)
        preview.resize(1000, 300)
        preview.load(window.left_path, window.right_path, "test", "Different", "", "")
        preview.show()
        QTest.qWait(20)
        preview._move_diff(0)
        self.assertEqual(preview.left_edit.verticalScrollBar().value(), 0)
        self.assertEqual(preview.right_edit.verticalScrollBar().value(), 0)

    def test_connector_edges_match_editor_lines(self):
        window = self.make_window("anchor\nold\ntail", "anchor\nnew1\nnew2\ntail")
        block = window.diff_blocks[0]
        for side in ("left", "right"):
            edit = getattr(window, f"{side}_edit")
            start = getattr(block, f"{side}_start")
            end = getattr(block, f"{side}_end")
            top = edit.cursorRect(QTextCursor(edit.document().findBlockByNumber(start))).top()
            bottom = edit.cursorRect(QTextCursor(edit.document().findBlockByNumber(end - 1))).bottom() + 1
            expected = window._viewport_range_to_action_panel(edit, top, bottom)
            band = window._block_band(block)
            self.assertEqual(band[:2] if side == "left" else band[2:], expected)


if __name__ == "__main__":
    unittest.main()
