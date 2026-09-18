"""预览底两行字幕条：切幕分页，不拦截点击。"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from system.captions import CaptionPager, two_line_max_chars

_TICK_MS = 200
_PAD_PX = 16
_CAPTION_LINES = 2


class CaptionBar(QWidget):
    """预览底部最多两行的只读字幕框。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """创建字幕条；默认关闭并隐藏。

        参数:
            parent: 通常为预览区，以便叠在底部。

        返回:
            无。

        副作用:
            安装 200 ms 切幕定时器；鼠标事件穿透到下层。
        """
        super().__init__(parent)
        self.setObjectName("captionBar")
        # QWidget 子类默认不绘 QSS background；没有这属性字幕条是透明的。
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._pager = CaptionPager()
        self._enabled = False
        self._label = QLabel(self)
        self._label.setObjectName("captionText")
        self._label.setWordWrap(True)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)
        layout.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        """打开或关闭字幕显示；关闭时立刻隐藏，不影响语音会话。

        参数:
            enabled: True 后允许 ``show_text`` 露面；False 则隐藏并停切幕。

        返回:
            无。

        副作用:
            关闭时 ``clear`` 并 ``hide``。
        """
        self._enabled = bool(enabled)
        if not self._enabled:
            self.clear()

    def show_text(self, text: str, hold_s: float | None = None) -> None:
        """用新全文替换当前幕（ASR 或后一句 TTS 顶前句）。

        参数:
            text: 识别或播报句全文；空串等价于 ``clear``。
            hold_s: TTS 句的 PCM 时长（秒）；``None`` 表示 ASR，每页 2 s。

        返回:
            无。

        副作用:
            关字幕时为空操作。开字幕则分页显示并启动切幕定时器。
        """
        if not self._enabled:
            return
        body = (text or "").strip()
        if not body:
            self.clear()
            return
        self._pager.show(body, self._max_chars(), time.monotonic(), hold_s=hold_s)
        self._sync_label()
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start()

    def clear(self) -> None:
        """立刻隐藏字幕并取消切幕。

        参数:
            无。

        返回:
            无。

        副作用:
            停定时器、清空分页、``hide``。
        """
        self._timer.stop()
        self._pager.clear()
        self._label.setText("")
        self.hide()

    def visible_text(self) -> str:
        """当前幕可见文本；无内容时为空串。

        参数:
            无。

        返回:
            :class:`CaptionPager` 的 ``visible_text``。

        副作用:
            无。
        """
        return self._pager.visible_text

    def preferred_height(self) -> int:
        """两行字高加内边距，供预览叠底定位。

        参数:
            无。

        返回:
            像素高度，至少能放下两行。

        副作用:
            无。
        """
        fm = self._label.fontMetrics()
        return fm.lineSpacing() * _CAPTION_LINES + _PAD_PX

    def _max_chars(self) -> int:
        """按当前宽度与汉字字宽估算两行容量。"""
        fm = self._label.fontMetrics()
        char_w = max(fm.horizontalAdvance("汉"), 1)
        inner = max(self._label.width(), self.width() - _PAD_PX, 0)
        return two_line_max_chars(inner, char_w)

    def _sync_label(self) -> None:
        """把当前幕写到标签。"""
        self._label.setText(self._pager.visible_text)

    def _on_tick(self) -> None:
        """定时翻页；末页保持直到 ``clear``。"""
        self._pager.tick(time.monotonic())
        self._sync_label()
