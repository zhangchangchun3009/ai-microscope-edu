"""右栏占位页。本计划不实现向导/历史/设置表单。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.shell_state import RightPanel

_TITLES = {
    RightPanel.FUSION: "融合（下期）",
    RightPanel.STITCH: "拼接（下期）",
    RightPanel.HISTORY: "历史（下期）",
    RightPanel.SETTINGS: "设置（下期）",
}


class StubPage(QWidget):
    """带关闭按钮的右栏占位页。"""

    def __init__(
        self,
        panel: RightPanel,
        on_close: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
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
