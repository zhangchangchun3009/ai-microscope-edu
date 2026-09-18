"""物理全屏旋转宿主：立刻旋转画面，并用 map_touch 转发触点。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QCloseEvent, QColor, QMouseEvent, QResizeEvent, QTouchEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from app.theme import BG
from system.display import PHYSICAL_H, PHYSICAL_W, logical_size, map_touch, normalize_rotation


def _is_touch_event(event: QEvent) -> bool:
    """是否为触摸开始/移动/结束/取消。"""
    return event.type() in (
        QEvent.Type.TouchBegin,
        QEvent.Type.TouchUpdate,
        QEvent.Type.TouchEnd,
        QEvent.Type.TouchCancel,
    )


def _click_focus_target(start: QWidget) -> QWidget | None:
    """从 ``start`` 向上找到最近一个自身或 ``focusProxy()`` 接受 ClickFocus 的控件。

    参数:
        start: 通常是 ``childAt`` 命中的控件。``QAbstractScrollArea`` 上
            ``childAt`` 会落到内部 ``qt_scrollarea_viewport``（``NoFocus``），
            真正该抢焦点的是外层 ``QTextEdit`` 等。

    返回:
        应 ``setFocus(MouseFocusReason)`` 的控件；整条祖先链都不接受
        ClickFocus 时为 ``None``。

    副作用:
        无。
    """
    widget: QWidget | None = start
    while widget is not None:
        proxy = widget.focusProxy()
        if proxy is not None and (proxy.focusPolicy() & Qt.FocusPolicy.ClickFocus):
            return proxy
        if widget.focusPolicy() & Qt.FocusPolicy.ClickFocus:
            return widget
        widget = widget.parentWidget()
    return None


_KEYBOARD_OBJECT = "eduInputPanel"


def _is_embedded_keyboard(widget: QWidget | None) -> bool:
    """控件或其祖先是否为内嵌虚拟键盘面板。

    参数:
        widget: 命中的子控件，可为 ``None``。

    返回:
        落在 ``eduInputPanel`` 上时为 True。
    """
    cur: QWidget | None = widget
    while cur is not None:
        if cur.objectName() == _KEYBOARD_OBJECT:
            return True
        cur = cur.parentWidget()
    return False


def _embedded_keyboard_at(content: QWidget, content_pt: QPoint) -> QWidget | None:
    """若逻辑点落在可见的内嵌键盘上，返回该面板。

    参数:
        content: ``MainWindow`` 等嵌入内容。
        content_pt: 内容逻辑坐标。

    返回:
        可见且包含该点的键盘控件；否则 ``None``。
    """
    kb = content.findChild(QWidget, _KEYBOARD_OBJECT)
    if kb is None or not kb.isVisible():
        return None
    if kb.geometry().contains(content_pt):
        return kb
    return None


class RotateHost(QGraphicsView):
    """顶层全屏窗：把内容按顺时针角度旋转并铺满物理屏。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """创建空场景宿主；缺省角 90°，内容由 :meth:`set_content` 嵌入。

        参数:
            parent: 通常为 ``None``（自身即顶层全屏窗）。

        返回:
            无。

        副作用:
            关闭滚动条与边框；视口接受触摸。尚未 ``showFullScreen``。
        """
        super().__init__(parent)
        self.setObjectName("rotateHost")
        self.setWindowTitle("教学显微镜")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # 键盘交给场景焦点（嵌入 QLineEdit / 虚拟键盘）；鼠标仍由本宿主 remap，
        # 代理 NoButton 避免 linuxfb 双击。setInteractive(False) 会在到达场景前丢掉按键。
        self.setInteractive(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setBackgroundBrush(QColor(BG))
        self.setStyleSheet("QGraphicsView#rotateHost { border: none; }")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._content: QWidget | None = None
        self._proxy: QGraphicsProxyWidget | None = None
        self._rotation_deg = 90
        self._mouse_target: QWidget | None = None
        self.resize(PHYSICAL_W, PHYSICAL_H)

    @property
    def rotation_deg(self) -> int:
        """当前已成功应用的顺时针旋转角（度）。

        参数:
            无。

        返回:
            0/90/180/270；从未成功应用时为缺省 90。

        副作用:
            无。
        """
        return self._rotation_deg

    def set_content(self, widget: QWidget) -> None:
        """把内容控件嵌进场景代理，由其铺满逻辑画布。

        参数:
            widget: 通常为 ``MainWindow``；嵌入后不要再对该控件 ``showFullScreen``。

        返回:
            无。

        副作用:
            从场景移除旧代理；内容改由代理托管，尺寸随旋转调整。
        """
        if self._proxy is not None:
            self._scene.removeItem(self._proxy)
            self._proxy = None
        self._content = widget
        self._proxy = self._scene.addWidget(widget)
        # 视觉旋转交给代理；鼠标/触摸由宿主 remap，避免 linuxfb 漏点或双击。
        self._proxy.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._proxy.setAcceptTouchEvents(False)
        self._relayout()

    def apply_rotation(self, deg: int) -> None:
        """立刻把内容转到 ``deg``；非法角归一为 90；失败则保持上一成功角。

        参数:
            deg: 期望顺时针角度，会先经 :func:`normalize_rotation`。

        返回:
            无。

        副作用:
            改内容逻辑尺寸、代理旋转与 ``fitInView``。变换异常时回滚上一成功角
            （规格 §11），不把失败角当成当前方向。
        """
        target = normalize_rotation(deg)
        previous = self._rotation_deg
        try:
            self._rotation_deg = target
            self._relayout()
        except Exception:
            self._rotation_deg = previous
            try:
                self._relayout()
            except Exception:
                pass

    def apply_settings_fields(self, **fields: object) -> None:
        """设置页 yaml 已写后的副作用：含 ``rotation_deg`` 则立刻旋转。

        参数:
            **fields: 与 ``patch_edu`` 相同的顶层关键字；其它字段忽略。

        返回:
            无。

        副作用:
            仅当 ``rotation_deg`` 出现在 ``fields`` 时调用 :meth:`apply_rotation`。
        """
        if "rotation_deg" not in fields:
            return
        self.apply_rotation(fields["rotation_deg"])  # type: ignore[arg-type]

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭宿主时先关闭嵌入内容，以便 MainWindow 执行语音 abort、有界 join 与浮标落盘。

        参数:
            event: Qt 关闭事件。

        返回:
            无。

        副作用:
            对已嵌入的 ``_content`` 调用 ``close()``，再交给 ``QGraphicsView``。
        """
        content = self._content
        if content is not None:
            content.close()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """物理尺寸变化后按当前成功角重铺内容。"""
        super().resizeEvent(event)
        self._relayout()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """把物理按下坐标映射到内容逻辑坐标。"""
        if not self._dispatch_mouse(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """把物理移动坐标映射到内容逻辑坐标（沿用按下目标，便于拖滑条）。"""
        if not self._dispatch_mouse(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """把物理抬起坐标映射到内容逻辑坐标。"""
        if not self._dispatch_mouse(event):
            super().mouseReleaseEvent(event)

    def event(self, event: QEvent) -> bool:
        """拦截触摸事件并用 :func:`map_touch` 转发给内容。"""
        if _is_touch_event(event) and self._dispatch_touch(event):
            return True
        return super().event(event)

    def viewportEvent(self, event: QEvent) -> bool:
        """linuxfb 触摸常打在视口上；同样走 map_touch，避免代理漏点。"""
        if _is_touch_event(event) and self._dispatch_touch(event):
            return True
        return super().viewportEvent(event)

    def _physical_size(self) -> tuple[int, int]:
        """当前物理像素；未实现尺寸时回退 1080×1920。"""
        pw = self.width()
        ph = self.height()
        if pw <= 1 or ph <= 1:
            return PHYSICAL_W, PHYSICAL_H
        return pw, ph

    def _relayout(self) -> None:
        """按物理尺寸与当前成功角设置内容逻辑尺寸、旋转代理并铺满视口。"""
        if self._content is None or self._proxy is None:
            return
        rotation = self._rotation_deg
        pw, ph = self._physical_size()
        lw, lh = logical_size(pw, ph, rotation)
        self._content.resize(lw, lh)
        self._proxy.resize(lw, lh)
        self._proxy.setTransformOriginPoint(lw / 2.0, lh / 2.0)
        self._proxy.setRotation(float(rotation))
        bounds = self._proxy.mapRectToScene(self._proxy.boundingRect())
        self.setSceneRect(bounds)
        self.resetTransform()
        self.fitInView(bounds, Qt.AspectRatioMode.IgnoreAspectRatio)

    def _dispatch_mouse(self, event: QMouseEvent) -> bool:
        """用 map_touch 把鼠标事件交给内容上的子控件。成功派发返回 True。"""
        content = self._content
        if content is None:
            return False
        pw, ph = self._physical_size()
        lx, ly = map_touch(
            event.position().x(),
            event.position().y(),
            pw,
            ph,
            self._rotation_deg,
        )
        content_pt = QPoint(int(round(lx)), int(round(ly)))
        et = event.type()
        if et == QEvent.Type.MouseButtonPress:
            kb = _embedded_keyboard_at(content, content_pt)
            target = kb if kb is not None else content.childAt(content_pt)
            if target is None:
                if not content.rect().contains(content_pt):
                    return False
                target = content
            self._mouse_target = target
            # 点虚拟键盘时保持编辑框焦点，否则 IM 立刻收起、键盘消失。
            if not _is_embedded_keyboard(target):
                if self._proxy is not None:
                    self._proxy.setFocus()
                # sendEvent 不会走 Qt ClickFocus；鼠标仍打在 childAt 目标上（便于
                # QTextEdit 落光标），焦点则沿祖先找到真正接受 ClickFocus 的控件。
                focus_target = _click_focus_target(target)
                if focus_target is not None:
                    focus_target.setFocus(Qt.FocusReason.MouseFocusReason)
        else:
            target = self._mouse_target
            if target is None:
                target = content.childAt(content_pt) or content
            if et == QEvent.Type.MouseButtonRelease:
                self._mouse_target = None
        local = QPointF(target.mapFrom(content, content_pt))
        global_pos = QPointF(content.mapToGlobal(content_pt))
        cloned = QMouseEvent(
            et,
            local,
            global_pos,
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        QApplication.sendEvent(target, cloned)
        return True

    def _dispatch_touch(self, event: QEvent) -> bool:
        """把触摸首点转成鼠标事件再走 :meth:`_dispatch_mouse`。"""
        if self._content is None or not isinstance(event, QTouchEvent):
            return False
        points = event.points()
        if not points:
            return False
        pt = points[0]
        et = event.type()
        if et == QEvent.Type.TouchBegin:
            mouse_type = QEvent.Type.MouseButtonPress
            button = Qt.MouseButton.LeftButton
            buttons = Qt.MouseButton.LeftButton
        elif et == QEvent.Type.TouchUpdate:
            mouse_type = QEvent.Type.MouseMove
            button = Qt.MouseButton.NoButton
            buttons = Qt.MouseButton.LeftButton
        else:
            mouse_type = QEvent.Type.MouseButtonRelease
            button = Qt.MouseButton.LeftButton
            buttons = Qt.MouseButton.NoButton
        fake = QMouseEvent(
            mouse_type,
            pt.position(),
            pt.globalPosition(),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        return self._dispatch_mouse(fake)
