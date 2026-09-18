"""会话标题截断与异步 LLM 标题解析。"""

from __future__ import annotations

from qa.client import complete_once  # 再导出，供调度线程与 ``qa.title.complete_once`` patch

# 空场标题：四个汉字，不含书名号。
EMPTY_SESSION_TITLE = "新对话"
# 送给标题模型的 user/assistant 各自截断长度（Unicode 码点）。
_TITLE_SNIPPET_CHARS = 200
_TITLE_MAX_CHARS = 20
_TITLE_SYSTEM = (
    "请根据本轮问答写一个不超过20个字的会话标题。"
    "只输出一行标题，不要引号，不要「标题：」前缀，不要解释。"
)
_WRAP_QUOTES = (
    ('"', '"'),
    ("'", "'"),
    ("“", "”"),
    ("‘", "’"),
    ("「", "」"),
    ("『", "』"),
)
_TITLE_PREFIXES = ("标题：", "标题:")


def clip_title(text: str, max_chars: int = 20) -> str:
    """将文本去空白后按 Unicode 码点截断为标题。

    参数:
        text: 原始标题或首轮 user 文本。
        max_chars: 最大码点数，缺省 20。

    返回值:
        截断后的标题；strip 后为空则返回「新对话」。

    副作用:
        无。
    """
    stripped = text.strip()
    if not stripped:
        return EMPTY_SESSION_TITLE
    return stripped[:max_chars]


def parse_llm_title(raw: str) -> str | None:
    """把模型返回的标题整理成可入库的短标题。

    参数:
        raw: 模型原文。

    返回值:
        去空白、去包裹引号、去掉「标题：」/「标题:」前缀后，再
        ``clip_title(..., 20)``；空或全标点则 ``None``。

    副作用:
        无。
    """
    text = raw.strip()
    text = _strip_wrapping_quotes(text)
    text = _strip_title_prefix(text)
    text = _strip_wrapping_quotes(text).strip()
    if not text or not any(ch.isalnum() for ch in text):
        return None
    clipped = clip_title(text, _TITLE_MAX_CHARS)
    if clipped == EMPTY_SESSION_TITLE:
        return None
    return clipped


def build_title_messages(user: str, assistant: str) -> list[dict[str, str]]:
    """组装标题补全的 chat messages。

    参数:
        user: 本轮用户原文。
        assistant: 本轮助手全文。

    返回值:
        OpenAI 风格 ``role`` / ``content`` 列表。system 要求只回一行
        ≤20 字标题；user/assistant 各截断约 200 字。

    副作用:
        无。
    """
    return [
        {"role": "system", "content": _TITLE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"用户：{user.strip()[:_TITLE_SNIPPET_CHARS]}\n"
                f"助手：{assistant.strip()[:_TITLE_SNIPPET_CHARS]}"
            ),
        },
    ]


def _strip_wrapping_quotes(text: str) -> str:
    """去掉成对包裹引号（含中英文）。"""
    if len(text) < 2:
        return text
    for left, right in _WRAP_QUOTES:
        if text.startswith(left) and text.endswith(right):
            inner = text[len(left) : len(text) - len(right)]
            return inner.strip()
    return text


def _strip_title_prefix(text: str) -> str:
    """去掉开头的「标题：」或「标题:」。"""
    for prefix in _TITLE_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text
