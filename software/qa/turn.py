"""快速问答端口：组消息、记忆、流式拉取助手 token、会话落盘。"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path

import qa.title as qa_title
from qa.client import LlmConfig, iter_chat_tokens, load_llm_config
from qa.knowledge import EmptyRecall, KnowledgeRecall
from qa.memory import QaMemory
from qa.prompt import build_system_prompt, build_user_message, load_user_md
from qa.store import SessionRecord, SessionStore, TurnRecord
from system.device_id import read_cpu_serial
from system.edu_config import load_edu, maybe_migrate_llm_json

_SOFTWARE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_QA_DIR = _SOFTWARE_ROOT / "var" / "qa"
_DEFAULT_EDU_YAML = _SOFTWARE_ROOT / "var" / "edu.yaml"
_LOG = logging.getLogger(__name__)


def _run_session_title_worker(
    *,
    user: str,
    assistant: str,
    session_id: str,
    config: LlmConfig,
    store: SessionStore,
) -> None:
    """标题 daemon：非流式补全、解析并写回指定场次（不读当前场指针）。

    参数:
        user: 首轮用户原文。
        assistant: 首轮助手全文。
        session_id: 落盘时的场次 id。
        config: LLM 配置快照。
        store: 场次库。

    返回值:
        无。

    副作用:
        可能 HTTP 请求并 ``update_title``；异常只打日志。
    """
    try:
        messages = qa_title.build_title_messages(user, assistant)
        timeout_s = min(float(config.timeout_s), 15.0)
        raw = qa_title.complete_once(config, messages, timeout_s=timeout_s)
        parsed = qa_title.parse_llm_title(raw)
        if parsed:
            store.update_title(session_id, parsed)
    except Exception:
        _LOG.exception("异步会话标题失败")


class QaService:
    """会话用问答端口：持有记忆、空知识库与可选 SQLite 场次库。"""

    def __init__(
        self,
        *,
        qa_dir: Path | None = None,
        environ: Mapping[str, str] | None = None,
        memory: QaMemory | None = None,
        recall: KnowledgeRecall | None = None,
        config: LlmConfig | None = None,
        store: SessionStore | None = None,
        purge_on_start: bool = True,
    ) -> None:
        """构造问答服务。

        参数:
            qa_dir: 存放 ``USER.md`` 与 ``sessions.sqlite`` 的目录；缺省
                ``software/var/qa``。未注入 ``config`` 时，同级目录的
                ``edu.yaml`` 为 LLM 配置（即 ``qa_dir.parent / edu.yaml``，
                缺省 ``software/var/edu.yaml``）。``qa`` 段（``retain_days`` /
                ``context_turns``）始终从该 yaml 读取；缺失则缺省 7/8。
            environ: 覆盖 LLM 环境变量；缺省读取进程环境。
            memory: 可注入的多轮记忆；缺省按 yaml ``context_turns`` 新建。
            recall: 知识库召回；缺省 ``EmptyRecall``。
            config: 已解析的 LLM 配置；提供时不再读盘，且 ``reload_llm`` 为空操作。
                注入时仍读取 yaml 的 ``qa`` 段。
            store: 可注入的场次库；缺省打开 ``qa_dir/sessions.sqlite``，
                失败则仅用内存（不抛到 GUI）。
            purge_on_start: 为 True 且库可用时，后台线程按 ``retain_days``
                清理过期非当前场；单测应传 False。

        副作用:
            未传入 ``config`` 时：若 yaml 尚无可用 ``llm`` 段，可能把
            ``qa_dir/llm.json`` 迁入 yaml；然后读取 ``edu.yaml``。
            成功打开库后会 hydrate 当前场最近 ``context_turns`` 轮到 memory。
            ``purge_on_start`` 时启动 daemon 清理线程。
        """
        self._qa_dir = qa_dir if qa_dir is not None else _DEFAULT_QA_DIR
        self._edu_yaml = (
            _DEFAULT_EDU_YAML if qa_dir is None else self._qa_dir.parent / "edu.yaml"
        )
        self._user_md_path = self._qa_dir / "USER.md"
        edu = load_edu(self._edu_yaml)
        self._retain_days = edu.retain_days
        self._context_turns = edu.context_turns
        self.memory = (
            memory
            if memory is not None
            else QaMemory(max_turns=self._context_turns)
        )
        self._recall = recall if recall is not None else EmptyRecall()
        self._environ: Mapping[str, str] = environ if environ is not None else os.environ
        self._serial = read_cpu_serial()
        self._config_injected = config is not None
        if self._config_injected:
            self._config = config
        else:
            maybe_migrate_llm_json(
                self._edu_yaml, self._qa_dir / "llm.json", self._serial
            )
            self._config = load_llm_config(
                self._edu_yaml, self._environ, serial=self._serial
            )
        self._store = self._open_store(store)
        self._purge_thread: threading.Thread | None = None
        self._title_thread: threading.Thread | None = None
        if self._store is not None:
            self._hydrate_memory()
            if purge_on_start:
                self._purge_thread = threading.Thread(
                    target=self._purge_expired_quiet,
                    name="edu-qa-purge",
                    daemon=True,
                )
                self._purge_thread.start()

    def reload_llm(self) -> None:
        """从 ``edu.yaml`` 重新加载 LLM 配置。

        参数:
            无。

        返回值:
            无。构造时注入了 ``config=`` 则不改 ``_config``。

        副作用:
            未注入配置时再次读盘解密；不重跑 ``llm.json`` 迁移。
            不重读 ``qa.retain_days`` / ``qa.context_turns``。
        """
        if self._config_injected:
            return
        self._config = load_llm_config(
            self._edu_yaml, self._environ, serial=self._serial
        )

    def iter_tokens(self, user_text: str) -> Iterator[str]:
        """组 prompt 后流式产出助手文本。

        参数:
            user_text: 本轮用户问句（通常为 ASR 文本）。

        返回值:
            增量 token。缺配置时立即结束（空迭代）；``QaClientError`` 原样抛出
            以便会话层按失败处理。

        副作用:
            **调用时**（尚未拉第一个 token）若空闲超时则切场，写入 SQLite，
            不只清内存。这样 ``iter_tokens(...)`` 即使未被迭代也会切场。
            可能读取 ``USER.md`` 并发出 HTTP 请求。本轮使用进入时快照的
            ``_config``，``reload_llm()`` 不打断进行中的回合。
        """
        # 本方法不能写成生成器：否则未迭代时切场不会发生。
        self._maybe_idle_rotate()
        return self._stream_tokens(user_text, self._config)

    def _stream_tokens(
        self, user_text: str, config: LlmConfig | None
    ) -> Iterator[str]:
        """按进入 ``iter_tokens`` 时的配置快照拉 token。"""
        if config is None:
            return
            yield  # pragma: no cover  — 保持生成器类型
        messages = self._build_messages(user_text)
        yield from iter_chat_tokens(config, messages)

    def append_turn(self, user: str, assistant: str) -> None:
        """把一轮完整问答写入当前场与记忆。

        参数:
            user: 用户原文。
            assistant: 助手全文（token 拼接，不是合并后的播报句）。

        返回值:
            无。

        副作用:
            先按空闲超时切场；再尝试落盘（失败只打日志，记忆仍写）；
            最后 ``memory.append_turn``。落盘第一轮成功且有 LLM 配置时
            启动 daemon 线程异步覆盖标题。
        """
        self._maybe_idle_rotate()
        if self._store is not None:
            try:
                seq, session_id = self._store.append_turn(user, assistant)
            except (OSError, sqlite3.Error):
                _LOG.exception("问答轮次落盘失败")
            else:
                if seq == 1:
                    config = self._config
                    if config is not None:
                        self._schedule_session_title(
                            user,
                            assistant,
                            session_id=session_id,
                            config=config,
                            store=self._store,
                        )
        self.memory.append_turn(user, assistant)

    def start_new_session(self) -> str | None:
        """切到新对话场；当前场零轮次则复用。

        参数:
            无。

        返回值:
            切场后的当前场 id；无可用库时清空记忆并返回 ``None``；
            有库但落盘失败时保留记忆并返回 ``None``。

        副作用:
            有库则委托 ``SessionStore.start_new_session``（空场复用、
            有内容则新建并更新 ``current_session_id``）；**仅成功时**把
            ``memory`` 换成同 ``max_turns`` / 时钟的空记忆。无库时只清 memory。
        """
        if self._store is None:
            self.memory = self._blank_memory()
            return None
        try:
            sid = self._store.start_new_session()
        except (OSError, sqlite3.Error):
            _LOG.exception("切场落盘失败")
            return None
        self.memory = self._blank_memory()
        return sid

    def list_sessions(self) -> list[SessionRecord]:
        """列出全部场次（按 ``updated_at`` 新→旧），供历史页。

        参数:
            无。

        返回值:
            ``SessionRecord`` 列表；无可用库时为空列表。

        副作用:
            无。
        """
        if self._store is None:
            return []
        try:
            return self._store.list_sessions()
        except (OSError, sqlite3.Error):
            _LOG.exception("列出会话失败")
            return []

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        """列出一场的全部轮次（按 seq 升序），供历史页只读正文。

        参数:
            session_id: 场次 id。

        返回值:
            ``TurnRecord`` 列表；无库或场不存在时为空列表。

        副作用:
            无。
        """
        if self._store is None:
            return []
        try:
            return self._store.list_turns(session_id)
        except (OSError, sqlite3.Error):
            _LOG.exception("列出轮次失败")
            return []

    def current_session_id(self) -> str | None:
        """返回当前场 id，供历史页标记「当前」。

        参数:
            无。

        返回值:
            当前场 id；无可用库时为 ``None``。

        副作用:
            库可用时可能补空当前场（同 ``SessionStore.current_id``）。
        """
        if self._store is None:
            return None
        try:
            return self._store.current_id()
        except (OSError, sqlite3.Error):
            _LOG.exception("读取当前场 id 失败")
            return None

    def _open_store(self, injected: SessionStore | None) -> SessionStore | None:
        """打开或缺省创建会话库；失败则返回 ``None``。"""
        if injected is not None:
            return injected
        try:
            self._qa_dir.mkdir(parents=True, exist_ok=True)
            return SessionStore(self._qa_dir / "sessions.sqlite")
        except OSError:
            _LOG.exception("无法打开会话库，问答仅使用内存")
            return None

    def _hydrate_memory(self) -> None:
        """把当前场最近 ``context_turns`` 轮填入 memory。"""
        if self._store is None:
            return
        try:
            sid = self._store.current_id()
            pairs = self._store.hydrate_turns(sid, limit=self._context_turns)
        except (OSError, sqlite3.Error):
            _LOG.exception("hydrate 会话记忆失败")
            return
        for user, assistant in pairs:
            self.memory.append_turn(user, assistant)

    def _blank_memory(self) -> QaMemory:
        """构造与当前时钟、yaml 轮数上限一致的空记忆。"""
        return QaMemory(clock=self.memory._clock, max_turns=self._context_turns)

    def _maybe_idle_rotate(self) -> None:
        """若记忆有轮次且空闲超时，则 ``start_new_session``（写入 SQLite）。"""
        if not self.memory.idle_due():
            return
        self.start_new_session()

    def _purge_expired_quiet(self) -> None:
        """启动清理：失败只打日志，不抛到 GUI。"""
        if self._store is None:
            return
        try:
            self._store.purge_expired(retain_days=self._retain_days)
        except Exception:
            _LOG.exception("启动时清理过期会话失败")

    def _schedule_session_title(
        self,
        user: str,
        assistant: str,
        *,
        session_id: str,
        config: LlmConfig,
        store: SessionStore,
    ) -> None:
        """第一轮落盘后在后台用短补全覆盖指定场次的标题。

        参数:
            user: 本轮用户原文。
            assistant: 本轮助手全文。
            session_id: 落盘线程上已确定的场次 id（不再读 ``current_id``）。
            config: 进入调度时的 LLM 配置快照（worker 不读 ``self._config``）。
            store: 场次库实例。

        返回值:
            无。

        副作用:
            启动 daemon 线程调用 ``_run_session_title_worker``；
            失败保持第一句截断标题。不改常规问答 system / ``iter_tokens``。
        """
        self._title_thread = threading.Thread(
            target=_run_session_title_worker,
            kwargs={
                "user": user,
                "assistant": assistant,
                "session_id": session_id,
                "config": config,
                "store": store,
            },
            name="edu-qa-title",
            daemon=True,
        )
        self._title_thread.start()

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
        return load_user_md(self._user_md_path)
