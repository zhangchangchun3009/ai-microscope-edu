"""会话场次与轮次的 SQLite 存储（无 Qt、无 LLM、不读 yaml）。"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from qa.title import EMPTY_SESSION_TITLE, clip_title

_META_CURRENT = "current_session_id"
_SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
class SessionRecord:
    """一场对话在历史列表中的只读快照。

    参数:
        id: 本机场次 id。
        title: 标题（空场为「新对话」）。
        created_at: 创建时间 unix 秒。
        updated_at: 最近写入时间 unix 秒。
        turn_count: 已落盘轮次数。

    返回值:
        无（数据类实例）。

    副作用:
        无。
    """

    id: str
    title: str
    created_at: float
    updated_at: float
    turn_count: int


@dataclass(frozen=True)
class TurnRecord:
    """一场内一轮 user/assistant 的只读快照。

    参数:
        id: 库内自增主键。
        session_id: 所属场次 id。
        seq: 场内从 1 递增的序号。
        user_text: 用户文本。
        assistant_text: 助手全文。
        created_at: 写入时间 unix 秒。

    返回值:
        无（数据类实例）。

    副作用:
        无。
    """

    id: int
    session_id: str
    seq: int
    user_text: str
    assistant_text: str
    created_at: float


class SessionStore:
    """本机 SQLite 场次库：当前场、轮次与按天数清理。

    参数:
        见 ``__init__``。

    返回值:
        无（对象实例）。

    副作用:
        持有一条进程内连接与锁；构造时建表并确保当前场。
    """

    def __init__(self, path: Path, *, clock: Callable[[], float] | None = None) -> None:
        """打开（或创建）会话库并建表。

        参数:
            path: SQLite 文件路径。
            clock: 可注入的 unix 秒时钟；缺省 ``time.time``。

        副作用:
            打开文件、启用 WAL / 外键、建表；必要时插入空当前场。
            打开失败时抛出 ``OSError``。
        """
        self._path = Path(path)
        self._clock = clock if clock is not None else time.time
        self._lock = threading.Lock()
        try:
            self._conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
            )
        except (OSError, sqlite3.Error) as exc:
            raise OSError(f"无法打开会话库: {self._path}") from exc
        self._conn.row_factory = sqlite3.Row
        try:
            self.ensure_schema()
            self.ensure_current()
        except sqlite3.Error as exc:
            self._conn.close()
            raise OSError(f"无法打开会话库: {self._path}") from exc

    def ensure_schema(self) -> None:
        """创建 sessions / turns / meta 表并打开 WAL 与外键。

        参数:
            无。

        返回值:
            无。

        副作用:
            写库结构；设置本连接的 ``PRAGMA``。
        """
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  id          TEXT PRIMARY KEY,
                  title       TEXT NOT NULL,
                  created_at  REAL NOT NULL,
                  updated_at  REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                  id              INTEGER PRIMARY KEY,
                  session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                  seq             INTEGER NOT NULL,
                  user_text       TEXT NOT NULL,
                  assistant_text  TEXT NOT NULL,
                  created_at      REAL NOT NULL,
                  UNIQUE(session_id, seq)
                );
                CREATE TABLE IF NOT EXISTS meta (
                  key    TEXT PRIMARY KEY,
                  value  TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def ensure_current(self) -> str:
        """保证存在当前场：meta 无 id 或行已删则插入空场。

        参数:
            无。

        返回值:
            当前场 id。

        副作用:
            可能插入 ``title=新对话`` 的空场并更新 meta。
        """
        with self._lock:
            return self._ensure_current_locked()

    def current_id(self) -> str:
        """返回当前场 id；必要时先补空场。

        参数:
            无。

        返回值:
            当前场 id。

        副作用:
            同 ``ensure_current``。
        """
        return self.ensure_current()

    def start_new_session(self) -> str:
        """切到新场；当前场零轮次则复用原 id。

        参数:
            无。

        返回值:
            切场后的当前场 id（可能与原 id 相同）。

        副作用:
            非空场时插入新空场并更新 ``meta.current_session_id``。
        """
        with self._lock:
            current = self._ensure_current_locked()
            count = self._turn_count_locked(current)
            if count == 0:
                return current
            new_id = self._insert_empty_session_locked()
            self._set_meta_locked(_META_CURRENT, new_id)
            self._conn.commit()
            return new_id

    def append_turn(self, user: str, assistant: str) -> tuple[int, str]:
        """向当前场追加一轮问答。

        参数:
            user: 本轮 user 文本。
            assistant: 本轮 assistant 全文。

        返回值:
            ``(seq, session_id)``：本场内从 1 递增的序号与写入的场次 id。

        副作用:
            插入 turns、刷新 ``updated_at``；标题仍为「新对话」时改为
            ``clip_title(user, 20)``。
        """
        with self._lock:
            sid = self._ensure_current_locked()
            now = float(self._clock())
            row = self._conn.execute(
                "SELECT MAX(seq) AS m FROM turns WHERE session_id = ?",
                (sid,),
            ).fetchone()
            seq = 1 if row["m"] is None else int(row["m"]) + 1
            self._conn.execute(
                """
                INSERT INTO turns (session_id, seq, user_text, assistant_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sid, seq, user, assistant, now),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, sid),
            )
            title_row = self._conn.execute(
                "SELECT title FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
            if title_row is not None and title_row["title"] == EMPTY_SESSION_TITLE:
                self._conn.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?",
                    (clip_title(user, 20), sid),
                )
            self._conn.commit()
            return seq, sid

    def list_sessions(self) -> list[SessionRecord]:
        """按 ``updated_at`` 降序列出会话。

        参数:
            无。

        返回值:
            ``SessionRecord`` 列表（含 ``turn_count``）。

        副作用:
            无。
        """
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id)
                         AS turn_count
                FROM sessions s
                ORDER BY s.updated_at DESC
                """
            ).fetchall()
            return [
                SessionRecord(
                    id=row["id"],
                    title=row["title"],
                    created_at=float(row["created_at"]),
                    updated_at=float(row["updated_at"]),
                    turn_count=int(row["turn_count"]),
                )
                for row in rows
            ]

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        """按 seq 升序列出一场的全部轮次。

        参数:
            session_id: 场次 id。

        返回值:
            ``TurnRecord`` 列表；场不存在则为空列表。

        副作用:
            无。
        """
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, session_id, seq, user_text, assistant_text, created_at
                FROM turns
                WHERE session_id = ?
                ORDER BY seq ASC
                """,
                (session_id,),
            ).fetchall()
            return [
                TurnRecord(
                    id=int(row["id"]),
                    session_id=row["session_id"],
                    seq=int(row["seq"]),
                    user_text=row["user_text"],
                    assistant_text=row["assistant_text"],
                    created_at=float(row["created_at"]),
                )
                for row in rows
            ]

    def update_title(self, session_id: str, title: str) -> None:
        """覆盖一场的标题。

        参数:
            session_id: 场次 id。
            title: 新标题。

        返回值:
            无。

        副作用:
            更新 ``sessions.title``；不改 ``updated_at``。
        """
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET title = ? WHERE id = ?",
                (title, session_id),
            )
            self._conn.commit()

    def hydrate_turns(
        self, session_id: str, *, limit: int
    ) -> list[tuple[str, str]]:
        """取出一场按 seq 升序的最后 ``limit`` 轮。

        参数:
            session_id: 场次 id。
            limit: 最多返回的轮数。

        返回值:
            ``(user_text, assistant_text)`` 列表，seq 从旧到新。

        副作用:
            无。
        """
        if limit <= 0:
            return []
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT user_text, assistant_text FROM (
                    SELECT seq, user_text, assistant_text
                    FROM turns
                    WHERE session_id = ?
                    ORDER BY seq DESC
                    LIMIT ?
                )
                ORDER BY seq ASC
                """,
                (session_id, limit),
            ).fetchall()
            return [(row["user_text"], row["assistant_text"]) for row in rows]

    def purge_expired(self, *, retain_days: int, now: float | None = None) -> int:
        """删除过期且非当前场的会话（CASCADE 删轮次）。

        参数:
            retain_days: 保留天数，由调用方传入；本模块不读 yaml。
            now: 可选 unix 秒；缺省用注入/系统时钟。

        返回值:
            删除的场次数。

        副作用:
            ``DELETE`` ``updated_at < now - retain_days*86400`` 且
            ``id != current`` 的 sessions。
        """
        ts = float(self._clock()) if now is None else now
        cutoff = ts - retain_days * _SECONDS_PER_DAY
        with self._lock:
            current = self._ensure_current_locked()
            cur = self._conn.execute(
                "DELETE FROM sessions WHERE updated_at < ? AND id != ?",
                (cutoff, current),
            )
            deleted = int(cur.rowcount)
            self._conn.commit()
            return deleted

    def _ensure_current_locked(self) -> str:
        """已持锁：读取或创建当前场。"""
        current = self._get_meta_locked(_META_CURRENT)
        if current:
            row = self._conn.execute(
                "SELECT id FROM sessions WHERE id = ?",
                (current,),
            ).fetchone()
            if row is not None:
                return current
        new_id = self._insert_empty_session_locked()
        self._set_meta_locked(_META_CURRENT, new_id)
        self._conn.commit()
        return new_id

    def _insert_empty_session_locked(self) -> str:
        """已持锁：插入一场标题为「新对话」的空会话。"""
        sid = uuid.uuid4().hex
        now = float(self._clock())
        self._conn.execute(
            """
            INSERT INTO sessions (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (sid, EMPTY_SESSION_TITLE, now, now),
        )
        return sid

    def _set_meta_locked(self, key: str, value: str) -> None:
        """已持锁：写入 meta 键值。"""
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )

    def _get_meta_locked(self, key: str) -> str | None:
        """已持锁：读取 meta；缺失则 ``None``。"""
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def _turn_count_locked(self, session_id: str) -> int:
        """已持锁：一场的轮次数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["n"])
