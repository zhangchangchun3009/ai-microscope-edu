"""会话 SQLite 存储：空场复用、截断标题、过期清理与 hydrate。"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.store import SessionStore  # noqa: E402
from qa.title import clip_title  # noqa: E402

_DAY = 86400.0
_EMPTY_TITLE = "新对话"


def _store(tmp_path: Path, clock: dict[str, float] | None = None) -> SessionStore:
    """在临时目录打开库；可选注入可变时钟。"""
    path = tmp_path / "sessions.sqlite"
    if clock is None:
        return SessionStore(path)
    return SessionStore(path, clock=lambda: clock["t"])


def test_clip_title_unicode_and_empty() -> None:
    assert clip_title("") == _EMPTY_TITLE
    assert clip_title("   ") == _EMPTY_TITLE
    twenty_one = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸末"
    assert len(twenty_one) == 21
    assert clip_title(twenty_one, 20) == "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸"
    # 按码点切，不能按 UTF-8 字节切成半个汉字。
    assert "�" not in clip_title(twenty_one, 20)


def test_empty_db_ensure_current_and_reuse_empty_session(tmp_path: Path) -> None:
    clock = {"t": 100.0}
    store = _store(tmp_path, clock)
    sid = store.ensure_current()
    assert sid == store.current_id()
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == sid
    assert sessions[0].title == _EMPTY_TITLE
    assert sessions[0].turn_count == 0
    assert sessions[0].created_at == 100.0
    assert sessions[0].updated_at == 100.0
    assert store.start_new_session() == sid
    assert store.list_sessions()[0].id == sid


def test_append_then_start_new_keeps_old_session(tmp_path: Path) -> None:
    clock = {"t": 1.0}
    store = _store(tmp_path, clock)
    old_id = store.ensure_current()
    seq, sid_appended = store.append_turn("洋葱表皮是什么", "植物细胞外壁。")
    assert seq == 1
    assert sid_appended == old_id
    clock["t"] = 2.0
    new_id = store.start_new_session()
    assert new_id != old_id
    assert store.current_id() == new_id
    sessions = store.list_sessions()
    assert [s.id for s in sessions] == [new_id, old_id]
    assert sessions[1].turn_count == 1
    assert sessions[0].turn_count == 0
    turns = store.list_turns(old_id)
    assert len(turns) == 1
    assert turns[0].seq == 1
    assert turns[0].user_text == "洋葱表皮是什么"
    assert turns[0].assistant_text == "植物细胞外壁。"


def test_first_turn_clips_title_by_unicode_code_points(tmp_path: Path) -> None:
    store = _store(tmp_path, {"t": 1.0})
    store.ensure_current()
    assert store.list_sessions()[0].title == _EMPTY_TITLE
    long_user = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸末余"
    store.append_turn(long_user, "答")
    title = store.list_sessions()[0].title
    assert title == clip_title(long_user, 20)
    assert len(title) == 20
    store.append_turn("第二问", "第二答")
    assert store.list_sessions()[0].title == title


def test_update_title_overwrites(tmp_path: Path) -> None:
    store = _store(tmp_path, {"t": 1.0})
    sid = store.ensure_current()
    store.update_title(sid, "显微镜观察")
    assert store.list_sessions()[0].title == "显微镜观察"


def test_purge_expired_keeps_current_and_recent(tmp_path: Path) -> None:
    clock = {"t": 0.0}
    store = _store(tmp_path, clock)
    store.ensure_current()
    store.append_turn("八天前用户", "八天前助手")
    stale_id = store.current_id()
    store.start_new_session()

    clock["t"] = 5 * _DAY
    store.append_turn("三天前用户", "三天前助手")
    recent_id = store.current_id()
    store.start_new_session()

    clock["t"] = 0.0
    store.append_turn("当前场旧轮", "当前场旧答")
    current_id = store.current_id()
    assert current_id not in {stale_id, recent_id}

    clock["t"] = 8 * _DAY
    deleted = store.purge_expired(retain_days=7)
    assert deleted == 1
    ids = {s.id for s in store.list_sessions()}
    assert stale_id not in ids
    assert recent_id in ids
    assert current_id in ids
    assert store.current_id() == current_id
    assert store.list_turns(stale_id) == []


def test_hydrate_turns_returns_last_limit_in_seq_order(tmp_path: Path) -> None:
    clock = {"t": 1.0}
    store = _store(tmp_path, clock)
    store.ensure_current()
    store.append_turn("u1", "a1")
    clock["t"] = 2.0
    store.append_turn("u2", "a2")
    clock["t"] = 3.0
    store.append_turn("u3", "a3")
    sid = store.current_id()
    assert store.hydrate_turns(sid, limit=2) == [("u2", "a2"), ("u3", "a3")]
    assert store.hydrate_turns(sid, limit=10) == [("u1", "a1"), ("u2", "a2"), ("u3", "a3")]


def test_constructor_raises_oserror_when_path_unusable(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    with pytest.raises(OSError):
        SessionStore(blocked)


def test_constructor_raises_oserror_on_corrupt_db_file(tmp_path: Path) -> None:
    """损坏或非 SQLite 文件须在构造时抛 OSError，供 QaService 统一捕获。"""
    path = tmp_path / "sessions.sqlite"
    path.write_bytes(b"NOT SQLITE\x00truncated-garbage")
    with pytest.raises(OSError) as exc_info:
        SessionStore(path)
    assert not isinstance(exc_info.value, sqlite3.Error)


def test_schema_wal_and_foreign_keys(tmp_path: Path) -> None:
    store = _store(tmp_path, {"t": 1.0})
    store.ensure_current()
    path = tmp_path / "sessions.sqlite"
    conn = sqlite3.connect(path)
    try:
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(journal).lower() == "wal"
        fk = store._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"sessions", "turns", "meta"} <= names
    finally:
        conn.close()
