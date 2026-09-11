"""快速问答：prompt 组装、空知识库与 8 轮记忆，无网络。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.config import IDLE_NEW_SESSION_S, QA_ROLE_CORE, USER_MD_MAX_CHARS  # noqa: E402
from qa.knowledge import EmptyRecall  # noqa: E402
from qa.memory import QaMemory  # noqa: E402
from qa.prompt import build_system_prompt, build_user_message  # noqa: E402


def test_empty_recall_returns_empty() -> None:
    assert EmptyRecall().lookup("细胞壁是什么") == ""


def test_build_user_message_without_knowledge() -> None:
    assert build_user_message("", "这是什么？") == "这是什么？"
    assert build_user_message("  \n\t  ", "这是什么？") == "这是什么？"


def test_build_user_message_with_knowledge_prefix() -> None:
    kb = "【知识库】线粒体是能量工厂。\n"
    assert build_user_message(kb, "这是什么？") == (
        "【知识库】线粒体是能量工厂。\n这是什么？"
    )


def test_build_system_prompt_datetime_and_user_md_truncation() -> None:
    now = datetime(2026, 9, 10, 19, 0, 0)
    long_md = "测" * 1500
    prompt = build_system_prompt(now, long_md)
    assert "2026-09-10 19:00:00" in prompt
    assert "测" * USER_MD_MAX_CHARS in prompt
    assert "测" * (USER_MD_MAX_CHARS + 1) not in prompt
    core = QA_ROLE_CORE.replace("{datetime}", "2026-09-10 19:00:00")
    assert prompt.startswith(core)


def test_build_system_prompt_empty_user_md() -> None:
    now = datetime(2026, 9, 10, 19, 0, 0)
    expected = QA_ROLE_CORE.replace("{datetime}", "2026-09-10 19:00:00")
    assert build_system_prompt(now, "") == expected
    assert build_system_prompt(now, "   ") == expected


def test_qa_memory_keeps_last_eight_turns() -> None:
    clock = {"t": 0.0}
    mem = QaMemory(clock=lambda: clock["t"])
    for i in range(1, 10):
        mem.append_turn(f"u{i}", f"a{i}")
    msgs = mem.messages()
    assert len(msgs) == 16
    assert msgs[0] == {"role": "user", "content": "u2"}
    assert msgs[-1] == {"role": "assistant", "content": "a9"}


def test_qa_memory_idle_touch_clears() -> None:
    clock = {"t": 0.0}
    mem = QaMemory(clock=lambda: clock["t"])
    mem.append_turn("u1", "a1")
    mem.append_turn("u2", "a2")
    assert len(mem.messages()) == 4
    clock["t"] = IDLE_NEW_SESSION_S + 1
    mem.touch()
    assert mem.messages() == []
