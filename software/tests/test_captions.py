"""字幕按字数分页与定时翻页。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from system.captions import PAGE_HOLD_S, CaptionPager, paginate  # noqa: E402


def test_short_text_single_page() -> None:
    assert paginate("你好", 20) == ["你好"]


def test_paginate_eight_chars_four_max() -> None:
    pages = paginate("abcdefgh", 4)
    assert len(pages) == 2
    assert all(len(p) <= 4 for p in pages)
    assert "".join(pages) == "abcdefgh"


def test_paginate_empty() -> None:
    assert paginate("", 10) == []


def test_pager_advances_after_hold() -> None:
    pager = CaptionPager()
    pager.show("abcdefgh", 4, now=0.0)
    assert pager.visible_text == "abcd"
    pager.tick(1.0)
    assert pager.visible_text == "abcd"
    pager.tick(2.0)
    assert pager.visible_text == "efgh"


def test_pager_advances_after_custom_hold() -> None:
    """TTS 传入总时长时，各幕均分停留。"""
    pager = CaptionPager()
    pager.show("abcdefgh", 4, now=0.0, hold_s=4.0)
    assert pager.visible_text == "abcd"
    pager.tick(1.9)
    assert pager.visible_text == "abcd"
    pager.tick(2.0)
    assert pager.visible_text == "efgh"


def test_pager_clear() -> None:
    pager = CaptionPager()
    pager.show("hello", 10, now=0.0)
    pager.clear()
    assert pager.visible_text == ""


def test_page_hold_constant() -> None:
    assert PAGE_HOLD_S == 2.0


def test_two_line_max_chars_is_width_over_char_times_two() -> None:
    """宽 / 平均汉字宽 × 2 行；至少 8。"""
    from system.captions import two_line_max_chars

    assert two_line_max_chars(100, 10) == 20
    assert two_line_max_chars(40, 10) == 8
    assert two_line_max_chars(10, 10) == 8
    assert two_line_max_chars(100, 0) == 8
    assert two_line_max_chars(0, 10) == 8


def test_caption_bar_disabled_stays_hidden_when_show_text() -> None:
    """字幕关：show_text 不露面；clear 立刻隐藏。"""
    import os

    import pytest

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from app.caption_bar import CaptionBar

    app = QApplication.instance() or QApplication([])
    bar = CaptionBar()
    from PySide6.QtCore import Qt

    assert bar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    bar.set_enabled(False)
    assert bar.isHidden()
    bar.show_text("你好")
    assert bar.isHidden()
    bar.set_enabled(True)
    bar.show_text("你好")
    assert not bar.isHidden()
    assert "你好" in bar.visible_text()
    bar.clear()
    assert bar.isHidden()
    bar.close()
    del app

