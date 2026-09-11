"""内存多轮对话：最近 8 轮，空闲 20 分钟切场。"""

from __future__ import annotations

from collections.abc import Callable

from qa.config import IDLE_NEW_SESSION_S, MAX_TURNS


class QaMemory:
    """快速问答会话记忆：保留最近 ``MAX_TURNS`` 轮 user/assistant 对。"""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        """构造空记忆。

        参数:
            clock: 可注入的单调时钟（默认 ``time.monotonic``），便于测试空闲切场。

        副作用:
            无。
        """
        if clock is None:
            import time

            clock = time.monotonic
        self._clock = clock
        self._turns: list[tuple[str, str]] = []
        self._last_activity = self._clock()

    def append_turn(self, user: str, assistant: str) -> None:
        """追加一轮问答；若空闲超时则先清空再写入。

        参数:
            user: 本轮 user 文本。
            assistant: 本轮 assistant 全文。

        返回值:
            无。

        副作用:
            可能因空闲超时清空历史；超出 ``MAX_TURNS`` 时丢弃最早一轮。
        """
        self.touch()
        self._turns.append((user, assistant))
        if len(self._turns) > MAX_TURNS:
            self._turns = self._turns[-MAX_TURNS:]

    def messages(self) -> list[dict[str, str]]:
        """展开为 OpenAI 风格消息列表。

        返回值:
            ``role`` / ``content`` 字典列表，按 user、assistant 交替。

        副作用:
            无。
        """
        out: list[dict[str, str]] = []
        for user, assistant in self._turns:
            out.append({"role": "user", "content": user})
            out.append({"role": "assistant", "content": assistant})
        return out

    def touch(self, now: float | None = None) -> None:
        """刷新活动时间；若已有内容且空闲超过阈值则清空会话。

        参数:
            now: 可选显式时间戳；缺省为 ``clock()``。

        返回值:
            无。

        副作用:
            可能清空 ``_turns``；总是更新 ``_last_activity``。
        """
        ts = self._clock() if now is None else now
        if self._turns and ts - self._last_activity >= IDLE_NEW_SESSION_S:
            self._turns.clear()
        self._last_activity = ts
