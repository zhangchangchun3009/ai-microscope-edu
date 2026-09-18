"""自定义问答助手子页：编辑 ``var/qa/USER.md``。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.theme import SETTINGS_CTRL_H
from qa.prompt import load_user_md, save_user_md

_DEFAULT_USER_MD = Path(__file__).resolve().parents[1] / "var" / "qa" / "USER.md"
_SAVE_FAIL = "无法写入自定义问答助手。"
_CLEAR_FAIL = "无法清空自定义问答助手。"


class PromptSettingsPage(QWidget):
    """设置栈中的 USER.md 编辑页。"""

    def __init__(
        self,
        on_back: Callable[[], None],
        path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """组装多行编辑器、保存与页内清空确认。

        参数:
            on_back: 页头「返回」，只退一层不关分屏。
            path: ``USER.md`` 路径；缺省 ``software/var/qa/USER.md``。
            parent: 父控件（通常为设置页栈）。

        返回:
            无。

        副作用:
            读入现有 ``USER.md``（缺文件则空编辑器）。清空走页内
            「确定清空 / 取消」，写失败用页内提示，不弹模态框。
        """
        super().__init__(parent)
        self.setObjectName("settingsPromptPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._path = path if path is not None else _DEFAULT_USER_MD
        self._editor = QTextEdit(self)
        self._editor.setObjectName("settingsPromptEdit")
        self._editor.setAcceptRichText(False)
        self._editor.setPlainText(load_user_md(self._path))

        self._status = QLabel(self)
        self._status.setObjectName("settingsError")
        self._status.setWordWrap(True)
        self._status.hide()

        self._confirm_hint = QLabel("确定清空自定义问答助手？下一轮问答将不再附加这段说明。")
        self._confirm_hint.setObjectName("settingsBanner")
        self._confirm_hint.setWordWrap(True)
        self._confirm_yes = QPushButton("确定清空")
        self._confirm_yes.setObjectName("settingsClearConfirm")
        self._confirm_yes.setMinimumHeight(SETTINGS_CTRL_H)
        self._confirm_yes.clicked.connect(self._on_confirm_clear)
        self._confirm_no = QPushButton("取消")
        self._confirm_no.setObjectName("settingsClearCancel")
        self._confirm_no.setMinimumHeight(SETTINGS_CTRL_H)
        self._confirm_no.clicked.connect(self._on_cancel_clear)
        self._confirm_row = QWidget(self)
        confirm_l = QHBoxLayout(self._confirm_row)
        confirm_l.setContentsMargins(0, 0, 0, 0)
        confirm_l.setSpacing(12)
        confirm_l.addWidget(self._confirm_yes, 1)
        confirm_l.addWidget(self._confirm_no, 1)
        self._confirm_row.hide()
        self._confirm_hint.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addLayout(self._header("自定义问答助手", "返回", on_back))
        layout.addWidget(self._editor, 1)
        layout.addWidget(self._status)
        layout.addWidget(self._confirm_hint)
        layout.addWidget(self._confirm_row)
        layout.addLayout(self._actions())

    def _header(
        self,
        title: str,
        action: str,
        on_action: Callable[[], None],
    ) -> QHBoxLayout:
        """页头标题与返回钮。"""
        row = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("settingsTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        btn = QPushButton(action)
        btn.setObjectName("ghostBtn")
        btn.setFixedHeight(SETTINGS_CTRL_H)
        btn.clicked.connect(on_action)
        row.addWidget(label, 1)
        row.addWidget(btn, 0)
        return row

    def _actions(self) -> QHBoxLayout:
        """保存与清空。"""
        row = QHBoxLayout()
        row.setSpacing(12)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("settingsNav")
        save_btn.setMinimumHeight(SETTINGS_CTRL_H)
        save_btn.clicked.connect(self._on_save)
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("ghostBtn")
        clear_btn.setMinimumHeight(SETTINGS_CTRL_H)
        clear_btn.clicked.connect(self._on_clear)
        row.addWidget(save_btn, 1)
        row.addWidget(clear_btn, 1)
        return row

    def _show_status(self, message: str) -> None:
        """显示页内错误，不弹模态框。"""
        self._status.setText(message)
        self._status.show()

    def _hide_confirm(self) -> None:
        """收起页内清空确认。"""
        self._confirm_row.hide()
        self._confirm_hint.hide()

    def _on_save(self) -> None:
        """把编辑器内容写入 USER.md；失败页内提示，不装成已保存。"""
        try:
            save_user_md(self._path, self._editor.toPlainText())
        except OSError:
            self._show_status(_SAVE_FAIL)
            return
        self._status.hide()
        self._status.clear()
        self._hide_confirm()

    def _on_clear(self) -> None:
        """展开页内「确定清空 / 取消」，不写盘。"""
        self._status.hide()
        self._confirm_hint.show()
        self._confirm_row.show()

    def _on_cancel_clear(self) -> None:
        """取消清空，保留编辑器与文件。"""
        self._hide_confirm()

    def _on_confirm_clear(self) -> None:
        """确认后写空文件并清空编辑器。"""
        try:
            save_user_md(self._path, "")
        except OSError:
            self._show_status(_CLEAR_FAIL)
            return
        self._editor.clear()
        self._status.hide()
        self._status.clear()
        self._hide_confirm()
