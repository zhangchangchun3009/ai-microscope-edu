"""教学主窗：占位预览 + 工具条 + 可拖分屏。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSplitter, QStackedWidget, QWidget

from app.ai_fab import AiFab
from app.fab_store import load_fab, save_fab
from app.platform import ensure_embedded_platform
from app.preview_pane import PreviewPane
from app.shell_state import FabPos, RightPanel, ShellState
from app.stub_pages import StubPage
from app.theme import apply_theme
from app.tool_strip import ToolStrip


class MainWindow(QWidget):
    """全屏 kiosk 壳。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("eduMain")
        self.setWindowTitle("教学显微镜")
        self._state = ShellState()
        self._preview = PreviewPane()
        self._fab_path = Path(__file__).resolve().parents[1] / "var" / "ui" / "fab.json"
        self._fab = AiFab(self._preview)
        self._fab.ptt_changed.connect(self._preview.set_ptt_active)
        self._fab.moved_or_released.connect(self._save_fab)
        self._preview.resized.connect(self._clamp_fab)
        self._right = QStackedWidget()
        self._pages = {
            RightPanel.FUSION: StubPage(RightPanel.FUSION, self._close_right),
            RightPanel.STITCH: StubPage(RightPanel.STITCH, self._close_right),
            RightPanel.HISTORY: StubPage(RightPanel.HISTORY, self._close_right),
            RightPanel.SETTINGS: StubPage(RightPanel.SETTINGS, self._close_right),
        }
        for page in self._pages.values():
            self._right.addWidget(page)
        self._right.hide()
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._preview)
        self._splitter.addWidget(self._right)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(8)
        self._splitter.splitterMoved.connect(self._on_splitter)
        self._strip = ToolStrip(self._on_tool, self._toggle_strip)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._mid = QWidget()
        mid_l = QHBoxLayout(self._mid)
        mid_l.setContentsMargins(0, 0, 0, 0)
        mid_l.setSpacing(0)
        mid_l.addWidget(self._splitter, 1)
        root.addWidget(self._mid, 1)
        root.addWidget(self._strip, 0)
        self._apply()
        QTimer.singleShot(0, self._restore_fab)

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭窗口前保存浮标位置，然后继续 Qt 默认关闭流程。"""
        self._save_fab()
        super().closeEvent(event)

    def _restore_fab(self) -> None:
        """按当前预览尺寸读取、夹紧并恢复浮标位置。"""
        pos = load_fab(
            self._fab_path,
            width=self._preview.width(),
            height=self._preview.height(),
        )
        self._state.fab = pos
        self._fab.move(int(pos.x), int(pos.y))
        self._fab.raise_()

    def _save_fab(self) -> None:
        """夹紧当前浮标位置并写入应用运行时目录。"""
        pos = self._clamp_fab()
        save_fab(self._fab_path, pos)

    def _clamp_fab(self) -> FabPos:
        """按当前预览尺寸夹紧浮标并返回坐标状态。"""
        pos = self._fab.pos_state().clamped(
            self._preview.width(),
            self._preview.height(),
        )
        self._state.fab = pos
        self._fab.move(int(pos.x), int(pos.y))
        return pos

    def _on_splitter(self, _pos: int, _index: int) -> None:
        sizes = self._splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        self._state.set_split_ratio(sizes[0] / total)

    def _on_tool(self, name: str) -> None:
        self._state.open_tool(name)
        self._apply()

    def _toggle_strip(self) -> None:
        self._state.toggle_strip()
        self._apply()

    def _close_right(self) -> None:
        self._state.close_right()
        self._apply()

    def _apply(self) -> None:
        self._strip.set_expanded(self._state.strip_expanded)
        self._preview.set_overlay(self._state.overlay)
        if self._state.split_open:
            self._right.show()
            page = self._pages[self._state.right_panel]
            self._right.setCurrentWidget(page)
            QTimer.singleShot(0, self._sync_splitter)
        else:
            self._right.hide()

    def _sync_splitter(self) -> None:
        w = max(self._splitter.width(), 1)
        left = int(w * self._state.split_ratio)
        self._splitter.setSizes([left, max(w - left, 1)])
        self._clamp_fab()


def main(argv: list[str] | None = None) -> int:
    """启动全屏教学壳，返回 Qt 事件循环退出码。"""
    ensure_embedded_platform()
    app = QApplication(argv if argv is not None else sys.argv)
    apply_theme(app)
    win = MainWindow()
    win.showFullScreen()
    return app.exec()
