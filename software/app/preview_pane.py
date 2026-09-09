"""占位预览。相机接入前只显示等待文案。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.shell_state import Overlay


class PreviewPane(QWidget):
    """铺满左侧（或全屏）的预览区。"""

    resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPane")
        self._overlay = Overlay.NONE
        self._ptt_on = False
        layout = QVBoxLayout(self)
        self._label = QLabel("等待相机")
        self._label.setObjectName("previewHint")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """处理预览尺寸变化，并通知叠加控件重新约束位置。"""
        super().resizeEvent(event)
        self.resized.emit()

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
