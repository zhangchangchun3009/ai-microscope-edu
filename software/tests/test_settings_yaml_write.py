"""设置首页 yaml 写失败：不更新内存/控件，页内报错，无模态框。"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.main_window import MainWindow  # noqa: E402
from app.settings_page import SettingsPage  # noqa: E402
from system.edu_config import defaults  # noqa: E402


@pytest.fixture
def qapp() -> QApplication:
    """进程内唯一 QApplication。"""
    return QApplication.instance() or QApplication([])


def _page(on_change, settings=None) -> SettingsPage:
    """构造带回调的设置首页。"""
    cfg = settings if settings is not None else defaults()
    return SettingsPage(on_close=lambda: None, settings=cfg, on_change=on_change)


def test_volume_oserror_rolls_back_and_shows_inline_error(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """音量写出失败时滑条回到旧值，页内提示，不走 QMessageBox.exec。"""
    del qapp
    settings = defaults()
    settings.volume_pct = 73
    execs: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda *a, **k: execs.append("exec") or 0)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: execs.append("warn"))
    page = _page(lambda **_kw: False, settings)
    page._volume.setValue(10)
    assert settings.volume_pct == 73
    assert page._volume.value() == 73
    assert page._volume_value.text() == "73%"
    assert not page._save_error.isHidden()
    assert page._save_error.text()
    assert execs == []


def test_captions_oserror_rolls_back_checkbox(
    qapp: QApplication,
) -> None:
    """字幕开关写盘失败时按钮与内存都保持关闭。"""
    del qapp
    settings = defaults()
    settings.captions_enabled = False
    page = _page(lambda **_kw: False, settings)
    page._captions.setChecked(True)
    assert settings.captions_enabled is False
    assert page._captions.isChecked() is False
    assert page._captions.text() == "关"
    assert not page._save_error.isHidden()


def test_on_settings_change_logs_not_prints() -> None:
    """写盘失败走 logging，不再 print 装成已处理。"""
    src = inspect.getsource(MainWindow._on_settings_change)
    assert "print(" not in src
    assert "_LOG" in src or "logging" in src
    assert "return False" in src
