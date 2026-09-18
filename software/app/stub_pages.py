"""右栏占位页。融合 / 拼接本计划不实现向导。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.shell_state import RightPanel

_TITLES = {
    RightPanel.FUSION: "融合（下期）",
    RightPanel.STITCH: "拼接（下期）",
}


class StubPage(QWidget):
    """带关闭按钮的右栏占位页。"""

    def __init__(
        self,
        panel: RightPanel,
        on_close: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """按右栏种类显示占位标题与关闭钮。

        参数:
            panel: 融合 / 拼接之一；历史与设置页不再走本类。
            on_close: 点「关闭」时退出分屏。
            parent: 父控件。

        返回:
            无。

        副作用:
            构建占位控件；点「关闭」会调用 ``on_close``。
        """
        super().__init__(parent)
        self.setObjectName("stubPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel(_TITLES[panel])
        title.setObjectName("stubTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("ghostBtn")
        close_btn.setFixedHeight(44)
        close_btn.clicked.connect(on_close)
        header.addWidget(title, 1)
        header.addWidget(close_btn, 0)
        layout.addLayout(header)
        layout.addStretch(1)
