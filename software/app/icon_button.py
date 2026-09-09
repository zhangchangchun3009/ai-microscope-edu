"""圆形触控按钮：图标在圆内，标题在圆下。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from app.icons import tool_pixmap
from app.theme import ACCENT, LINE, MUTED, SURFACE, TEXT


class CircleIconButton(QAbstractButton):
    """工具条圆形入口。直径默认 56，适合指尖。"""

    def __init__(
        self,
        icon_key: str,
        caption: str = "",
        *,
        diameter: int = 56,
        parent: QWidget | None = None,
    ) -> None:
        """创建带矢量图标的圆钮。

        参数：
            icon_key: ``app.icons`` 中的键。
            caption: 圆下方短标题；空则只画圆。
            diameter: 圆形热区直径。
            parent: 父控件。
        """
        super().__init__(parent)
        self._icon_key = icon_key
        self._caption = caption
        self._diameter = diameter
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        width = max(diameter + 8, 72 if caption else diameter + 8)
        height = diameter + (22 if caption else 8)
        self.setFixedSize(width, height)

    def set_icon_key(self, icon_key: str) -> None:
        """切换矢量图标并重绘。"""
        self._icon_key = icon_key
        self.update()

    def sizeHint(self) -> QSize:
        """返回固定触控尺寸。"""
        return self.size()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        """绘制圆形底、矢量图标和可选标题。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        d = self._diameter
        x = (self.width() - d) / 2
        y = 4
        fill = QColor(ACCENT if self.isDown() else SURFACE)
        if self.isDown():
            fill.setAlpha(80)
        painter.setBrush(fill)
        painter.setPen(QPen(QColor(ACCENT if self.isDown() else LINE), 1.4))
        painter.drawEllipse(QRectF(x, y, d, d))
        icon = tool_pixmap(self._icon_key, int(d * 0.55), ACCENT if self.isDown() else TEXT)
        ix = int(x + (d - icon.width()) / 2)
        iy = int(y + (d - icon.height()) / 2)
        painter.drawPixmap(ix, iy, icon)
        if self._caption:
            painter.setPen(QColor(MUTED if not self.isDown() else ACCENT))
            painter.drawText(
                QRectF(0, y + d + 1, self.width(), 18),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                self._caption,
            )
        painter.end()
