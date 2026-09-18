"""自定义问答助手页：页内确认清空，写失败不弹模态框。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.settings_prompt import PromptSettingsPage  # noqa: E402


@pytest.fixture
def qapp() -> QApplication:
    """单进程内共享 QApplication，供 QWidget 测试使用。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


def _page(path: Path) -> PromptSettingsPage:
    """构造指向临时 USER.md 的提示词页。"""
    return PromptSettingsPage(on_back=lambda: None, path=path)


def test_clear_confirm_cancel_keeps_text(tmp_path: Path, qapp: QApplication) -> None:
    """点清空后再取消：编辑器与文件原文都保留。"""
    del qapp
    original = "保留这段说明"
    path = tmp_path / "USER.md"
    path.write_text(original, encoding="utf-8")
    page = _page(path)
    page._on_clear()
    page._confirm_no.click()
    assert page._editor.toPlainText() == original
    assert path.read_text(encoding="utf-8") == original


def test_clear_confirm_writes_empty_file(tmp_path: Path, qapp: QApplication) -> None:
    """页内确定清空后写空文件并清编辑器。"""
    del qapp
    path = tmp_path / "USER.md"
    path.write_text("旧说明", encoding="utf-8")
    page = _page(path)
    page._on_clear()
    page._confirm_yes.click()
    assert page._editor.toPlainText() == ""
    assert path.read_text(encoding="utf-8") == ""


def test_save_oserror_shows_message_without_modal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qapp: QApplication,
) -> None:
    """写盘失败时页内提示，且不得 QMessageBox.exec。"""
    del qapp
    path = tmp_path / "USER.md"
    path.write_text("原文", encoding="utf-8")

    def fail_save(_path: Path, _body: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.settings_prompt.save_user_md", fail_save)
    execs: list[str] = []

    def boom_exec(*args: object, **kwargs: object) -> int:
        del args, kwargs
        execs.append("exec")
        return 0

    monkeypatch.setattr(QMessageBox, "exec", boom_exec)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: execs.append("warn"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: execs.append("ask"))

    page = _page(path)
    page._on_save()
    assert execs == []
    assert not page._status.isHidden()
    assert "无法写入" in page._status.text()
    assert page._editor.toPlainText() == "原文"


def test_on_clear_oserror_keeps_editor_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qapp: QApplication,
) -> None:
    """确定清空但写盘失败时保留编辑器原文，页内提示、无模态。"""
    del qapp
    original = "保留这段说明"
    path = tmp_path / "USER.md"
    path.write_text(original, encoding="utf-8")

    def fail_save(_path: Path, _body: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.settings_prompt.save_user_md", fail_save)
    execs: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda *a, **k: execs.append("exec") or 0)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: execs.append("warn"))

    page = _page(path)
    page._on_clear()
    page._confirm_yes.click()
    assert page._editor.toPlainText() == original
    assert path.read_text(encoding="utf-8") == original
    assert execs == []
    assert not page._status.isHidden()
    assert "无法" in page._status.text()
