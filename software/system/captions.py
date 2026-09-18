"""字幕分页与按停留时间自动翻页。"""

from __future__ import annotations

PAGE_HOLD_S: float = 2.0


def two_line_max_chars(width_px: int, char_width_px: int) -> int:
    """按条宽与单字宽估算两行可容纳的字符数。

    参数:
        width_px: 字幕条内容区宽度（像素）。
        char_width_px: 平均汉字宽度（像素）。

    返回:
        ``(width_px // char_width_px) * 2``，至少为 8；宽或字宽非法时为 8。

    副作用:
        无。
    """
    if width_px <= 0 or char_width_px <= 0:
        return 8
    return max(8, (int(width_px) // int(char_width_px)) * 2)


def paginate(text: str, max_chars: int) -> list[str]:
    """按最大字符数将文本切成多页，尽量在词界（空格）处断开。

    参数:
        text: 待分页全文。
        max_chars: 每页上限字符数。

    返回:
        页字符串列表；空串返回 []。
    """
    if not text:
        return []
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    pages: list[str] = []
    rest = text
    while rest:
        if len(rest) <= max_chars:
            pages.append(rest)
            break
        chunk = rest[:max_chars]
        last_space = chunk.rfind(" ")
        if last_space >= 0 and last_space >= max_chars // 2:
            pages.append(rest[:last_space])
            rest = rest[last_space + 1 :]
        else:
            pages.append(rest[:max_chars])
            rest = rest[max_chars:]
    return pages


class CaptionPager:
    """维护当前可见字幕页，并在每页停留时间后自动翻到下一页。"""

    def __init__(self) -> None:
        self._pages: list[str] = []
        self._index: int = 0
        self._shown_at: float = 0.0
        self._hold_s: float = PAGE_HOLD_S

    def show(
        self,
        text: str,
        max_chars: int,
        now: float,
        *,
        hold_s: float | None = None,
    ) -> None:
        """加载新字幕并重置页索引与计时起点。

        参数:
            text: 全文。
            max_chars: 分页上限。
            now: 当前单调时间（秒）。
            hold_s: 整段字幕的总停留；``None`` 则每页 ``PAGE_HOLD_S``（ASR）。
                TTS 传入该句 PCM 时长，各幕均分。

        副作用:
            替换内部分页状态。
        """
        self._pages = paginate(text, max_chars)
        self._index = 0
        self._shown_at = now
        n = max(len(self._pages), 1)
        if hold_s is None:
            self._hold_s = PAGE_HOLD_S
        else:
            self._hold_s = max(0.4, float(hold_s) / n)

    def tick(self, now: float) -> None:
        """若当前页已展示足够久且还有下一页，则前进一页。

        参数:
            now: 当前单调时间（秒）。
        """
        if not self._pages or self._index >= len(self._pages) - 1:
            return
        if now - self._shown_at >= self._hold_s:
            self._index += 1
            self._shown_at = now

    def clear(self) -> None:
        """清空字幕状态。"""
        self._pages = []
        self._index = 0
        self._shown_at = 0.0

    @property
    def visible_text(self) -> str:
        """当前应显示的页文本；无内容时为空串。"""
        if not self._pages or self._index >= len(self._pages):
            return ""
        return self._pages[self._index]
