"""右侧工具条：圆钮加大并垂直居中。无 PySide6 的开发机自动跳过。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QSpacerItem  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.tool_strip import (  # noqa: E402
    TOOL_BUTTON_DIAMETER,
    TOOL_STRIP_EXPANDED_W,
    ToolStrip,
)


@pytest.fixture
def qapp() -> QApplication:
    """进程内唯一 QApplication。"""
    return QApplication.instance() or QApplication([])


def test_tool_buttons_are_larger_and_cluster_is_centered(qapp: QApplication) -> None:
    """圆钮直径加大；上下有 stretch，整组落在工具条垂直中部。"""
    del qapp
    assert TOOL_BUTTON_DIAMETER >= 72
    assert TOOL_STRIP_EXPANDED_W >= 96
    strip = ToolStrip(on_tool=lambda _k: None, on_toggle=lambda: None)
    strip.set_expanded(True)
    layout = strip.layout()
    assert layout is not None
    first = layout.itemAt(0)
    last = layout.itemAt(layout.count() - 1)
    assert first is not None and isinstance(first.spacerItem(), QSpacerItem)
    assert last is not None and isinstance(last.spacerItem(), QSpacerItem)
    assert strip.width() == TOOL_STRIP_EXPANDED_W
