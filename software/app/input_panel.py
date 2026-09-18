"""把 Qt VirtualKeyboard 的 InputPanel 嵌进主窗，随 RotateHost 一起转。"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

_LOG = logging.getLogger(__name__)
_QML = Path(__file__).resolve().with_name("input_panel.qml")
_KEYBOARD_OBJECT = "eduInputPanel"
RIGHT_SCROLL = "rightPaneScroll"
RIGHT_PAD = "rightKeyboardPad"
_SCROLL_EXTRA_PX = 16


def keyboard_panel_height(host_h: int, implicit_h: int = 0) -> int:
    """计算内嵌 InputPanel 的控件高度。

    参数:
        host_h: 主窗高度（逻辑像素）。
        implicit_h: QML InputPanel 的隐式高度；未知时为 0。

    返回:
        夹紧后的高度：优先用隐式高度，否则约半屏，且不超过 ``host_h - 80``。
    """
    cap = max(host_h - 80, 120)
    if implicit_h >= 200:
        return min(implicit_h, cap)
    fallback = max(int(host_h * 0.5), 400)
    return min(fallback, cap)


def scroll_delta_to_clear_keyboard(
    widget_bottom: int,
    visible_bottom: int,
    extra: int = _SCROLL_EXTRA_PX,
) -> int:
    """焦点底边被键盘挡住时，滚动条需要增加的像素。

    参数:
        widget_bottom: 焦点（或光标）底边在视口中的 y。
        visible_bottom: 键盘上方可见区底边 y。
        extra: 额外留白。

    返回:
        需要向下滚的像素；已露出则为 0。
    """
    if widget_bottom <= visible_bottom:
        return 0
    return widget_bottom - visible_bottom + extra


def configure_right_pane_scroll(scroll: QScrollArea) -> None:
    """右栏始终可纵向滚动：常显粗滚动条。不做内容区拖动手势。

    参数:
        scroll: ``rightPaneScroll``。

    返回:
        无。

    副作用:
        改滚动条策略；视口不抢焦点，避免点滚动条时输入框失焦。
    """
    scroll.setWidgetResizable(True)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    viewport = scroll.viewport()
    if viewport is not None:
        viewport.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    inner = scroll.widget()
    if inner is not None:
        inner.setFocusPolicy(Qt.FocusPolicy.NoFocus)


def apply_right_pane_keyboard_inset(host: QWidget, kb_h: int) -> None:
    """键盘弹出时垫高右栏，并把焦点滚到键盘上方。

    不压缩设置页控件：在内容下方加垫块，用滚动把编辑框移出遮挡。

    参数:
        host: ``MainWindow``。
        kb_h: 当前键盘高度；0 表示收起。

    返回:
        无。
    """
    scroll = host.findChild(QScrollArea, RIGHT_SCROLL)
    pad = host.findChild(QWidget, RIGHT_PAD)
    inset = max(int(kb_h), 0)
    if pad is not None:
        pad.setFixedHeight(inset)
    if scroll is None:
        return
    inner = scroll.widget()
    viewport = scroll.viewport()
    vp_h = viewport.height() if viewport is not None else 0
    if inner is not None:
        target_h = vp_h + inset if inset else 0
        inner.setMinimumHeight(target_h)
        if inset and vp_h:
            inner.resize(max(inner.width(), 1), target_h)
    if inset <= 0:
        bar = scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(0)
        return

    def _reveal() -> None:
        _scroll_focus_above_keyboard(scroll, inset)

    QTimer.singleShot(0, _reveal)


def dismiss_embedded_keyboard(host: QWidget) -> None:
    """关掉设置/历史右栏时收起键盘。

    参数:
        host: ``MainWindow``。

    返回:
        无。

    副作用:
        ``QInputMethod.hide``、隐藏 ``eduInputPanel``、垫块归零。
    """
    im = QGuiApplication.inputMethod()
    if im is not None:
        im.hide()
    panel = host.findChild(QWidget, _KEYBOARD_OBJECT)
    if panel is not None:
        panel.hide()
    apply_right_pane_keyboard_inset(host, 0)


def attach_embedded_keyboard(host: QWidget) -> QWidget | None:
    """在 ``host`` 底边叠一层 InputPanel；未启用虚拟键盘模块时返回 None。

    参数:
        host: 通常为 ``MainWindow``。键盘不进布局，用几何叠底，避开工具条宽度。

    返回:
        已创建的 ``QQuickWidget``；导入/加载失败或未设 ``QT_IM_MODULE`` 时为 ``None``。

    副作用:
        监听输入法可见性、键盘高度与宿主 resize；垫高右栏。
        面板 ``NoFocus``，避免点按键抢走编辑框焦点。
        显隐只跟 ``QInputMethod``，隐藏键才能收起，不做失焦闩锁。
    """
    if os.environ.get("QT_IM_MODULE") != "qtvirtualkeyboard":
        return None
    try:
        from PySide6.QtQuickWidgets import QQuickWidget
    except Exception:
        _LOG.exception("无法导入 QQuickWidget，内嵌虚拟键盘不可用")
        return None
    panel = QQuickWidget(host)
    panel.setObjectName(_KEYBOARD_OBJECT)
    panel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    panel.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
    # 视口跟着 InputPanel 内容变高，避免候选栏把最下一排键压扁。
    panel.setResizeMode(QQuickWidget.ResizeMode.SizeViewToRootObject)
    panel.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
    panel.setClearColor(QColor("#1c1c1c"))
    panel.setSource(QUrl.fromLocalFile(str(_QML)))
    if panel.status() == QQuickWidget.Status.Error:
        errors = "; ".join(err.toString() for err in panel.errors())
        _LOG.error("加载 InputPanel QML 失败: %s", errors)
        panel.deleteLater()
        return None
    panel.hide()

    def _sync() -> None:
        _layout_keyboard(host, panel)

    im = QGuiApplication.inputMethod()
    if im is not None:
        im.visibleChanged.connect(_sync)
    _bind_panel_height(panel, _sync)
    filt = _ResizeFilter(host, _sync)
    host.installEventFilter(filt)
    host._edu_kb_filter = filt  # noqa: SLF001 — 避免过滤器被回收
    _sync()
    return panel


def _bind_panel_height(panel: QWidget, sync: Callable[[], None]) -> None:
    """InputPanel 高度变化（候选栏）时重铺。"""
    if getattr(panel, "_edu_h_bound", False):
        return
    root = getattr(panel, "rootObject", lambda: None)()
    if root is None:
        return
    try:
        root.heightChanged.connect(sync)
    except Exception:
        return
    panel._edu_h_bound = True  # noqa: SLF001


def _input_panel_implicit_height(panel: QWidget, width: int) -> int:
    """读取 QML 根对象（InputPanel）按当前宽度算出的高度。"""
    root = getattr(panel, "rootObject", lambda: None)()
    if root is None:
        return 0
    root.setProperty("width", width)
    value = root.property("height")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _layout_keyboard(host: QWidget, panel: QWidget) -> None:
    """按输入法是否可见，把面板铺在宿主底边（不含工具条）。"""
    im = QGuiApplication.inputMethod()
    visible = bool(im is not None and im.isVisible())
    strip = host.findChild(QWidget, "toolStrip")
    strip_w = strip.width() if strip is not None else 0
    width = max(host.width() - strip_w, 1)
    if not visible or not _right_pane_open(host):
        panel.hide()
        apply_right_pane_keyboard_inset(host, 0)
        return
    _bind_panel_height(panel, lambda: _layout_keyboard(host, panel))
    implicit = _input_panel_implicit_height(panel, width)
    height = keyboard_panel_height(host.height(), implicit)
    panel.setGeometry(0, host.height() - height, width, height)
    panel.show()
    panel.raise_()
    apply_right_pane_keyboard_inset(host, height)


def _scroll_focus_above_keyboard(scroll: QScrollArea, kb_h: int) -> None:
    """若光标/焦点底边落在键盘里，把右栏滚到露出为止。"""
    fw = QApplication.focusWidget()
    if fw is None or kb_h <= 0:
        return
    vp = scroll.viewport()
    if vp is None:
        return
    cur: QWidget | None = fw
    inside = False
    while cur is not None:
        if cur is scroll:
            inside = True
            break
        cur = cur.parentWidget()
    if not inside:
        return
    cursor_rect = getattr(fw, "cursorRect", None)
    if callable(cursor_rect):
        bottom = fw.mapTo(vp, cursor_rect().bottomLeft()).y()
    else:
        bottom = fw.mapTo(vp, fw.rect().bottomLeft()).y()
    visible_bottom = vp.height() - kb_h
    delta = scroll_delta_to_clear_keyboard(bottom, visible_bottom)
    if delta:
        bar = scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.value() + delta)
    reveal = getattr(fw, "ensureCursorVisible", None)
    if callable(reveal):
        reveal()


def _right_pane_open(host: QWidget) -> bool:
    """右栏滚动区是否正在显示。"""
    scroll = host.findChild(QScrollArea, RIGHT_SCROLL)
    return bool(scroll is not None and scroll.isVisible())


class _ResizeFilter(QObject):
    """宿主尺寸变化时重铺键盘。"""

    def __init__(self, host: QWidget, sync: Callable[[], None]) -> None:
        super().__init__(host)
        self._sync = sync

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        """处理 ``Resize``；其它事件放行。"""
        del watched
        if event.type() == QEvent.Type.Resize:
            self._sync()
        return False
