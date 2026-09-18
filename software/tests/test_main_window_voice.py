"""教学主窗语音接线回归测试。无 PySide6 的开发机自动跳过。"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

import app.main_window as main_window  # noqa: E402


class _VoiceSession:
    """记录主窗对语音会话的构造和调用。"""

    def __init__(self, capture: object, playback: object, wav_path: Path, **kwargs: object) -> None:
        self.args = (capture, playback, wav_path)
        self.kwargs = kwargs
        self.calls: list[str] = []
        self.stop_ident: int | None = None
        self.tick_ident: int | None = None
        self.entered_stop = threading.Event()
        self.entered_tick = threading.Event()
        self.block_stop = threading.Event()
        self.block_tick = threading.Event()
        self.block_stop.set()
        self.block_tick.set()
        self._input_enabled = True
        self._busy = False
        self._would_auto_stop = False
        self.leave_input_enabled = True
        self.announce_ident: int | None = None

    def announce_new_session(self) -> str:
        """记录切场播报；主窗必须在工作线程调用，不得在 GUI 线程 TTS。"""
        self.calls.append("announce")
        self.announce_ident = threading.get_ident()
        return "played"

    def input_enabled(self) -> bool:
        """模拟会话：仅回合中为 False。"""
        return self._input_enabled

    def is_busy(self) -> bool:
        """模拟会话：录音或回合中为 True。"""
        return self._busy

    def start_ptt(self) -> bool:
        """记录开始 PTT，并模拟进入录音（浮标仍应可松开）。"""
        self.calls.append("start")
        self._busy = True
        self._input_enabled = True
        return True

    def stop_ptt(self) -> str:
        """记录停止 PTT；可阻塞以观察禁用态，并记下调用线程。"""
        self.calls.append("stop")
        self.stop_ident = threading.get_ident()
        self._busy = True
        self._input_enabled = False
        self.entered_stop.set()
        self.block_stop.wait(timeout=5.0)
        self._busy = False
        self._input_enabled = self.leave_input_enabled
        return "ignored"

    def abort(self) -> None:
        """记录无声中止录音。"""
        self.calls.append("abort")

    def would_auto_stop(self, now: float | None = None) -> bool:
        """模拟廉价超时判定；测试可改 ``_would_auto_stop``。"""
        del now
        return self._would_auto_stop

    def tick(self) -> None:
        """记录周期检查；可阻塞以观察自动收尾工作线程。"""
        self.calls.append("tick")
        self.tick_ident = threading.get_ident()
        self._busy = True
        self._input_enabled = False
        self.entered_tick.set()
        self.block_tick.wait(timeout=5.0)
        self._busy = False
        self._input_enabled = self.leave_input_enabled


class _DummyQa:
    """避免主窗测试写真实 sqlite；提供历史页与 reload_llm 所需方法。"""

    def __init__(self) -> None:
        self.reload_calls = 0
        self.list_calls = 0
        self.current_calls = 0
        self.start_calls = 0

    def reload_llm(self) -> None:
        """记录设置页保存后的刷新。"""
        self.reload_calls += 1

    def list_sessions(self) -> list[object]:
        """空库：历史页按无法读取处理。"""
        self.list_calls += 1
        return []

    def list_turns(self, session_id: str) -> list[object]:
        """无轮次。"""
        del session_id
        return []

    def current_session_id(self) -> None:
        """无可用库。"""
        self.current_calls += 1
        return None

    def start_new_session(self) -> None:
        """历史列表点击不得走到这里；按钮走 announce。"""
        self.start_calls += 1
        return None


@pytest.fixture
def app() -> QApplication:
    """返回测试进程唯一的 QApplication。"""
    return QApplication.instance() or QApplication([])


def _make_window(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[main_window.MainWindow, object, object]:
    """构造接到假会话与假问答的主窗，并返回注入的采集/播放端口。"""
    capture = object()
    playback = object()
    monkeypatch.setattr(
        main_window,
        "build_audio_io",
        lambda: (capture, playback),
        raising=False,
    )
    monkeypatch.setattr(main_window, "VoiceSession", _VoiceSession, raising=False)
    return main_window.MainWindow(qa=_DummyQa()), capture, playback


def _wait_ptt_worker(window: main_window.MainWindow, app: QApplication) -> None:
    """等待 PTT 工作线程结束，并抽干排队到主线程的浮标同步。"""
    worker = getattr(window, "_ptt_worker", None)
    if worker is not None:
        worker.join(timeout=2.0)
    app.processEvents()


def test_main_window_wires_fab_timer_and_close_to_voice(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """浮标、200 ms 定时器和关闭事件均应驱动同一个语音会话。"""
    window, capture, playback = _make_window(monkeypatch)
    expected_wav = _SOFTWARE / "var" / "voice" / "last.wav"
    assert window._voice.args == (capture, playback, expected_wav)
    assert callable(window._voice.kwargs.get("on_asr"))
    assert callable(window._voice.kwargs.get("on_assistant_sentence"))
    assert callable(window._voice.kwargs.get("on_captions_clear"))
    assert window._preview.caption_bar().isHidden()
    assert window._voice_timer.interval() == 200
    assert window._voice_timer.isActive() is True

    gui_ident = threading.get_ident()
    window._fab.ptt_changed.emit(True)
    window._fab.ptt_changed.emit(False)
    _wait_ptt_worker(window, app)
    window._voice_timer.timeout.emit()
    window.close()
    app.processEvents()

    assert window._voice.calls == ["start", "stop", "abort"]
    assert window._voice.stop_ident is not None
    assert window._voice.stop_ident != gui_ident
    assert window._voice_timer.isActive() is False


def test_ptt_press_keeps_fab_enabled(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """录音中浮标必须保持可点，否则抬手无法结束 PTT。"""
    window, _, _ = _make_window(monkeypatch)
    window._fab.ptt_changed.emit(True)
    assert window._fab.isEnabled() is True
    assert window._voice.input_enabled() is True
    window._voice.block_stop.set()
    window._fab.ptt_changed.emit(False)
    _wait_ptt_worker(window, app)
    window.close()


def test_ptt_release_disables_fab_until_worker_finishes(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """松开后立即禁用浮标，stop_ptt 在工作线程跑完再按 input_enabled 恢复。"""
    window, _, _ = _make_window(monkeypatch)
    window._voice.block_stop.clear()
    window._fab.ptt_changed.emit(True)
    assert window._fab.isEnabled() is True

    window._fab.ptt_changed.emit(False)
    assert window._voice.entered_stop.wait(timeout=1.0) is True
    assert window._fab.isEnabled() is False
    assert window._voice.stop_ident != threading.get_ident()

    window._voice.block_stop.set()
    _wait_ptt_worker(window, app)
    assert window._fab.isEnabled() is True
    window.close()


def test_fab_stays_disabled_when_input_enabled_false_after_stop(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工作线程结束后应按 input_enabled() 同步，不得无条件 setEnabled(True)。"""
    window, _, _ = _make_window(monkeypatch)
    window._voice.leave_input_enabled = False
    window._fab.ptt_changed.emit(True)
    window._fab.ptt_changed.emit(False)
    _wait_ptt_worker(window, app)
    assert window._fab.isEnabled() is False
    window.close()


def test_voice_tick_auto_stop_runs_on_worker(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """300s/无数据自动收尾必须禁用浮标并在工作线程 tick，不得冻 GUI。"""
    window, _, _ = _make_window(monkeypatch)
    window._voice.block_tick.clear()
    window._voice._busy = True
    window._voice._input_enabled = True
    window._voice._would_auto_stop = True
    gui_ident = threading.get_ident()

    window._voice_timer.timeout.emit()
    assert window._voice.entered_tick.wait(timeout=1.0) is True
    assert window._fab.isEnabled() is False
    assert window._voice.tick_ident is not None
    assert window._voice.tick_ident != gui_ident
    assert "stop" not in window._voice.calls

    window._voice.block_tick.set()
    _wait_ptt_worker(window, app)
    assert window._fab.isEnabled() is True
    window.close()


def test_voice_tick_noop_stays_on_gui_without_worker(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """尚未超时的录音 tick 不得开工作线程，浮标保持可抬手。"""
    window, _, _ = _make_window(monkeypatch)
    window._voice._busy = True
    window._voice._input_enabled = True
    window._voice._would_auto_stop = False

    window._voice_timer.timeout.emit()
    app.processEvents()
    assert window._voice.calls == []
    assert window._ptt_worker is None or not window._ptt_worker.is_alive()
    assert window._fab.isEnabled() is True
    window.close()


def test_auto_stop_resets_fab_ptt_before_disabling(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """自动收尾禁用浮标前必须复位 PTT：Qt 不给禁用控件派发松手，红环会卡住。"""
    window, _, _ = _make_window(monkeypatch)
    window._voice.block_tick.clear()
    window._voice._busy = True
    window._voice._input_enabled = True
    window._voice._would_auto_stop = True
    seen: list[bool] = []
    window._fab.ptt_changed.connect(seen.append)
    window._fab._ptt_on = True  # 手指仍按着

    window._voice_timer.timeout.emit()
    assert window._voice.entered_tick.wait(timeout=1.0) is True
    assert window._fab._ptt_on is False
    assert seen == [False]
    # 复位发出的 ptt_changed(False) 不得再触发一次收尾。
    assert window._voice.calls == ["tick"]

    window._voice.block_tick.set()
    _wait_ptt_worker(window, app)
    window.close()


def test_close_join_is_bounded(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """关窗必须 abort 并有界 join，不能等整段回答播完。"""
    window, _, _ = _make_window(monkeypatch)
    monkeypatch.setattr(main_window, "PTT_JOIN_TIMEOUT_S", 0.05)
    window._voice.block_stop.clear()
    window._fab.ptt_changed.emit(True)
    window._fab.ptt_changed.emit(False)
    assert window._voice.entered_stop.wait(timeout=1.0) is True

    started = time.monotonic()
    window.close()
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    assert "abort" in window._voice.calls

    window._voice.block_stop.set()
    _wait_ptt_worker(window, app)


def test_set_turning_ui_disables_fab(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回合 UI 开关应禁用浮标；关闭后恢复可点。"""
    window, _, _ = _make_window(monkeypatch)
    assert window._fab.isEnabled() is True
    window._set_turning_ui(True)
    assert window._fab.isEnabled() is False
    window._set_turning_ui(False)
    assert window._fab.isEnabled() is True
    window.close()


def test_disabled_fab_uses_gray_not_ptt_colors(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """禁用态必须画灰色，即使内部仍标记 PTT 也不能用警示色。"""
    from app.theme import DANGER, MUTED

    window, _, _ = _make_window(monkeypatch)
    fab = window._fab
    fab._ptt_on = True
    window._set_turning_ui(True)
    fill, _pen, _icon = fab._ring_colors()
    assert fill == MUTED
    assert fill != DANGER
    window._set_turning_ui(False)
    fill, _pen, _icon = fab._ring_colors()
    assert fill == DANGER
    window.close()


def test_rotate_host_close_aborts_embedded_voice(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """关 RotateHost 必须传到嵌入 MainWindow.closeEvent：abort 并停语音定时器。"""
    from app.rotate_host import RotateHost

    window, _, _ = _make_window(monkeypatch)
    host = RotateHost()
    host.set_content(window)
    host.close()
    app.processEvents()

    assert "abort" in window._voice.calls
    assert window._voice_timer.isActive() is False


def test_main_window_injects_qa_and_reload_llm(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主窗应把同一 QaService 注入语音，reload_llm 不再窥探 VoiceSession._qa。"""
    window, _, _ = _make_window(monkeypatch)
    assert window._voice.kwargs.get("qa") is window._qa
    window._reload_llm()
    assert window._qa.reload_calls == 1
    window.close()


def test_open_history_reloads_and_new_session_announces_off_gui(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """打开历史会刷新列表；「新对话」在工作线程 announce，不在 GUI 线程 TTS。"""
    from PySide6.QtWidgets import QPushButton

    from app.shell_state import RightPanel

    window, _, _ = _make_window(monkeypatch)
    before = window._qa.current_calls
    window._on_tool("history")
    app.processEvents()
    assert window._state.right_panel is RightPanel.HISTORY
    assert window._qa.current_calls > before

    gui_ident = threading.get_ident()
    page = window._pages[RightPanel.HISTORY]
    buttons = [btn for btn in page.findChildren(QPushButton) if btn.text() == "新对话"]
    assert buttons
    buttons[0].click()
    _wait_ptt_worker(window, app)
    assert "announce" in window._voice.calls
    assert window._voice.announce_ident is not None
    assert window._voice.announce_ident != gui_ident
    window.close()
