"""流式分句、短句合并与开播水位，无网络。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.sentences import (  # noqa: E402
    SentenceSplitter,
    merge_short_sentences,
    ready_to_play,
)


def test_split_on_full_stop_keeps_punct() -> None:
    sp = SentenceSplitter()
    assert sp.push("你好。世界！") == ["你好。"]
    assert sp.finish() == ["世界！"]


def test_comma_does_not_split() -> None:
    sp = SentenceSplitter()
    assert sp.push("细胞壁，细胞膜") == []
    assert sp.finish() == ["细胞壁，细胞膜"]


def test_newline_splits() -> None:
    sp = SentenceSplitter()
    assert sp.push("甲\n乙") == ["甲"]
    assert sp.finish() == ["乙"]


def test_newline_boundary_survives_refill() -> None:
    """换行切出的句子回填缓冲区后边界不能丢，否则多行回答会被粘成一句。"""
    sp = SentenceSplitter()
    out = sp.push("甲\n")
    out += sp.push("乙\n")
    out += sp.finish()
    assert out == ["甲", "乙"]


def test_merge_short_with_following_sentence() -> None:
    out = merge_short_sentences(["好。", "这是洋葱。"], producer_done=False)
    assert out == ["好。这是洋葱。"]


def test_short_alone_when_producer_done_is_kept() -> None:
    assert merge_short_sentences(["好。"], producer_done=True) == ["好。"]


def test_ready_to_play_waits_for_two_until_done() -> None:
    assert ready_to_play(1, False) is False
    assert ready_to_play(2, False) is True
    assert ready_to_play(1, True) is True
    assert ready_to_play(0, True) is False
