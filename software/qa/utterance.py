"""语音切场口令判定（纯函数，无 TTS / 会话副作用）。"""

from __future__ import annotations

import re

# 与 spec §6 一致：空白 + 。！？,.!?、
_STRIP_RE = re.compile(r"[\s。！？,.!?、]+")

_NEW_SESSION_PHRASES = frozenset(
    {
        "新对话",
        "新会话",
        "新建对话",
        "新建会话",
        # SenseVoice 常把「会话」听成「绘画」；整句相等才转义。
        "新绘画",
        "新建绘画",
    }
)


def _normalize(text: str) -> str:
    """去掉空白与常见标点，便于与口令表精确比对。"""
    return _STRIP_RE.sub("", text)


def is_new_session_utterance(text: str) -> bool:
    """判断 ASR 文本是否为「新对话 / 新会话」切场口令。

    去掉空白与 ``。！？,.!?、`` 后，整句必须 **恰好等于** 「新对话」「新会话」
    「新建对话」「新建会话」，或 ASR 把「会话」听成「绘画」时的「新绘画」
    「新建绘画」；不做子串或关键词包含匹配。

    Args:
        text: SenseVoice 等 ASR 输出的整句文本。

    Returns:
        命中切场口令为 True，否则 False。

    Side effects:
        无。
    """
    normalized = _normalize(text)
    return normalized in _NEW_SESSION_PHRASES
