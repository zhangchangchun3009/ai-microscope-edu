"""占位预览。相机接入前只显示等待文案。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.caption_bar import CaptionBar
from app.shell_state import Overlay

_CAPTION_MARGIN = 16


class PreviewPane(QWidget):
    """铺满左侧（或全屏）的预览区。"""

    resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPane")
        self._overlay = Overlay.NONE
        self._ptt_on = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("等待相机")
        self._label.setObjectName("previewHint")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        self._caption = CaptionBar(self)
        self._caption.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

    def caption_bar(self) -> CaptionBar:
        """预览底部字幕条（叠层，不拦截点击）。

        参数:
            无。

        返回:
            本预览持有的 :class:`CaptionBar`。

        副作用:
            无。
        """
        return self._caption

    def resizeEvent(self, event: QResizeEvent) -> None:
        """处理预览尺寸变化，叠底字幕条并通知浮标重新约束。"""
        super().resizeEvent(event)
        self._place_caption()
        self.resized.emit()

    def _place_caption(self) -> None:
        """把字幕条铺在预览底边，左右留边。"""
        height = self._caption.preferred_height()
        width = max(self.width() - 2 * _CAPTION_MARGIN, 1)
        y = max(self.height() - height - _CAPTION_MARGIN, 0)
        self._caption.setGeometry(_CAPTION_MARGIN, y, width, height)
        self._caption.raise_()

    def set_overlay(self, overlay: Overlay) -> None:
        """标注/计数尚未实现，只改角标提示。"""
        self._overlay = overlay
        self._refresh_label()

    def set_ptt_active(self, active: bool) -> None:
        """更新按住说话提示；只影响预览占位文案。"""
        self._ptt_on = active
        self._refresh_label()

    def _refresh_label(self) -> None:
        """按当前叠图和 PTT 状态组合预览占位文案。"""
        extra = {
            Overlay.NONE: "",
            Overlay.ANNOTATE: "（标注）",
            Overlay.COUNT: "（计数）",
        }[self._overlay]
        if self._ptt_on:
            extra += "（说话中）"
        self._label.setText("等待相机" + extra)
