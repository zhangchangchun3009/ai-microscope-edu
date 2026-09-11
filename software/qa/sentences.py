"""流式分句、短句合并与开播水位判定。"""

from __future__ import annotations

from qa.config import PLAY_START_WATERMARK, SHORT_SENTENCE_CHARS

# 句末切分字符：中文/英文句号、问号、叹号及换行
_SPLIT_CHARS = frozenset("。！？!?\n")
# 短句判定时需剥离的空白与标点
_STRIP_CHARS = " \t\n\r。！？!?.,，"


def _effective_len(text: str) -> int:
    """返回去掉空白与句末标点后用于短句判定的有效字符数。"""
    return len(text.strip().strip(_STRIP_CHARS))


class SentenceSplitter:
    """流式文本分句器：按句末标点或换行切分，保留标点。"""

    def __init__(self) -> None:
        self._buf = ""

    def push(self, chunk: str) -> list[str]:
        """追加文本块，返回已完整的句子列表。

        参数:
            chunk: 流式输入的一段文本。

        返回值:
            本次 push 中已切出的完整句子（含句末标点）。

        副作用:
            未切完的尾部保留在内部缓冲区；若 chunk 以句末标点结束，
            最后一句仍留在缓冲区，待 finish 或后续 push 再输出。
        """
        self._buf += chunk
        pairs = self._drain_complete()
        if pairs and not self._buf:
            # 缓冲区全是完整句时，保留最后一句供后续合并或 finish 刷新。
            # 必须回填**原始切片**（含分隔符），否则换行边界会永久丢失，
            # 下一次 push 会把它和后一句粘成一句。
            self._buf = pairs.pop()[1]
        return [sentence for sentence, _raw in pairs]

    def _drain_complete(self) -> list[tuple[str, str]]:
        """从缓冲区切出所有完整句，剩余尾巴留回 _buf。

        返回值:
            ``(句子, 原始切片)`` 列表；句子已按分隔符规则处理（换行不保留、
            标点保留），原始切片含分隔符，供 push 回填时还原边界。

        副作用:
            把最后一个分隔符之后的尾巴写回 ``_buf``。
        """
        out: list[tuple[str, str]] = []
        start = 0
        for i, ch in enumerate(self._buf):
            if ch in _SPLIT_CHARS:
                sentence = self._buf[start:i]
                raw = self._buf[start : i + 1]
                if ch == "\n":
                    if sentence:
                        out.append((sentence, raw))
                else:
                    out.append((sentence + ch, raw))
                start = i + 1
        self._buf = self._buf[start:]
        return out

    def finish(self) -> list[str]:
        """刷新缓冲区，返回剩余未切分的文本作为最后一句（若有）。

        返回值:
            缓冲区中剩余文本组成的列表（0 或 1 个元素）；回填的换行分隔符
            不进入句子文本。

        副作用:
            清空内部缓冲区。
        """
        # _buf 内的换行只可能来自 push 的原始切片回填，按分隔符语义剥掉。
        tail = self._buf.rstrip("\n")
        self._buf = ""
        return [tail] if tail else []


def merge_short_sentences(
    parts: list[str],
    *,
    producer_done: bool,
    min_chars: int = SHORT_SENTENCE_CHARS,
) -> list[str]:
    """将过短句子与后续句子合并，避免 TTS 播报碎句。

    参数:
        parts: 待合并的句子列表。
        producer_done: **本函数不使用**，仅为调用约定保留（plan 规定的签名）。
            末尾短句要不要"留一拍"等下一句，由调用方决定：见
            ``voice.session.VoiceSession._run_turn`` 里的 ``ingest``——流未结束时
            它把合并结果的最后一条短句退回 pending，流结束时才整批入队。
        min_chars: 短句阈值（有效字符数，不含空白与句末标点）。

    返回值:
        合并后的句子列表；末尾短句无后继时原样保留，不因 producer_done 而变化。

    副作用:
        无。
    """
    del producer_done  # 语义在调用方（见上）；此处显式说明未使用，避免假信心。
    if not parts:
        return []

    merged: list[str] = []
    i = 0
    while i < len(parts):
        current = parts[i]
        while (
            _effective_len(current) < min_chars
            and i + 1 < len(parts)
        ):
            i += 1
            current = current + parts[i]
        merged.append(current)
        i += 1

    return merged


def ready_to_play(
    queued: int,
    producer_done: bool,
    watermark: int = PLAY_START_WATERMARK,
) -> bool:
    """判断是否满足 TTS 开播水位。

    参数:
        queued: 已排队待播的句子数。
        producer_done: 上游是否已全部产出。
        watermark: 流式产出时的最低排队句数。

    返回值:
        True 表示可以开始播放。

    副作用:
        无。
    """
    if queued <= 0:
        return False
    if producer_done:
        return queued >= 1
    return queued >= watermark
