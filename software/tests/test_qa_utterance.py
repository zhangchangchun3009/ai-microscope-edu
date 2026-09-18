"""语音「新对话」口令判定。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.utterance import is_new_session_utterance  # noqa: E402


def test_new_session_exact_phrases() -> None:
    assert is_new_session_utterance("新对话") is True
    assert is_new_session_utterance("新会话") is True
    assert is_new_session_utterance("新建对话") is True
    assert is_new_session_utterance("新建会话") is True
    assert is_new_session_utterance("  新对话。") is True
    assert is_new_session_utterance("开始新会话") is False
    assert is_new_session_utterance("新的对话") is False
    assert is_new_session_utterance("新的对话方式是什么") is False
    assert is_new_session_utterance("洋葱表皮是什么") is False
    assert is_new_session_utterance("") is False
