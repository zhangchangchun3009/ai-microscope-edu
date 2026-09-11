"""教学主窗：占位预览 + 工具条 + 可拖分屏。"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
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
from voice import VoiceSession, build_audio_io

# 关窗等待语音工作线程的上限：abort() 只能停下一句，已交给 aplay 的一句仍要播完，
# 所以 join 必须有界，否则 systemd stop 会拖到 90 s 超时被 SIGKILL。
PTT_JOIN_TIMEOUT_S = 5.0


class MainWindow(QWidget):
    """全屏 kiosk 壳。"""

    # 工作线程结束 stop_ptt 后排队回主线程同步浮标，禁止跨线程改控件。
    _ptt_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("eduMain")
        self.setWindowTitle("教学显微镜")
        self._state = ShellState()
        capture, playback = build_audio_io()
        wav_path = Path(__file__).resolve().parents[1] / "var" / "voice" / "last.wav"
        self._voice = VoiceSession(capture, playback, wav_path)
        self._ptt_worker: threading.Thread | None = None
        # 复位浮标 PTT 时会发 ptt_changed(False)，用它屏蔽由此重入收尾。
        self._suppress_ptt = False
        self._ptt_finished.connect(self._apply_fab_input)
        self._voice_timer = QTimer(self)
        self._voice_timer.setInterval(200)
        self._voice_timer.timeout.connect(self._on_voice_tick)
        self._voice_timer.start()
        self._preview = PreviewPane()
        self._fab_path = Path(__file__).resolve().parents[1] / "var" / "ui" / "fab.json"
        self._fab = AiFab(self._preview)
        self._fab.ptt_changed.connect(self._preview.set_ptt_active)
        self._fab.ptt_changed.connect(self._on_ptt)
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
        """关闭窗口前中止语音计时与录音，等待工作线程，并保存浮标位置。"""
        self._voice_timer.stop()
        self._voice.abort()
        self._join_ptt_worker()
        self._save_fab()
        super().closeEvent(event)

    def _apply_fab_input(self) -> None:
        """按 ``input_enabled()`` 同步浮标。不得用 ``is_busy()``：录音中忙碌但仍需抬手。"""
        self._fab.setEnabled(self._voice.input_enabled())

    def _set_turning_ui(self, turning: bool) -> None:
        """回合进行中禁用浮标；录音与空闲保持可点以便抬手结束 PTT。"""
        self._fab.setEnabled(not turning)

    def _has_live_worker(self) -> bool:
        """当前是否已有未结束的语音工作线程。"""
        return self._ptt_worker is not None and self._ptt_worker.is_alive()

    def _join_ptt_worker(self) -> None:
        """有界等待 PTT 工作线程结束，避免关窗时 ASR / TTS 仍在跑。

        超过 ``PTT_JOIN_TIMEOUT_S`` 就放弃等待：线程是 daemon，进程退出时随之结束。
        """
        worker = self._ptt_worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=PTT_JOIN_TIMEOUT_S)
        self._ptt_worker = None

    def _on_voice_tick(self) -> None:
        """200 ms 检查超时；需收尾时走与松开相同的工作线程，避免冻 linuxfb。"""
        if self._has_live_worker() or (
            self._voice.is_busy() and not self._voice.input_enabled()
        ):
            return
        # would_auto_stop 只比时钟/字节；真正 tick/_finish_recording 必须离 GUI。
        if not self._voice.would_auto_stop():
            return
        self._spawn_ptt_worker(self._tick_worker)

    def _on_ptt(self, active: bool) -> None:
        """按住开始录音（浮标保持可点）；松开后禁用浮标并在工作线程 ``stop_ptt``。"""
        if self._suppress_ptt and not active:
            # 由 _cancel_fab_ptt 复位视觉产生的松手信号，不是真的用户抬手。
            return
        if active:
            # 回合中 is_busy 且不可点；录音中 busy 但仍要允许再次接线，由 start_ptt 自行拒绝。
            if self._has_live_worker() or not self._voice.input_enabled():
                return
            self._voice.start_ptt()
            self._apply_fab_input()
            return
        self._spawn_ptt_worker(self._stop_ptt_worker)

    def _cancel_fab_ptt(self) -> None:
        """复位浮标 PTT 视觉，并屏蔽由此发出的松手信号，避免重入收尾。"""
        self._suppress_ptt = True
        try:
            self._fab.cancel_ptt()
        finally:
            self._suppress_ptt = False

    def _spawn_ptt_worker(self, target: Callable[[], None]) -> None:
        """禁用浮标并启动语音收尾线程。松开与 300s/无数据自动停录共用。

        禁用前先 ``_cancel_fab_ptt()``：自动收尾时手指可能还按着，Qt 不会给
        禁用控件派发 release，否则浮标与预览的 PTT 高亮会一直卡在录音态。
        """
        self._cancel_fab_ptt()
        self._fab.setEnabled(False)
        if self._has_live_worker():
            return
        self._ptt_worker = threading.Thread(
            target=target,
            name="edu-ptt-stop",
            daemon=True,
        )
        self._ptt_worker.start()

    def _stop_ptt_worker(self) -> None:
        """在工作线程结束 PTT；ASR / 问答 / TTS 不得占用 GUI 线程。"""
        try:
            self._voice.stop_ptt()
        finally:
            self._ptt_finished.emit()

    def _tick_worker(self) -> None:
        """在工作线程跑自动收尾 tick；与松开路径一样不得占用 GUI。"""
        try:
            self._voice.tick()
        finally:
            self._ptt_finished.emit()

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
