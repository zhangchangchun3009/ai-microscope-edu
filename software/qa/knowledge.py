"""知识库召回接口；本刀仅空实现。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class KnowledgeRecall(Protocol):
    """知识库文本召回协议。"""

    def lookup(self, text: str) -> str:
        """按用户问句检索相关知识块。

        参数:
            text: 用户原始问句。

        返回值:
            非空时为拼接到 user 消息前的知识块；本刀恒可为空串。

        副作用:
            无（具体实现若访问存储则依实现而定）。
        """
        ...


class EmptyRecall:
    """空知识库：lookup 恒返回空串。"""

    def lookup(self, text: str) -> str:
        """不检索任何知识，恒返回 ``""``。

        参数:
            text: 用户问句（忽略）。

        返回值:
            空字符串。

        副作用:
            无。
        """
        return ""
