"""历史右栏：只读列表与正文，点行不切场。无 PySide6 的开发机自动跳过。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
)

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.history_page import HistoryPage  # noqa: E402
from app.theme import SETTINGS_CTRL_H  # noqa: E402
from qa.store import SessionRecord, TurnRecord  # noqa: E402


class _FakeQa:
    """内存假问答端口：两场数据，记录是否被要求切场。"""

    def __init__(
        self,
        sessions: list[SessionRecord],
        turns: dict[str, list[TurnRecord]],
        current_id: str | None,
    ) -> None:
        self.sessions = sessions
        self.turns = turns
        self._current = current_id
        self.start_calls = 0

    def list_sessions(self) -> list[SessionRecord]:
        """返回构造时注入的场次列表。"""
        return list(self.sessions)

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        """返回指定场的轮次；未知 id 为空。"""
        return list(self.turns.get(session_id, []))

    def current_session_id(self) -> str | None:
        """当前场 id；None 表示库不可用。"""
        return self._current

    def start_new_session(self) -> str | None:
        """历史页不应调用；计数用于断言点列表不切场。"""
        self.start_calls += 1
        return "should-not-happen"


def _session(
    sid: str,
    title: str,
    *,
    updated_at: float,
    turn_count: int,
) -> SessionRecord:
    """构造列表行用的场次快照。"""
    return SessionRecord(
        id=sid,
        title=title,
        created_at=1.0,
        updated_at=updated_at,
        turn_count=turn_count,
    )


def _turn(sid: str, user: str, assistant: str) -> TurnRecord:
    """构造只读正文用的一轮。"""
    return TurnRecord(
        id=1,
        session_id=sid,
        seq=1,
        user_text=user,
        assistant_text=assistant,
        created_at=1.0,
    )


def _two_session_qa() -> _FakeQa:
    """一场有问答、一场空当前场。"""
    sessions = [
        _session("old", "洋葱表皮", updated_at=2.0, turn_count=1),
        _session("cur", "新对话", updated_at=1.0, turn_count=0),
    ]
    turns = {
        "old": [_turn("old", "这是什么", "这是洋葱表皮。")],
        "cur": [],
    }
    return _FakeQa(sessions, turns, current_id="cur")


def _find_button(page: HistoryPage, text: str) -> QPushButton:
    """按按钮文案查找；找不到则失败。"""
    for btn in page.findChildren(QPushButton):
        if btn.text() == text:
            return btn
    raise AssertionError(f"没有按钮「{text}」")


def _list(page: HistoryPage) -> QListWidget:
    """历史页应只有一个会话列表。"""
    widgets = page.findChildren(QListWidget)
    assert len(widgets) == 1
    return widgets[0]


def _body(page: HistoryPage) -> QTextEdit:
    """只读正文区。"""
    widgets = page.findChildren(QTextEdit)
    assert len(widgets) == 1
    return widgets[0]


@pytest.fixture
def qapp() -> QApplication:
    """进程内唯一 QApplication。"""
    return QApplication.instance() or QApplication([])


def test_click_first_row_shows_assistant_without_starting_session(
    qapp: QApplication,
) -> None:
    """点第一行只换阅读正文，含助手句，且不调用 start_new_session。"""
    qa = _two_session_qa()
    new_calls: list[int] = []
    page = HistoryPage(
        on_close=lambda: None,
        qa=qa,
        on_new_session=lambda: new_calls.append(1),
    )
    page.show()
    qapp.processEvents()
    lst = _list(page)
    assert lst.count() == 2
    lst.setCurrentRow(0)
    qapp.processEvents()
    assert "这是洋葱表皮。" in _body(page).toPlainText()
    assert qa.start_calls == 0
    assert new_calls == []
    page.close()


def test_new_session_button_calls_callback_not_qa(
    qapp: QApplication,
) -> None:
    """「新对话」只走 on_new_session，由主窗丢到语音线程，页内不切场。"""
    qa = _two_session_qa()
    new_calls: list[int] = []
    page = HistoryPage(
        on_close=lambda: None,
        qa=qa,
        on_new_session=lambda: new_calls.append(1),
    )
    page.show()
    qapp.processEvents()
    btn = _find_button(page, "新对话")
    assert btn.height() >= SETTINGS_CTRL_H
    btn.click()
    qapp.processEvents()
    assert new_calls == [1]
    assert qa.start_calls == 0
    page.close()


def test_empty_turns_show_placeholder(qapp: QApplication) -> None:
    """空场正文为「还没有问答」，且无输入框。"""
    qa = _two_session_qa()
    page = HistoryPage(on_close=lambda: None, qa=qa, on_new_session=lambda: None)
    page.show()
    qapp.processEvents()
    lst = _list(page)
    lst.setCurrentRow(1)
    qapp.processEvents()
    assert "还没有问答" in _body(page).toPlainText()
    assert page.findChildren(QLineEdit) == []
    assert _body(page).isReadOnly()
    texts = [lst.item(i).text() for i in range(lst.count())]
    assert any("当前" in text for text in texts)
    page.close()


def test_unreadable_store_shows_hint(qapp: QApplication) -> None:
    """current_session_id 为 None 时提示无法读取。"""
    qa = _FakeQa([], {}, current_id=None)
    page = HistoryPage(on_close=lambda: None, qa=qa, on_new_session=lambda: None)
    page.show()
    qapp.processEvents()
    labels = [lab.text() for lab in page.findChildren(QLabel)]
    assert any("无法读取" in text for text in labels)
    page.close()


def test_reload_keeps_selected_id(qapp: QApplication) -> None:
    """reload(keep_selected_id=) 在该场仍存在时保持阅读选中。"""
    qa = _two_session_qa()
    page = HistoryPage(on_close=lambda: None, qa=qa, on_new_session=lambda: None)
    page.show()
    qapp.processEvents()
    page.reload(keep_selected_id="old")
    qapp.processEvents()
    lst = _list(page)
    assert lst.currentRow() == 0
    assert "这是洋葱表皮。" in _body(page).toPlainText()
    page.close()
