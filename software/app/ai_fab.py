"""可拖动 AI 浮标：单击无事，按住发 PTT，位移超过阈值则拖动。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from app.icons import tool_pixmap
from app.shell_state import (
    FAB_SIZE,
    PTT_HOLD_S,
    FabGestureKind,
    FabPos,
    classify_fab_gesture,
)
from app.theme import ACCENT, ACCENT_DIM, DANGER, LINE, MUTED, SURFACE


class AiFab(QPushButton):
    """叠在预览上的 AI 浮标，负责拖动和按住说话手势。"""

    ptt_changed = Signal(bool)
    moved_or_released = Signal()

    def __init__(self, parent: QWidget) -> None:
        """创建浮标并把坐标系绑定到预览父控件。"""
        super().__init__(parent)
        self.setFixedSize(int(FAB_SIZE), int(FAB_SIZE))
        self.setCheckable(False)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._press_global = QPoint()
        self._max_moved = 0.0
        self._ptt_on = False
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._start_ptt)

    def hitButton(self, _pos: QPoint) -> bool:
        """始终接收已开始手势的释放，避免拖出原区域后 Qt 丢失按压。"""
        return True

    def _ring_colors(self) -> tuple[str, str, str]:
        """返回外环填充、描边与图标色。禁用态用灰色，不走 PTT 警示色。"""
        if not self.isEnabled():
            return MUTED, LINE, MUTED
        if self._ptt_on:
            return DANGER, "#ffd0d6", "#fff6f7"
        return ACCENT_DIM, ACCENT, ACCENT

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        """画青绿圆钮；PTT 时改为警示色外环；禁用时灰色。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        d = min(self.width(), self.height()) - 4
        rect = QRectF(2, 2, d, d)
        fill, pen, icon_color = self._ring_colors()
        painter.setBrush(QColor(fill))
        painter.setPen(QPen(QColor(pen), 2.2 if self._ptt_on and self.isEnabled() else 2.0))
        painter.drawEllipse(rect)
        inner = QColor(SURFACE)
        inner.setAlpha(40)
        painter.setBrush(inner)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect.adjusted(8, 8, -8, -8))
        icon = tool_pixmap("mic", int(d * 0.46), icon_color)
        painter.drawPixmap(
            int((self.width() - icon.width()) / 2),
            int((self.height() - icon.height()) / 2),
            icon,
        )
        painter.end()

    def _start_ptt(self) -> None:
        """长按期间未发生拖动时开始 PTT，并发出状态变化。"""
        kind = classify_fab_gesture(moved=self._max_moved, held_s=PTT_HOLD_S)
        if kind is FabGestureKind.PTT and not self._ptt_on:
            self._ptt_on = True
            self.update()
            self.ptt_changed.emit(True)

    def cancel_ptt(self) -> None:
        """外部强制结束 PTT 视觉状态（用于禁用浮标前的复位）。

        返回:
            无。

        副作用:
            停掉长按计时器（避免禁用期间还触发 PTT）；若当前处于 PTT，
            清除标记、重绘并发出 ``ptt_changed(False)``。不在 PTT 时只停计时器，
            不重复发信号。Qt 不向禁用控件派发 release，因此自动收尾这类
            "手指还按着就禁用" 的路径必须显式调用本方法。
        """
        self._hold.stop()
        if not self._ptt_on:
            return
        self._ptt_on = False
        self.update()
        self.ptt_changed.emit(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """记录左键按下位置，并启动 PTT 长按计时器。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._max_moved = 0.0
            self._ptt_on = False
            self._hold.start(int(PTT_HOLD_S * 1000))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """位移达到阈值后取消 PTT，并在预览边界内拖动浮标。"""
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_global
            moved = float((delta.x() ** 2 + delta.y() ** 2) ** 0.5)
            self._max_moved = max(self._max_moved, moved)
            kind = classify_fab_gesture(moved=self._max_moved, held_s=1.0)
            if kind is FabGestureKind.DRAG:
                self._hold.stop()
                if self._ptt_on:
                    self._ptt_on = False
                    self.update()
                    self.ptt_changed.emit(False)
                parent = self.parentWidget()
                local = parent.mapFromGlobal(event.globalPosition().toPoint())
                pos = FabPos(
                    float(local.x()) - FAB_SIZE / 2,
                    float(local.y()) - FAB_SIZE / 2,
                ).clamped(parent.width(), parent.height())
                self.move(int(pos.x), int(pos.y))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """结束 PTT 并通知持久化；拖动和 PTT 抬手不会触发 clicked。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._hold.stop()
            was_ptt = self._ptt_on
            if was_ptt:
                self._ptt_on = False
                self.update()
                self.ptt_changed.emit(False)
            self.moved_or_released.emit()
            kind = classify_fab_gesture(moved=self._max_moved, held_s=0.0)
            if kind is FabGestureKind.DRAG or was_ptt:
                self.setDown(False)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def pos_state(self) -> FabPos:
        """返回浮标左上角在预览中的局部坐标。"""
        return FabPos(float(self.x()), float(self.y()))
