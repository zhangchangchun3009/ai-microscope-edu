"""RotateHost 点击嵌入输入框后应能收到键盘（C1）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QInputMethodEvent, QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QWidget,
)

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.rotate_host import RotateHost  # noqa: E402
from system.display import map_touch  # noqa: E402


@pytest.fixture
def qapp() -> QApplication:
    """进程内唯一 QApplication（offscreen）。"""
    return QApplication.instance() or QApplication([])


def test_click_line_edit_then_host_key_reaches_text(qapp: QApplication) -> None:
    """点击映射后的输入框坐标后，宿主按键应写入该框。"""
    del qapp
    host = RotateHost()
    content = QWidget()
    edit = QLineEdit(content)
    edit.setGeometry(10, 10, 220, 48)
    host.set_content(content)
    host.resize(400, 300)
    host.show()
    host.apply_rotation(0)
    QApplication.processEvents()

    click_x, click_y = 50.0, 30.0
    mapped = map_touch(click_x, click_y, host.width(), host.height(), 0)
    assert mapped[0] == pytest.approx(click_x, abs=1)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(click_x, click_y),
        QPointF(click_x, click_y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    host.mousePressEvent(event)
    QApplication.processEvents()
    assert edit.hasFocus()

    key = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.NoModifier,
        "a",
    )
    QApplication.sendEvent(host, key)
    QApplication.processEvents()
    assert edit.text() == "a"
    host.close()


def _press_at_content_point(host: RotateHost, x: float, y: float) -> None:
    """向宿主发送一次映射后的左键按下（旋转 0° 时物理点即逻辑点）。"""
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    host.mousePressEvent(event)
    QApplication.processEvents()


def test_click_text_edit_in_scroll_area_then_key_and_ime(
    qapp: QApplication,
) -> None:
    """QScrollArea 内的 QTextEdit：点击中心后应抢到焦点、收下按键与 IME 提交。"""
    del qapp
    host = RotateHost()
    content = QWidget()
    scroll = QScrollArea(content)
    scroll.setGeometry(10, 10, 260, 160)
    scroll.setWidgetResizable(True)
    editor = QTextEdit()
    editor.setAcceptRichText(False)
    scroll.setWidget(editor)
    host.set_content(content)
    host.resize(400, 300)
    host.show()
    host.apply_rotation(0)
    QApplication.processEvents()

    center = editor.mapTo(content, editor.rect().center())
    click_x, click_y = float(center.x()), float(center.y())
    mapped = map_touch(click_x, click_y, host.width(), host.height(), 0)
    assert mapped[0] == pytest.approx(click_x, abs=1)
    _press_at_content_point(host, click_x, click_y)
    assert editor.hasFocus()

    key = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.NoModifier,
        "a",
    )
    QApplication.sendEvent(host, key)
    QApplication.processEvents()
    assert editor.toPlainText() == "a"

    ime = QInputMethodEvent("", [])
    ime.setCommitString("你")
    QApplication.sendEvent(editor, ime)
    QApplication.processEvents()
    assert editor.toPlainText() == "a你"
    host.close()


def test_click_embedded_keyboard_keeps_line_edit_focus(qapp: QApplication) -> None:
    """点到底部 ``eduInputPanel`` 不得抢走输入框焦点（否则 IM 收起、键盘消失）。"""
    del qapp
    host = RotateHost()
    content = QWidget()
    content.resize(400, 300)
    edit = QLineEdit(content)
    edit.setGeometry(10, 10, 220, 48)
    panel = QWidget(content)
    panel.setObjectName("eduInputPanel")
    # QQuickWidget 默认会抢 ClickFocus；即使如此也不得让输入框失焦。
    panel.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    panel.setGeometry(0, 180, 400, 120)
    host.set_content(content)
    host.resize(400, 300)
    host.show()
    host.apply_rotation(0)
    QApplication.processEvents()
    edit.setFocus(Qt.FocusReason.MouseFocusReason)
    QApplication.processEvents()
    assert edit.hasFocus()

    _press_at_content_point(host, 50.0, 220.0)
    QApplication.processEvents()
    assert edit.hasFocus()
    host.close()
