"""右侧工具条：展开为圆形图标入口，折叠为窄柄。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.icon_button import CircleIconButton

# 顺序与 spec §3 表格一致（AI 浮标不在此列）。
TOOLS: tuple[tuple[str, str], ...] = (
    ("annotate", "标注"),
    ("count", "计数"),
    ("fusion", "融合"),
    ("stitch", "拼接"),
    ("history", "历史"),
    ("settings", "设置"),
)
TOOL_BUTTON_DIAMETER = 72
TOOL_FOLD_DIAMETER = 48
TOOL_STRIP_EXPANDED_W = 104
TOOL_STRIP_FOLDED_W = 60


class ToolStrip(QWidget):
    """右缘工具条。"""

    def __init__(
        self,
        on_tool: Callable[[str], None],
        on_toggle: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """组装折叠柄与功能圆钮，垂直居中。

        参数:
            on_tool: 点功能钮，参数为 ``TOOLS`` 的 key。
            on_toggle: 点折叠柄。
            parent: 父控件。

        返回:
            无。

        副作用:
            构建控件树。
        """
        super().__init__(parent)
        self.setObjectName("toolStrip")
        self._on_tool = on_tool
        self._buttons: list[CircleIconButton] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._fold = CircleIconButton("chevron_right", diameter=TOOL_FOLD_DIAMETER)
        self._fold.clicked.connect(on_toggle)
        layout.addStretch(1)
        layout.addWidget(self._fold, 0, Qt.AlignmentFlag.AlignHCenter)
        for key, title in TOOLS:
            btn = CircleIconButton(key, title, diameter=TOOL_BUTTON_DIAMETER)
            btn.clicked.connect(lambda checked=False, k=key: self._on_tool(k))
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append(btn)
        layout.addStretch(1)

    def set_expanded(self, expanded: bool) -> None:
        """折叠时只留圆形折叠柄。

        参数:
            expanded: True 显示全部功能钮。

        返回:
            无。

        副作用:
            改宽度与功能钮可见性。
        """
        self._fold.set_icon_key("chevron_right" if expanded else "chevron_left")
        for btn in self._buttons:
            btn.setVisible(expanded)
        self.setFixedWidth(TOOL_STRIP_EXPANDED_W if expanded else TOOL_STRIP_FOLDED_W)
