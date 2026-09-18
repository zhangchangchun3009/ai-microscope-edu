"""内嵌虚拟键盘：未开 IM 模块时不创建；开启时写入 Desktop disable。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))


def test_attach_keyboard_noop_without_im_module() -> None:
    os.environ.pop("QT_IM_MODULE", None)
    from app.input_panel import attach_embedded_keyboard

    assert attach_embedded_keyboard(None) is None  # type: ignore[arg-type]


def test_keyboard_panel_height_uses_implicit_when_tall_enough() -> None:
    from app.input_panel import keyboard_panel_height

    assert keyboard_panel_height(1080, 700) == 700
    assert keyboard_panel_height(1080, 2000) == 1000  # cap host-80


def test_keyboard_panel_height_fallback_about_half_screen() -> None:
    from app.input_panel import keyboard_panel_height

    h = keyboard_panel_height(1080, 0)
    assert 500 <= h <= 720


def test_apply_virtual_keyboard_sets_desktop_disable(monkeypatch) -> None:
    monkeypatch.setenv("QT_IM_MODULE", "qtvirtualkeyboard")
    monkeypatch.delenv("QT_VIRTUALKEYBOARD_DESKTOP_DISABLE", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    from app.platform import apply_virtual_keyboard_locale

    apply_virtual_keyboard_locale()
    assert os.environ.get("QT_VIRTUALKEYBOARD_DESKTOP_DISABLE") == "1"
    assert os.environ.get("QT_QUICK_BACKEND") == "software"
