"""异步 LLM 会话标题：解析、非流式一次补全、首轮调度。"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.client import LlmConfig  # noqa: E402
from qa.turn import QaService  # noqa: E402


def _cfg(*, timeout_s: float = 30.0) -> LlmConfig:
    """构造可注入的假 LLM 配置。"""
    return LlmConfig(
        base_url="https://api.example.com/v1",
        api_key="sk",
        model="qwen-plus",
        timeout_s=timeout_s,
    )


def _join_title_thread(svc: QaService, timeout: float = 1.0) -> None:
    """若服务记下了标题线程则 join，避免只靠 sleep 竞态。"""
    thread = getattr(svc, "_title_thread", None)
    if thread is not None:
        thread.join(timeout=timeout)


def test_parse_llm_title_strips_prefix_and_quotes() -> None:
    from qa.title import parse_llm_title

    assert parse_llm_title("标题：洋葱表皮") == "洋葱表皮"
    assert parse_llm_title('"细胞壁"') == "细胞壁"
    assert parse_llm_title("   ") is None
    assert parse_llm_title("标题:气孔") == "气孔"
    assert parse_llm_title("标题：") is None
    assert parse_llm_title("。。。") is None
    twenty_one = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸末"
    assert parse_llm_title("标题：" + twenty_one) == twenty_one[:20]


def test_build_title_messages_truncates_about_200() -> None:
    from qa.title import build_title_messages

    user = "问" * 250
    assistant = "答" * 250
    msgs = build_title_messages(user, assistant)
    assert msgs[0]["role"] == "system"
    assert "20" in msgs[0]["content"]
    joined = "\n".join(m["content"] for m in msgs)
    assert user[:200] in joined
    assert assistant[:200] in joined
    assert user not in joined
    assert assistant not in joined


def test_first_turn_schedules_title_override(tmp_path: Path, monkeypatch) -> None:
    from qa.client import LlmConfig
    from qa.turn import QaService

    seen: dict[str, float] = {}

    def fake_complete(_config, _messages, *, timeout_s: float) -> str:
        seen["timeout_s"] = timeout_s
        return "洋葱切片观察"

    cfg = LlmConfig(
        base_url="https://api.example.com/v1",
        api_key="sk",
        model="qwen-plus",
        timeout_s=30.0,
    )
    monkeypatch.setattr("qa.title.complete_once", fake_complete)
    svc = QaService(
        qa_dir=tmp_path, environ={}, config=cfg, purge_on_start=False
    )
    svc.append_turn("这是什么标本", "这是洋葱表皮。")
    _join_title_thread(svc)
    # 等标题线程
    for _ in range(50):
        sessions = svc.list_sessions()
        if sessions and sessions[0].title == "洋葱切片观察":
            break
        time.sleep(0.02)
    assert svc.list_sessions()[0].title == "洋葱切片观察"
    assert seen["timeout_s"] == 15.0


def test_title_failure_keeps_user_clip(tmp_path: Path, monkeypatch) -> None:
    from qa.client import LlmConfig
    from qa.turn import QaService

    cfg = LlmConfig(
        base_url="https://api.example.com/v1",
        api_key="sk",
        model="qwen-plus",
        timeout_s=30.0,
    )
    monkeypatch.setattr("qa.title.complete_once", lambda *_a, **_k: "")
    svc = QaService(qa_dir=tmp_path, environ={}, config=cfg, purge_on_start=False)
    svc.append_turn("这是什么标本呀同学们", "答")
    _join_title_thread(svc)
    time.sleep(0.05)
    title = svc.list_sessions()[0].title
    assert title.startswith("这是什么标本")
    assert title != "新对话"


def test_no_config_skips_title_thread(tmp_path: Path, monkeypatch) -> None:
    called = {"n": 0}

    def boom(*_a, **_k) -> str:
        called["n"] += 1
        return "不该调用"

    monkeypatch.setattr("qa.title.complete_once", boom)
    svc = QaService(
        qa_dir=tmp_path, environ={}, config=None, purge_on_start=False
    )
    svc.append_turn("这是什么标本呀同学们", "答")
    _join_title_thread(svc)
    time.sleep(0.05)
    assert called["n"] == 0
    assert svc.list_sessions()[0].title.startswith("这是什么标本")


def test_title_updates_appended_session_not_current_id(
    tmp_path: Path, monkeypatch
) -> None:
    """切场或 current_id 变化后，标题仍写回 append 时的场次。"""
    gate = threading.Event()
    released = threading.Event()

    def blocking_complete(*_a, **_k) -> str:
        gate.set()
        released.wait(timeout=2.0)
        return "历史场标题"

    monkeypatch.setattr("qa.title.complete_once", blocking_complete)
    svc = QaService(
        qa_dir=tmp_path, environ={}, config=_cfg(), purge_on_start=False
    )
    original_sid = svc.current_session_id()
    assert original_sid is not None
    svc.append_turn("第一问", "第一答")
    for _ in range(50):
        if gate.is_set():
            break
        time.sleep(0.01)
    assert gate.is_set()

    wrong_id = "00000000000000000000000000000000"

    def fake_current_id(self):  # noqa: ANN001
        return wrong_id

    monkeypatch.setattr(
        type(svc._store), "current_id", fake_current_id, raising=False
    )
    new_sid = svc.start_new_session()
    assert new_sid is not None
    assert svc.current_session_id() == wrong_id
    released.set()
    _join_title_thread(svc, timeout=2.0)

    by_id = {s.id: s for s in svc.list_sessions()}
    assert by_id[original_sid].title == "历史场标题"
    assert by_id[new_sid].title == "新对话"


def test_second_turn_does_not_retitle(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_complete(*_a, **_k) -> str:
        calls.append("x")
        return "首轮标题"

    monkeypatch.setattr("qa.title.complete_once", fake_complete)
    svc = QaService(
        qa_dir=tmp_path, environ={}, config=_cfg(), purge_on_start=False
    )
    svc.append_turn("第一问", "第一答")
    _join_title_thread(svc)
    for _ in range(50):
        if svc.list_sessions() and svc.list_sessions()[0].title == "首轮标题":
            break
        time.sleep(0.02)
    svc.append_turn("第二问", "第二答")
    _join_title_thread(svc)
    time.sleep(0.05)
    assert calls == ["x"]
    assert svc.list_sessions()[0].title == "首轮标题"


class _FakeResponse:
    """假 HTTP 响应：可读且可作上下文管理器。"""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, *args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:  # noqa: ANN002
        return False


def test_complete_once_nonstream_timeout_and_swallows_errors() -> None:
    from qa.client import complete_once

    cfg = _cfg(timeout_s=30.0)
    messages = [{"role": "user", "content": "标题"}]
    captured: dict[str, object] = {}
    body = json.dumps(
        {"choices": [{"message": {"content": "洋葱表皮"}}]},
        ensure_ascii=False,
    ).encode("utf-8")

    def fake_ok(req, timeout=None):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(body)

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_ok):
        text = complete_once(cfg, messages, timeout_s=12.0)
    assert text == "洋葱表皮"
    assert captured["timeout"] == 12.0
    assert captured["payload"]["stream"] is False

    def fake_fail(req, timeout=None):  # noqa: ANN001
        del req, timeout
        raise TimeoutError("slow")

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_fail):
        assert complete_once(cfg, messages, timeout_s=1.0) == ""
