"""QaService 落盘、空闲切场、hydrate 与启动清理。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.memory import QaMemory  # noqa: E402
from qa.store import SessionStore  # noqa: E402
from qa.turn import QaService  # noqa: E402

_DAY = 86400.0


def test_append_then_list_and_idle_rotates(tmp_path: Path) -> None:
    clock = {"t": 0.0}
    yaml_path = tmp_path / "edu.yaml"
    yaml_path.write_text(
        "v: 1\nqa:\n  retain_days: 7\n  context_turns: 2\n",
        encoding="utf-8",
    )
    qa_dir = tmp_path / "qa"
    svc = QaService(
        qa_dir=qa_dir,
        environ={},
        memory=QaMemory(clock=lambda: clock["t"], max_turns=2),
        config=None,  # 无 llm 亦可落盘
        purge_on_start=False,
    )
    svc.append_turn("第一问", "第一答")
    svc.append_turn("第二问", "第二答")
    svc.append_turn("第三问", "第三答")
    users = [m["content"] for m in svc.memory.messages() if m["role"] == "user"]
    assert users == ["第二问", "第三问"]  # context_turns=2
    sessions = svc.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].turn_count == 3
    turns = svc.list_turns(sessions[0].id)
    assert [t.user_text for t in turns] == ["第一问", "第二问", "第三问"]

    clock["t"] = 20 * 60 + 1
    svc.iter_tokens("新问题")  # 无配置应空迭代，但必须已切场
    assert svc.current_session_id() != sessions[0].id
    assert svc.memory.messages() == []


def test_start_new_session_store_failure_keeps_memory(
    tmp_path: Path, monkeypatch
) -> None:
    """落盘切场失败时不丢 memory，当前场 id 不变。"""
    svc = QaService(
        qa_dir=tmp_path / "qa",
        environ={},
        config=None,
        purge_on_start=False,
    )
    svc.append_turn("问", "答")
    sid_before = svc.current_session_id()
    prior_messages = list(svc.memory.messages())

    def _raise_oserror(self: SessionStore) -> str:
        raise OSError("disk full")

    monkeypatch.setattr(SessionStore, "start_new_session", _raise_oserror)
    assert svc.start_new_session() is None
    assert svc.current_session_id() == sid_before
    assert svc.memory.messages() == prior_messages


def test_empty_start_new_session_reuses(tmp_path: Path) -> None:
    svc = QaService(
        qa_dir=tmp_path / "qa",
        environ={},
        config=None,
        purge_on_start=False,
    )
    first = svc.current_session_id()
    assert svc.start_new_session() == first
    svc.append_turn("u", "a")
    second = svc.start_new_session()
    assert second != first


def test_new_service_hydrates_memory_from_store(tmp_path: Path) -> None:
    """新进程打开同一库时，memory 只装当前场最近 context_turns 轮。"""
    qa_dir = tmp_path / "qa"
    (tmp_path / "edu.yaml").write_text(
        "v: 1\nqa:\n  retain_days: 7\n  context_turns: 2\n",
        encoding="utf-8",
    )
    svc1 = QaService(
        qa_dir=qa_dir,
        environ={},
        config=None,
        purge_on_start=False,
    )
    svc1.append_turn("u1", "a1")
    svc1.append_turn("u2", "a2")
    svc1.append_turn("u3", "a3")
    sid = svc1.current_session_id()

    svc2 = QaService(
        qa_dir=qa_dir,
        environ={},
        config=None,
        purge_on_start=False,
    )
    users = [m["content"] for m in svc2.memory.messages() if m["role"] == "user"]
    assert users == ["u2", "u3"]
    assert svc2.current_session_id() == sid


def test_unusable_store_falls_back_to_memory_only(tmp_path: Path) -> None:
    """库打不开时问答仍走内存；历史 API 为空，切场只清 memory。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    (qa_dir / "sessions.sqlite").mkdir()
    svc = QaService(
        qa_dir=qa_dir,
        environ={},
        config=None,
        purge_on_start=False,
    )
    svc.append_turn("问", "答")
    assert svc.memory.messages() == [
        {"role": "user", "content": "问"},
        {"role": "assistant", "content": "答"},
    ]
    assert svc.list_sessions() == []
    assert svc.list_turns("missing") == []
    assert svc.current_session_id() is None
    assert svc.start_new_session() is None
    assert svc.memory.messages() == []


def test_list_sessions_survives_store_oserror(tmp_path: Path, monkeypatch) -> None:
    """历史读 API 不得把 sqlite/OSError 抛到 Qt 槽。"""
    svc = QaService(
        qa_dir=tmp_path / "qa",
        environ={},
        config=None,
        purge_on_start=False,
    )
    svc.append_turn("问", "答")
    assert len(svc.list_sessions()) == 1

    def _raise(_self: SessionStore) -> list:
        raise OSError("read fail")

    monkeypatch.setattr(SessionStore, "list_sessions", _raise)
    assert svc.list_sessions() == []


def test_list_turns_survives_store_oserror(tmp_path: Path, monkeypatch) -> None:
    svc = QaService(
        qa_dir=tmp_path / "qa",
        environ={},
        config=None,
        purge_on_start=False,
    )
    svc.append_turn("问", "答")
    sid = svc.current_session_id()
    assert sid is not None
    assert len(svc.list_turns(sid)) == 1

    def _raise(_self: SessionStore, _session_id: str) -> list:
        raise OSError("read fail")

    monkeypatch.setattr(SessionStore, "list_turns", _raise)
    assert svc.list_turns(sid) == []


def test_current_session_id_survives_store_oserror(tmp_path: Path, monkeypatch) -> None:
    svc = QaService(
        qa_dir=tmp_path / "qa",
        environ={},
        config=None,
        purge_on_start=False,
    )
    svc.append_turn("问", "答")
    assert svc.current_session_id() is not None

    def _raise(_self: SessionStore) -> str:
        raise OSError("read fail")

    monkeypatch.setattr(SessionStore, "current_id", _raise)
    assert svc.current_session_id() is None


def test_purge_on_start_drops_expired_non_current(tmp_path: Path) -> None:
    """purge_on_start=True 时后台线程按 retain_days 删过期非当前场。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    (tmp_path / "edu.yaml").write_text(
        "v: 1\nqa:\n  retain_days: 7\n  context_turns: 8\n",
        encoding="utf-8",
    )
    clock = {"t": 0.0}
    store = SessionStore(qa_dir / "sessions.sqlite", clock=lambda: clock["t"])
    store.append_turn("过期问", "过期答")
    stale_id = store.current_id()
    store.start_new_session()
    clock["t"] = 8 * _DAY
    store.append_turn("当前问", "当前答")
    current_id = store.current_id()

    svc = QaService(
        qa_dir=qa_dir,
        environ={},
        config=None,
        purge_on_start=True,
    )
    thread = svc._purge_thread
    assert thread is not None
    thread.join(timeout=5)
    assert not thread.is_alive()
    ids = {s.id for s in svc.list_sessions()}
    assert stale_id not in ids
    assert current_id in ids
    assert svc.current_session_id() == current_id
