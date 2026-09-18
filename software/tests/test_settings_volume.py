"""音量滑条：点槽位/非拖动要提交，松手不重复写。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.settings_page import SettingsPage  # noqa: E402
from system.edu_config import defaults  # noqa: E402


@pytest.fixture
def app() -> QApplication:
    """返回测试进程唯一的 QApplication。"""
    return QApplication.instance() or QApplication([])


def test_should_commit_volume_decision_table() -> None:
    """拖动预览不写；点槽位/松手写；已提交值跳过。"""
    from app.settings_page import should_commit_volume

    assert (
        should_commit_volume(
            slider_down=True, from_release=False, value=40, committed=73
        )
        is False
    )
    assert (
        should_commit_volume(
            slider_down=False, from_release=False, value=40, committed=73
        )
        is True
    )
    assert (
        should_commit_volume(
            slider_down=False, from_release=True, value=40, committed=73
        )
        is True
    )
    assert (
        should_commit_volume(
            slider_down=True, from_release=True, value=40, committed=73
        )
        is True
    )
    assert (
        should_commit_volume(
            slider_down=False, from_release=True, value=40, committed=40
        )
        is False
    )
    assert (
        should_commit_volume(
            slider_down=False, from_release=False, value=40, committed=40
        )
        is False
    )


def _make_page(volume_pct: int = 73) -> tuple[SettingsPage, list[dict], object]:
    """构造带记录回调的设置页。"""
    settings = defaults()
    settings.volume_pct = volume_pct
    calls: list[dict] = []
    page = SettingsPage(
        on_close=lambda: None,
        settings=settings,
        on_change=lambda **kw: calls.append(kw),
    )
    return page, calls, settings


def test_groove_set_value_commits_once(app: QApplication) -> None:
    """非拖动改值（点槽位等价于 setValue）应提交 volume_pct，松手不重复写。"""
    del app
    page, calls, settings = _make_page(73)
    page._volume.setValue(40)
    assert calls == [{"volume_pct": 40}]
    assert settings.volume_pct == 40
    assert page._volume_value.text() == "40%"
    calls.clear()
    page._volume.sliderReleased.emit()
    assert calls == []


def test_slider_released_commits_after_blocked_drag(app: QApplication) -> None:
    """拖动中未提交时，松手仍应写出。"""
    del app
    page, calls, settings = _make_page(73)
    page._volume.blockSignals(True)
    page._volume.setValue(10)
    page._volume.blockSignals(False)
    page._volume_value.setText("10%")
    page._volume.sliderReleased.emit()
    assert calls == [{"volume_pct": 10}]
    assert settings.volume_pct == 10
