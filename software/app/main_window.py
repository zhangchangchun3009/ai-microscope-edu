"""教学主窗：占位预览 + 工具条 + 可拖分屏。"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ai_fab import AiFab
from app.fab_store import load_fab, save_fab
from app.history_page import HistoryPage
from app.input_panel import (
    RIGHT_PAD,
    RIGHT_SCROLL,
    attach_embedded_keyboard,
    configure_right_pane_scroll,
    dismiss_embedded_keyboard,
)
from app.platform import apply_virtual_keyboard_locale, ensure_embedded_platform
from app.preview_pane import PreviewPane
from app.rotate_host import RotateHost
from app.settings_page import SettingsPage
from app.shell_state import SPLIT_HANDLE_PX, FabPos, RightPanel, ShellState, place_fab
from app.stub_pages import StubPage
from app.theme import apply_theme
from app.tool_strip import ToolStrip
from qa.turn import QaService
from system.edu_config import EduSettings, edu_yaml_path, load_edu, patch_edu
from system.mixer import apply_fixed_path, apply_volume
from voice import VoiceSession, build_audio_io

# 关窗等待语音工作线程的上限：abort() 只能停下一句，已交给 aplay 的一句仍要播完，
# 所以 join 必须有界，否则 systemd stop 会拖到 90 s 超时被 SIGKILL。
PTT_JOIN_TIMEOUT_S = 5.0
_LOG = logging.getLogger(__name__)


class MainWindow(QWidget):
    """教学壳内容：预览 + 工具条 + 可拖分屏（由 RotateHost 全屏承载）。"""

    # 工作线程结束 stop_ptt 后排队回主线程同步浮标，禁止跨线程改控件。
    _ptt_finished = Signal()
    asr_caption = Signal(str)
    assistant_caption = Signal(str, float)
    captions_clear = Signal()

    def __init__(
        self,
        *,
        edu: EduSettings | None = None,
        on_settings_patch: Callable[..., None] | None = None,
        qa: QaService | None = None,
    ) -> None:
        """组装预览、分屏右栏与工具条。

        参数:
            edu: 已加载的设置；缺省读 ``var/edu.yaml``（缺文件则用缺省值）。
            on_settings_patch: 设置页字段已写入 yaml 后的副作用钩子。
                ``rotation_deg`` 由宿主立刻旋转；``volume_pct`` 由本窗写 ALSA。
                关键字与 ``patch_edu`` 相同。
            qa: 问答服务；缺省 ``QaService()``（生产路径启动清库线程）。
                同一实例注入 ``VoiceSession`` 与历史页。

        返回:
            无。

        副作用:
            读 ``edu.yaml``（若未注入）、创建预览/设置页/历史页/工具条、
            启动语音会话与定时器；未注入 ``qa`` 时打开会话库。
        """
        super().__init__()
        self.setObjectName("eduMain")
        self.setWindowTitle("教学显微镜")
        self._edu_path = edu_yaml_path()
        self._edu = edu if edu is not None else load_edu(self._edu_path)
        self._on_settings_patch = on_settings_patch
        self._state = ShellState()
        self._qa = qa if qa is not None else QaService()
        capture, playback = build_audio_io()
        wav_path = Path(__file__).resolve().parents[1] / "var" / "voice" / "last.wav"
        self._voice = VoiceSession(
            capture,
            playback,
            wav_path,
            qa=self._qa,
            on_asr=self.asr_caption.emit,
            on_assistant_sentence=self._emit_assistant_caption,
            on_captions_clear=self.captions_clear.emit,
        )
        self._ptt_worker: threading.Thread | None = None
        # 复位浮标 PTT 时会发 ptt_changed(False)，用它屏蔽由此重入收尾。
        self._suppress_ptt = False
        self._ptt_finished.connect(self._on_ptt_finished)
        self._voice_timer = QTimer(self)
        self._voice_timer.setInterval(200)
        self._voice_timer.timeout.connect(self._on_voice_tick)
        self._voice_timer.start()
        self._preview = PreviewPane()
        self._preview.caption_bar().set_enabled(self._edu.captions_enabled)
        queued = Qt.ConnectionType.QueuedConnection
        self.asr_caption.connect(self._preview.caption_bar().show_text, queued)
        self.assistant_caption.connect(self._on_assistant_caption, queued)
        self.captions_clear.connect(self._preview.caption_bar().clear, queued)
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
            RightPanel.HISTORY: HistoryPage(
                self._close_right,
                self._qa,
                self._on_history_new_session,
            ),
            RightPanel.SETTINGS: SettingsPage(
                self._close_right,
                self._edu,
                self._on_settings_change,
                user_md_path=Path(__file__).resolve().parents[1] / "var" / "qa" / "USER.md",
                edu_path=self._edu_path,
                reload_llm=self._reload_llm,
            ),
        }
        for page in self._pages.values():
            self._right.addWidget(page)
        self._right_inner = QWidget()
        self._right_inner.setObjectName("rightPaneInner")
        right_col = QVBoxLayout(self._right_inner)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)
        right_col.addWidget(self._right, 1)
        self._right_pad = QWidget()
        self._right_pad.setObjectName(RIGHT_PAD)
        self._right_pad.setFixedHeight(0)
        right_col.addWidget(self._right_pad, 0)
        self._right_scroll = QScrollArea()
        self._right_scroll.setObjectName(RIGHT_SCROLL)
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._right_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._right_scroll.setWidget(self._right_inner)
        configure_right_pane_scroll(self._right_scroll)
        self._right_scroll.hide()
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._preview)
        self._splitter.addWidget(self._right_scroll)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(SPLIT_HANDLE_PX)
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
        self._kb = attach_embedded_keyboard(self)
        self._apply()
        QTimer.singleShot(0, self._restore_fab)

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭窗口前中止语音计时与录音，等待工作线程，并保存浮标位置。"""
        self._voice_timer.stop()
        self._voice.abort()
        self._join_ptt_worker()
        self._save_fab()
        super().closeEvent(event)

    def _emit_assistant_caption(self, text: str, duration_s: float = 0.0) -> None:
        """语音线程排队：一句开口时带上 PCM 时长。"""
        self.assistant_caption.emit(text, float(duration_s))

    def _on_assistant_caption(self, text: str, duration_s: float = 0.0) -> None:
        """GUI：用该句时长均分切幕。"""
        hold = duration_s if duration_s > 0 else None
        self._preview.caption_bar().show_text(text, hold_s=hold)

    def _apply_fab_input(self) -> None:
        """按 ``input_enabled()`` 同步浮标。不得用 ``is_busy()``：录音中忙碌但仍需抬手。"""
        self._fab.setEnabled(self._voice.input_enabled())

    def _on_ptt_finished(self) -> None:
        """工作线程结束后同步浮标；若右栏是历史则刷新列表并尽量保持选中。"""
        self._apply_fab_input()
        self._reload_history_if_open()

    def _reload_history_if_open(self) -> None:
        """历史页开着时从库刷新；阅读选中 id 仍在则保留。"""
        if self._state.right_panel is not RightPanel.HISTORY:
            return
        page = self._pages[RightPanel.HISTORY]
        keep = page.selected_session_id()
        page.reload(keep_selected_id=keep)

    def _on_history_new_session(self) -> None:
        """历史页「新对话」：丢到语音工作线程播报，禁止在 GUI 线程 TTS。"""
        if self._has_live_worker() or self._voice.is_busy():
            return
        self._spawn_ptt_worker(self._announce_new_session_worker)

    def _announce_new_session_worker(self) -> None:
        """在工作线程调用 ``announce_new_session``，结束后续 ``_ptt_finished``。"""
        try:
            self._voice.announce_new_session()
        finally:
            self._ptt_finished.emit()

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
        """按当前预览放置浮标：仍在界内保持，越界则回到 80%/80%。"""
        pos = place_fab(
            self._fab.pos_state(),
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
        if self._state.right_panel is RightPanel.HISTORY:
            self._pages[RightPanel.HISTORY].reload()

    def _toggle_strip(self) -> None:
        self._state.toggle_strip()
        self._apply()

    def _close_right(self) -> None:
        self._state.close_right()
        self._apply()

    def _on_settings_change(self, **fields: object) -> bool:
        """把设置页改动写入 yaml；立刻旋转等副作用由 ``on_settings_patch`` 处理。

        参数:
            **fields: ``rotation_deg`` / ``captions_enabled`` / ``volume_pct`` 等
                已由设置页改过的顶层字段。

        返回:
            写盘成功为 True；``OSError`` 为 False（内存设置保持原值）。

        副作用:
            先 :func:`patch_edu`；成功后才改内存设置、写混音器音量，再调
            注入的 ``on_settings_patch``。写盘失败记日志并返回 False，
            由设置页回滚控件，不假装已保存。
        """
        try:
            patched = patch_edu(self._edu_path, **fields)
        except OSError:
            _LOG.exception("edu.yaml 写入失败")
            return False
        self._edu.v = patched.v
        self._edu.rotation_deg = patched.rotation_deg
        self._edu.captions_enabled = patched.captions_enabled
        self._edu.volume_pct = patched.volume_pct
        self._edu.llm = patched.llm
        if "captions_enabled" in fields:
            self._preview.caption_bar().set_enabled(bool(self._edu.captions_enabled))
        if "volume_pct" in fields:
            apply_volume(int(self._edu.volume_pct))
        if self._on_settings_patch is not None:
            self._on_settings_patch(**fields)
        return True

    def _reload_llm(self) -> None:
        """保存 LLM 段后刷新本窗持有的问答端口；尚未首轮则下一轮读盘。

        参数:
            无。

        返回:
            无。

        副作用:
            调用 ``QaService.reload_llm()``；进行中的回合使用配置快照，
            不会被打断。
        """
        self._qa.reload_llm()

    def _apply(self) -> None:
        """按状态刷新工具条、预览叠层与右栏；工具条始终显示，只改展开/折叠。"""
        self._strip.set_expanded(self._state.strip_expanded)
        self._preview.set_overlay(self._state.overlay)
        if self._state.split_open:
            self._right_scroll.show()
            page = self._pages[self._state.right_panel]
            self._right.setCurrentWidget(page)
            QTimer.singleShot(0, self._sync_splitter)
        else:
            self._right_scroll.hide()
            dismiss_embedded_keyboard(self)

    def _sync_splitter(self) -> None:
        w = max(self._splitter.width(), 1)
        left = int(w * self._state.split_ratio)
        self._splitter.setSizes([left, max(w - left, 1)])
        self._clamp_fab()


def main(argv: list[str] | None = None) -> int:
    """启动全屏教学壳（RotateHost 承载），返回事件循环退出码。

    参数:
        argv: 命令行参数；缺省为进程 argv。

    返回:
        事件循环退出码。

    副作用:
        写固定混音器通路与 yaml 音量（缺 amixer 时吞 OSError）；
        先旋转再全屏，避免 0° 闪帧。
    """
    ensure_embedded_platform()
    apply_virtual_keyboard_locale()
    app = QApplication(argv if argv is not None else sys.argv)
    apply_theme(app)
    cfg = load_edu(edu_yaml_path())
    apply_fixed_path()
    apply_volume(cfg.volume_pct)
    host = RotateHost()
    win = MainWindow(edu=cfg, on_settings_patch=host.apply_settings_fields)
    host.set_content(win)
    host.apply_rotation(cfg.rotation_deg)  # 先转再全屏，避免 0° 闪帧
    host.showFullScreen()
    return app.exec()
