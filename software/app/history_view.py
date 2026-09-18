"""历史正文 HTML：时间戳与用户/助手对比色块。"""

from __future__ import annotations

from datetime import datetime
from html import escape

from qa.store import TurnRecord

_USER_BG = "#243044"
_ASSISTANT_BG = "#16332e"
_TEXT = "#e7eef6"
_MUTED = "#8d9aab"


def format_turn_stamp(created_at: float) -> str:
    """把 unix 秒格式化成本地「年月日时分秒」。

    参数:
        created_at: 该轮写入时间（unix 秒）。

    返回:
        如 ``2026年09月18日 19:07:34``。

    副作用:
        无。
    """
    dt = datetime.fromtimestamp(float(created_at))
    return dt.strftime("%Y年%m月%d日 %H:%M:%S")


def history_body_html(turns: list[TurnRecord]) -> str:
    """把一轮轮用户/助手拼成只读 HTML。

    参数:
        turns: 场内轮次，按 seq 已排好。

    返回:
        可交给 ``QTextEdit.setHtml`` 的文档；空列表为「还没有问答」。

    副作用:
        无。
    """
    if not turns:
        return escape("还没有问答")
    chunks = [
        (
            "<style>"
            f".historyWho {{ color:{_MUTED}; font-size:18px; margin-bottom:6px; }}"
            ".historyBodyLine { font-size:22px; white-space:pre-wrap; }"
            ".historyBubble { border-radius:12px; padding:12px; margin:0 0 12px 0; }"
            f".historyUser {{ background:{_USER_BG}; color:{_TEXT}; }}"
            f".historyAssistant {{ background:{_ASSISTANT_BG}; color:{_TEXT}; }}"
            "</style>"
        )
    ]
    for turn in turns:
        stamp = format_turn_stamp(turn.created_at)
        chunks.append(
            _bubble("historyUser", f"用户 {stamp}：", turn.user_text)
        )
        chunks.append(
            _bubble("historyAssistant", f"助手 {stamp}：", turn.assistant_text)
        )
    return "".join(chunks)


def _bubble(css_class: str, who: str, body: str) -> str:
    """一块带角色标题的气泡。"""
    return (
        f'<div class="historyBubble {css_class}">'
        f'<div class="historyWho">{escape(who)}</div>'
        f'<div class="historyBodyLine">{escape(body)}</div>'
        "</div>"
    )
