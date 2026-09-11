"""AI 浮标 Qt 手势回归测试。无 PySide6 的开发机自动跳过。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QSignalSpy  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.ai_fab import AiFab  # noqa: E402
from app.shell_state import DRAG_THRESHOLD_PX  # noqa: E402


class _ReleaseEvent:
    """提供拖动释放路径所需的最小鼠标事件接口。"""

    def __init__(self) -> None:
        self.accepted = False

    def button(self) -> Qt.MouseButton:
        """返回左键，模拟手指抬起。"""
        return Qt.MouseButton.LeftButton

    def accept(self) -> None:
        """记录事件已由浮标消费。"""
        self.accepted = True


@pytest.fixture
def app() -> QApplication:
    """返回测试进程唯一的 QApplication。"""
    return QApplication.instance() or QApplication([])


def test_hit_button_keeps_press_during_drag(app: QApplication) -> None:
    """手指移出浮标原区域后仍应保持按钮按下语义。"""
    fab = AiFab(QWidget())

    assert fab.hitButton(QPoint(-100, -100)) is True


def test_cancel_ptt_resets_state_and_emits_off(app: QApplication) -> None:
    """外部收尾复位 PTT：清状态并只发一次 False，重复调用不再发。"""
    parent = QWidget()  # 保留引用：父被 GC 会连带析构 C++ 子对象
    fab = AiFab(parent)
    seen: list[bool] = []
    fab.ptt_changed.connect(seen.append)
    fab._ptt_on = True

    fab.cancel_ptt()

    assert fab._ptt_on is False
    assert seen == [False]

    fab.cancel_ptt()

    assert seen == [False]


def test_drag_release_emits_persist_signal_without_click(app: QApplication) -> None:
    """拖动抬手应请求持久化，但不得发出按钮 clicked。"""
    fab = AiFab(QWidget())
    moved_or_released = QSignalSpy(fab.moved_or_released)
    clicked = QSignalSpy(fab.clicked)
    event = _ReleaseEvent()
    fab._max_moved = DRAG_THRESHOLD_PX
    fab.setDown(True)

    fab.mouseReleaseEvent(event)  # type: ignore[arg-type]

    assert moved_or_released.count() == 1
    assert clicked.count() == 0
    assert fab.isDown() is False
    assert event.accepted is True
