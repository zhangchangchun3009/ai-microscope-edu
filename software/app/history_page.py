"""历史右栏：只读场次列表与正文，「新对话」交给主窗语音线程。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.theme import SETTINGS_CTRL_H
from qa.store import SessionRecord, TurnRecord


class HistoryQa(Protocol):
    """历史页只读问答接口：列场、列轮次、当前场 id。"""

    def list_sessions(self) -> list[SessionRecord]:
        """按更新时间新→旧列出场次。"""
        ...

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        """列出一场的全部轮次。"""
        ...

    def current_session_id(self) -> str | None:
        """当前可写入的场次；库不可用时为 ``None``。"""
        ...


class HistoryPage(QWidget):
    """历史分屏右栏：列表 + 只读正文 +「新对话」。"""

    def __init__(
        self,
        on_close: Callable[[], None],
        qa: HistoryQa,
        on_new_session: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """组装历史页并立刻从 ``qa`` 刷新列表。

        参数:
            on_close: 页头「关闭」时退出分屏。
            qa: 提供 ``list_sessions`` / ``list_turns`` / ``current_session_id``。
            on_new_session: 点「新对话」时由主窗丢到语音工作线程切场播报。
            parent: 父控件。

        返回:
            无。

        副作用:
            构建控件树并 ``reload()``。点列表只改阅读选中，不切场。
        """
        super().__init__(parent)
        self.setObjectName("historyPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._qa = qa
        self._on_new_session = on_new_session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addLayout(self._header(on_close))
        self._status = QLabel("")
        self._status.setObjectName("historyStatus")
        self._status.setWordWrap(True)
        self._status.hide()
        layout.addWidget(self._status)
        self._list = QListWidget(self)
        self._list.setObjectName("historyList")
        self._list.setUniformItemSizes(True)
        self._list.setWordWrap(True)
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self._body = QTextEdit(self)
        self._body.setObjectName("historyBody")
        self._body.setReadOnly(True)
        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self._list)
        split.addWidget(self._body)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setChildrenCollapsible(False)
        layout.addWidget(split, 1)
        self.reload()

    def reload(self, keep_selected_id: str | None = None) -> None:
        """从库刷新列表；点行不切场。

        参数:
            keep_selected_id: 若该场仍在列表中则保持阅读选中；否则选当前场。

        返回:
            无。

        副作用:
            重填 ``QListWidget`` 并更新正文。``current_session_id`` 为 ``None``
            时提示「无法读取」，不调用 ``start_new_session``。
        """
        current = self._qa.current_session_id()
        if current is None:
            self._status.setText("无法读取")
            self._status.show()
            self._list.blockSignals(True)
            self._list.clear()
            self._list.blockSignals(False)
            self._body.clear()
            return
        self._status.hide()
        self._status.clear()
        sessions = self._qa.list_sessions()
        ids = {sess.id for sess in sessions}
        target = keep_selected_id
        if target is None or target not in ids:
            target = current if current in ids else None
            if target is None and sessions:
                target = sessions[0].id
        self._list.blockSignals(True)
        self._list.clear()
        select_row = 0
        for index, sess in enumerate(sessions):
            label = sess.title
            if sess.id == current:
                label = f"{sess.title}  当前"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, sess.id)
            item.setSizeHint(QSize(0, SETTINGS_CTRL_H))
            self._list.addItem(item)
            if sess.id == target:
                select_row = index
        self._list.blockSignals(False)
        if sessions:
            self._list.setCurrentRow(select_row)
            self._show_turns(str(sessions[select_row].id))
        else:
            self._body.setPlainText("还没有问答")

    def selected_session_id(self) -> str | None:
        """当前阅读选中的场次 id；无选中时为 ``None``。

        参数:
            无。

        返回:
            列表当前项上的场次 id。

        副作用:
            无。
        """
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def _header(self, on_close: Callable[[], None]) -> QHBoxLayout:
        """页头：标题、「新对话」、「关闭」。"""
        row = QHBoxLayout()
        title = QLabel("历史")
        title.setObjectName("historyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        new_btn = QPushButton("新对话")
        new_btn.setObjectName("ghostBtn")
        new_btn.setFixedHeight(SETTINGS_CTRL_H)
        new_btn.clicked.connect(self._on_new_session)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("ghostBtn")
        close_btn.setFixedHeight(SETTINGS_CTRL_H)
        close_btn.clicked.connect(on_close)
        row.addWidget(title, 1)
        row.addWidget(new_btn, 0)
        row.addWidget(close_btn, 0)
        return row

    def _on_current_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        """列表选中变化只刷新正文，不切当前场。"""
        if current is None:
            return
        sid = current.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        self._show_turns(str(sid))

    def _show_turns(self, session_id: str) -> None:
        """把一场的用户/助手轮次写入只读区；空场显示占位文案。"""
        turns = self._qa.list_turns(session_id)
        if not turns:
            self._body.setPlainText("还没有问答")
            return
        chunks: list[str] = []
        for turn in turns:
            chunks.append(
                f"用户\n{turn.user_text}\n\n助手\n{turn.assistant_text}"
            )
        self._body.setPlainText("\n\n".join(chunks))
