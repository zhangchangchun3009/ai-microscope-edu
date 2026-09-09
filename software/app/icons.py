"""触屏工具图标：矢量绘制，避免依赖位图资源。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from app.theme import TEXT

TOOL_ICON_KEYS: frozenset[str] = frozenset(
    {
        "annotate",
        "count",
        "fusion",
        "stitch",
        "history",
        "settings",
        "chevron_left",
        "chevron_right",
        "close",
        "mic",
    }
)


def tool_pixmap(key: str, size: int, color: str = TEXT) -> QPixmap:
    """绘制指定键的正方形图标。

    参数：
        key: ``TOOL_ICON_KEYS`` 中的名称。
        size: 边长像素。
        color: 描边/填充色。

    返回：
        透明底的 ``size×size`` 位图。

    异常：
        KeyError: ``key`` 未登记。
    """
    if key not in _DRAWERS:
        raise KeyError(key)
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setWindow(0, 0, 24, 24)
    ink = QColor(color)
    pen = QPen(ink, 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _DRAWERS[key](painter, ink)
    painter.end()
    return pm


def _annotate(p: QPainter, ink: QColor) -> None:
    """方框加斜笔，表示在画面上圈选。"""
    p.drawRoundedRect(QRectF(4.5, 5.5, 13, 11), 1.6, 1.6)
    path = QPainterPath()
    path.moveTo(9, 18)
    path.lineTo(10.2, 14.2)
    path.lineTo(17.5, 6.8)
    path.lineTo(19.2, 8.4)
    path.lineTo(11.8, 15.8)
    path.closeSubpath()
    p.setBrush(ink)
    p.drawPath(path)


def _count(p: QPainter, ink: QColor) -> None:
    """三枚圆点，表示计数。"""
    p.setBrush(ink)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(8, 8), 2.3, 2.3)
    p.drawEllipse(QPointF(16, 8.5), 2.3, 2.3)
    p.drawEllipse(QPointF(11.5, 16), 2.6, 2.6)


def _fusion(p: QPainter, _ink: QColor) -> None:
    """三层错开圆角矩形，表示 Z 向叠层。"""
    p.drawRoundedRect(QRectF(5, 5, 14, 8), 1.4, 1.4)
    p.drawRoundedRect(QRectF(6.2, 8.5, 14, 8), 1.4, 1.4)
    p.drawRoundedRect(QRectF(7.4, 12, 14, 8), 1.4, 1.4)


def _stitch(p: QPainter, _ink: QColor) -> None:
    """2×2 瓦片，表示拼接。"""
    p.drawRoundedRect(QRectF(4.2, 4.2, 7, 7), 1.2, 1.2)
    p.drawRoundedRect(QRectF(12.8, 4.2, 7, 7), 1.2, 1.2)
    p.drawRoundedRect(QRectF(4.2, 12.8, 7, 7), 1.2, 1.2)
    p.drawRoundedRect(QRectF(12.8, 12.8, 7, 7), 1.2, 1.2)


def _history(p: QPainter, _ink: QColor) -> None:
    """时钟，表示历史会话。"""
    p.drawEllipse(QPointF(12, 12), 8, 8)
    p.drawLine(QPointF(12, 12), QPointF(12, 7.2))
    p.drawLine(QPointF(12, 12), QPointF(16.2, 13.5))


def _settings(p: QPainter, ink: QColor) -> None:
    """简化齿轮：外齿 + 内孔。"""
    path = QPainterPath()
    path.addEllipse(QPointF(12, 12), 7.2, 7.2)
    p.drawPath(path)
    p.setBrush(ink)
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(6):
        p.save()
        p.translate(12, 12)
        p.rotate(i * 60)
        p.drawRoundedRect(QRectF(-1.3, -9.6, 2.6, 3.4), 0.6, 0.6)
        p.restore()
    p.setBrush(QColor(0, 0, 0, 0))
    p.setPen(QPen(ink, 1.8))
    p.drawEllipse(QPointF(12, 12), 2.6, 2.6)


def _chevron_left(p: QPainter, _ink: QColor) -> None:
    """向左折起工具条。"""
    p.drawLine(QPointF(14, 6), QPointF(8, 12))
    p.drawLine(QPointF(8, 12), QPointF(14, 18))


def _chevron_right(p: QPainter, _ink: QColor) -> None:
    """向右展开工具条。"""
    p.drawLine(QPointF(10, 6), QPointF(16, 12))
    p.drawLine(QPointF(16, 12), QPointF(10, 18))


def _close(p: QPainter, _ink: QColor) -> None:
    """关闭右栏。"""
    p.drawLine(QPointF(7, 7), QPointF(17, 17))
    p.drawLine(QPointF(17, 7), QPointF(7, 17))


def _mic(p: QPainter, ink: QColor) -> None:
    """胶囊麦 + 支架，给 AI 浮标用。"""
    p.setBrush(ink)
    p.drawRoundedRect(QRectF(9, 4.2, 6, 10.5), 3, 3)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(7, 12)
    path.quadTo(7, 17.2, 12, 17.2)
    path.quadTo(17, 17.2, 17, 12)
    p.drawPath(path)
    p.drawLine(QPointF(12, 17.2), QPointF(12, 19.6))
    p.drawLine(QPointF(8.5, 19.6), QPointF(15.5, 19.6))


_DRAWERS: dict[str, Callable[[QPainter, QColor], None]] = {
    "annotate": _annotate,
    "count": _count,
    "fusion": _fusion,
    "stitch": _stitch,
    "history": _history,
    "settings": _settings,
    "chevron_left": _chevron_left,
    "chevron_right": _chevron_right,
    "close": _close,
    "mic": _mic,
}
