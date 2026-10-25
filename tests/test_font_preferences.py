from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from smartdiff import app_settings
from smartdiff.diff_window import DiffWindow
from smartdiff.main_window import MainWindow
from smartdiff.settings_dialog import SettingsDialog
from smartdiff.theme import LIGHT_THEME


class FontPreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if os.name == "nt":
            for filename in ("consola.ttf", "segoeui.ttf"):
                font_path = Path("C:/Windows/Fonts") / filename
                if font_path.exists():
                    QFontDatabase.addApplicationFont(str(font_path))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="smartdiff-font-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_path = self.root / "settings.json"
        for name, value in (
            ("SETTINGS_PATH", self.settings_path),
            ("_current_settings", app_settings.default_settings()),
        ):
            context = patch.object(app_settings, name, value)
            context.start()
            self.addCleanup(context.stop)

    def dispose(self, widget):
        if isinstance(widget, DiffWindow):
            widget.recompare_timer.stop()
        widget.hide()
        widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def make_diff(self):
        left = self.root / "l.txt"
        right = self.root / "r.txt"
        left.write_text("anchor0\nold\nanchor1\n", encoding="utf-8")
        right.write_text("anchor0\nnew1\nnew2\nanchor1\n", encoding="utf-8")
        window = DiffWindow(left, right)
        self.addCleanup(self.dispose, window)
        window.show()
        QTest.qWait(15)
        return window

    def test_legacy_settings_keep_font_defaults(self):
        self.settings_path.write_text(json.dumps({"max_text_diff_bytes": 1024}), encoding="utf-8")
        settings = app_settings.load_settings()
        self.assertEqual(settings.editor_font_family, "")
        self.assertEqual(settings.editor_font_size, app_settings.DEFAULT_EDITOR_FONT_SIZE)
        self.assertEqual(settings.max_text_diff_bytes, 1024)

    def test_font_choices_persist_across_reload(self):
        settings = replace(app_settings.default_settings(), editor_font_family="Consolas", editor_font_size=18.5)
        app_settings.save_settings(settings)
        self.assertEqual(app_settings.load_settings(), settings)
        self.assertEqual(app_settings.get_settings(), settings)

    def test_invalid_font_values_use_defaults(self):
        for size in (None, True, "18", 0, 5.9, 72.1, float("nan"), float("inf")):
            with self.subTest(size=size):
                self.settings_path.write_text(json.dumps({"editor_font_family": 123, "editor_font_size": size}), encoding="utf-8")
                settings = app_settings.load_settings()
                self.assertEqual(settings.editor_font_family, "")
                self.assertEqual(settings.editor_font_size, app_settings.DEFAULT_EDITOR_FONT_SIZE)

    def test_dialog_reads_and_returns_font_choices(self):
        families = QFontDatabase.families()
        family = families[0] if families else ""
        app_settings._current_settings = replace(app_settings.get_settings(), editor_font_family=family, editor_font_size=16.5)
        dialog = SettingsDialog()
        self.addCleanup(self.dispose, dialog)
        self.assertEqual(dialog.editor_font_size.value(), 16.5)
        if family:
            self.assertEqual(
                QFontInfo(dialog.editor_font_combo.currentFont()).family(),
                QFontInfo(QFont(family)).family(),
            )
            dialog.editor_font_combo.setCurrentFont(QFont(families[-1]))
        dialog.editor_font_size.setValue(22)
        result = dialog.settings()
        self.assertEqual(result.editor_font_size, 22)
        if family:
            # A generic family such as Serif can resolve to DejaVu Serif on Linux.
            self.assertEqual(
                QFontInfo(QFont(result.editor_font_family)).family(),
                QFontInfo(QFont(families[-1])).family(),
            )
        self.assertEqual(result.binary_extensions, app_settings.get_settings().binary_extensions)

    def test_preferences_update_open_editors_preview_and_line_numbers(self):
        main = MainWindow()
        self.addCleanup(self.dispose, main)
        window = self.make_diff()
        main.preview_panel.load(window.left_path, window.right_path, "test", "Different", "", "")
        window.left_edit.insertPlainText("unsaved-")
        window.recompare()
        before_text = window.left_edit.toPlainText()
        before_width = window.left_edit.line_number_area.width()
        families = QFontDatabase.families()
        family = families[0] if families else ""
        updated = replace(app_settings.get_settings(), editor_font_family=family, editor_font_size=24)
        with patch("smartdiff.main_window.SettingsDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog_type.return_value.settings.return_value = updated
            main._open_settings()
        QTest.qWait(15)
        self.assertEqual(app_settings.load_settings(), updated)
        for edit in (window.left_edit, window.right_edit, main.preview_panel.left_edit, main.preview_panel.right_edit):
            self.assertEqual(edit.font().pointSizeF(), 24)
            self.assertEqual(edit.line_number_area.width(), edit.line_number_area_width())
        self.assertGreater(window.left_edit.line_number_area.width(), before_width)
        self.assertEqual(window.left_edit.toPlainText(), before_text)
        self.assertTrue(window._has_unsaved_changes())
        self.assertEqual(window.left_path.read_text(encoding="utf-8"), "anchor0\nold\nanchor1\n")
        window._update_action_buttons()
        self.assertTrue(window.action_buttons)
        for button in window.action_buttons:
            self.assertTrue(window.action_panel.rect().contains(button.geometry()))
        # The common anchor must stay aligned after the font changes and gaps are rebuilt.
        left_anchor = window.left_edit.document().findBlockByNumber(2)
        right_anchor = window.right_edit.document().findBlockByNumber(3)
        self.assertEqual(
            window.left_edit.block_viewport_rect(left_anchor).top(),
            window.right_edit.block_viewport_rect(right_anchor).top(),
        )
        window.apply_theme(LIGHT_THEME)
        self.assertEqual(window.left_edit.font().pointSizeF(), 24)
        new_window = self.make_diff()
        self.assertEqual(new_window.left_edit.font().pointSizeF(), 24)

    def test_font_preview_updates_without_saving_or_changing_settings(self):
        original = app_settings.get_settings()
        dialog = SettingsDialog()
        self.addCleanup(self.dispose, dialog)
        sample = dialog.font_preview.toPlainText()
        self.assertIn('\u0421\u044a\u0435\u0448\u044c \u0435\u0449\u0451 \u044d\u0442\u0438\u0445 \u043c\u044f\u0433\u043a\u0438\u0445 \u0444\u0440\u0430\u043d\u0446\u0443\u0437\u0441\u043a\u0438\u0445 \u0431\u0443\u043b\u043e\u043a.', sample)
        self.assertTrue(dialog.font_preview.isReadOnly())
        families = QFontDatabase.families()
        if families:
            dialog.editor_font_combo.setCurrentFont(QFont(families[-1]))
            self.assertEqual(
                dialog.font_preview.fontInfo().family(),
                QFontInfo(QFont(families[-1])).family(),
            )
        for size in (6, 18.5, 72):
            dialog.editor_font_size.setValue(size)
            self.assertEqual(dialog.font_preview.font().pointSizeF(), size)
            self.assertEqual(dialog.font_preview.toPlainText(), sample)
        dialog.reject()
        self.assertEqual(app_settings.get_settings(), original)
        self.assertFalse(self.settings_path.exists())

    def test_cancel_does_not_save_preferences(self):
        main = MainWindow()
        self.addCleanup(self.dispose, main)
        with patch("smartdiff.main_window.SettingsDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Rejected
            main._open_settings()
        self.assertFalse(self.settings_path.exists())


if __name__ == "__main__":
    unittest.main()
