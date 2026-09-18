"""右栏键盘避让：垫高与滚动距离。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))


def test_scroll_delta_to_clear_keyboard() -> None:
    from app.input_panel import scroll_delta_to_clear_keyboard

    assert scroll_delta_to_clear_keyboard(400, 500) == 0
    assert scroll_delta_to_clear_keyboard(500, 500) == 0
    assert scroll_delta_to_clear_keyboard(520, 500) == 36


def test_apply_virtual_keyboard_sets_zh_en_locales(monkeypatch) -> None:
    monkeypatch.setenv("QT_IM_MODULE", "qtvirtualkeyboard")
    monkeypatch.delenv("QT_VIRTUALKEYBOARD_AVAILABLE_LOCALES", raising=False)
    monkeypatch.delenv("QT_VIRTUALKEYBOARD_DESKTOP_DISABLE", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    from app.platform import VK_LOCALES, apply_virtual_keyboard_locale

    apply_virtual_keyboard_locale()
    assert os.environ.get("QT_VIRTUALKEYBOARD_AVAILABLE_LOCALES") == ",".join(VK_LOCALES)
    assert "zh_CN" in VK_LOCALES
    assert "en_US" in VK_LOCALES
    assert "zh_TW" in VK_LOCALES


def test_apply_right_pane_keyboard_inset_pads_and_clears() -> None:
    """垫块高度跟随键盘；收起后归零。"""
    import pytest

    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget

    from app.input_panel import RIGHT_PAD, RIGHT_SCROLL, apply_right_pane_keyboard_inset

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    inner = QWidget()
    pad = QWidget()
    pad.setObjectName(RIGHT_PAD)
    pad.setFixedHeight(0)
    col = QVBoxLayout(inner)
    col.setContentsMargins(0, 0, 0, 0)
    col.addWidget(QWidget(), 1)
    col.addWidget(pad, 0)
    scroll = QScrollArea(host)
    scroll.setObjectName(RIGHT_SCROLL)
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    host.resize(400, 300)
    host.show()
    app.processEvents()
    apply_right_pane_keyboard_inset(host, 180)
    app.processEvents()
    assert pad.height() == 180
    assert scroll.verticalScrollBar().maximum() > 0
    apply_right_pane_keyboard_inset(host, 0)
    app.processEvents()
    assert pad.height() == 0
    host.close()
    del app
