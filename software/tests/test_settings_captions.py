"""字幕开关：与方向钮同高的开/关按钮，不用勾选框。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.settings_page import SettingsPage, captions_toggle_text  # noqa: E402
from app.theme import SETTINGS_CTRL_H, apply_theme  # noqa: E402
from system.edu_config import defaults  # noqa: E402


@pytest.fixture
def qapp() -> QApplication:
    """进程内唯一 QApplication。"""
    return QApplication.instance() or QApplication([])


def test_captions_toggle_text() -> None:
    assert captions_toggle_text(False) == "关"
    assert captions_toggle_text(True) == "开"


def test_captions_button_matches_rotation_height(qapp: QApplication) -> None:
    """字幕是可点的开/关钮，高度与 90° 方向钮相同。"""
    apply_theme(qapp)
    page = SettingsPage(on_close=lambda: None, settings=defaults(), on_change=lambda **_k: True)
    page.show()
    qapp.processEvents()
    assert page._captions.isCheckable()
    assert page._captions.text() == "关"
    assert page._captions.height() == page._rot_buttons[90].height()
    assert page._captions.height() >= SETTINGS_CTRL_H
    page._captions.click()
    qapp.processEvents()
    assert page._captions.isChecked()
    assert page._captions.text() == "开"
    page.close()


def test_theme_has_no_captions_checkbox(qapp: QApplication) -> None:
    apply_theme(qapp)
    sheet = qapp.styleSheet()
    assert "QCheckBox#settingsToggle" not in sheet
