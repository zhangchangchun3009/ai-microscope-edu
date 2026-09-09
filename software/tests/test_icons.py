"""矢量工具图标：无 PySide6 的开发机自动跳过。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.icons import TOOL_ICON_KEYS, tool_pixmap  # noqa: E402


@pytest.fixture
def app() -> QApplication:
    """返回测试进程唯一的 QApplication。"""
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("key", sorted(TOOL_ICON_KEYS))
def test_tool_icon_is_square_and_has_ink(app: QApplication, key: str) -> None:
    """每个工具键应绘出正方形位图，且不全透明。"""
    pm = tool_pixmap(key, 64)
    assert pm.width() == 64
    assert pm.height() == 64
    image = pm.toImage()
    opaque = 0
    for y in range(0, 64, 4):
        for x in range(0, 64, 4):
            if QColor(image.pixel(x, y)).alpha() > 16:
                opaque += 1
    assert opaque > 8


def test_unknown_icon_key_raises(app: QApplication) -> None:
    """未登记的图标键应拒绝绘制。"""
    with pytest.raises(KeyError):
        tool_pixmap("wifi", 64)
