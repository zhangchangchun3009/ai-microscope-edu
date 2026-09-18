"""字幕条居中。无 PySide6 的开发机自动跳过。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.caption_bar import CaptionBar  # noqa: E402


@pytest.fixture
def qapp() -> QApplication:
    """进程内唯一 QApplication。"""
    return QApplication.instance() or QApplication([])


def test_caption_text_is_horizontally_centered(qapp: QApplication) -> None:
    """字幕两行在底栏内水平居中。"""
    del qapp
    bar = CaptionBar()
    align = bar._label.alignment()
    assert align & Qt.AlignmentFlag.AlignHCenter
    assert not (align & Qt.AlignmentFlag.AlignLeft)
