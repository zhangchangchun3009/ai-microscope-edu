"""快速问答端口：组消息、记忆、流式拉取助手 token。"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path

from qa.client import LlmConfig, iter_chat_tokens, load_llm_config
from qa.knowledge import EmptyRecall, KnowledgeRecall
from qa.memory import QaMemory
from qa.prompt import build_system_prompt, build_user_message

_SOFTWARE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_QA_DIR = _SOFTWARE_ROOT / "var" / "qa"


class QaService:
    """会话用问答端口：持有记忆与空知识库，缺 LLM 配置时不产出 token。"""

    def __init__(
        self,
        *,
        qa_dir: Path | None = None,
        environ: Mapping[str, str] | None = None,
        memory: QaMemory | None = None,
        recall: KnowledgeRecall | None = None,
        config: LlmConfig | None = None,
    ) -> None:
        """构造问答服务。

        参数:
            qa_dir: 存放 ``USER.md`` / ``llm.json`` 的目录；缺省 ``software/var/qa``。
            environ: 覆盖 LLM 环境变量；缺省读取进程环境。
            memory: 可注入的多轮记忆；缺省新建 ``QaMemory``。
            recall: 知识库召回；缺省 ``EmptyRecall``。
            config: 已解析的 LLM 配置；提供时不再读盘。

        副作用:
            未传入 ``config`` 时可能读取 ``qa_dir/llm.json``。
        """
        self._qa_dir = qa_dir if qa_dir is not None else _DEFAULT_QA_DIR
        self._user_md_path = self._qa_dir / "USER.md"
        self.memory = memory if memory is not None else QaMemory()
        self._recall = recall if recall is not None else EmptyRecall()
        if config is not None:
            self._config = config
        else:
            env = environ if environ is not None else os.environ
            self._config = load_llm_config(self._qa_dir, env)

    def iter_tokens(self, user_text: str) -> Iterator[str]:
        """组 prompt 后流式产出助手文本。

        参数:
            user_text: 本轮用户问句（通常为 ASR 文本）。

        返回值:
            增量 token。缺配置时立即结束（空迭代）；``QaClientError`` 原样抛出
            以便会话层按失败处理。

        副作用:
            可能读取 ``USER.md`` 并发出 HTTP 请求。
        """
        if self._config is None:
            return
            yield  # pragma: no cover  — 保持生成器类型
        messages = self._build_messages(user_text)
        yield from iter_chat_tokens(self._config, messages)

    def append_turn(self, user: str, assistant: str) -> None:
        """把一轮完整问答写入记忆。

        参数:
            user: 用户原文。
            assistant: 助手全文（token 拼接，不是合并后的播报句）。

        返回值:
            无。

        副作用:
            更新 ``memory``；可能因空闲超时先清空再写入。
        """
        self.memory.append_turn(user, assistant)

    def _build_messages(self, user_text: str) -> list[dict[str, str]]:
        """读取 USER.md、召回知识并组装 system + 历史 + user。"""
        user_md = self._read_user_md()
        system = build_system_prompt(datetime.now(), user_md)
        knowledge = self._recall.lookup(user_text)
        user_msg = build_user_message(knowledge, user_text)
        return [
            {"role": "system", "content": system},
            *self.memory.messages(),
            {"role": "user", "content": user_msg},
        ]

    def _read_user_md(self) -> str:
        """若 USER.md 存在则读出全文，读失败当空。"""
        if not self._user_md_path.is_file():
            return ""
        try:
            return self._user_md_path.read_text(encoding="utf-8")
        except OSError:
            return ""
