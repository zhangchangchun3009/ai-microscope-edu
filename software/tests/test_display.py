"""屏幕旋转：逻辑尺寸、触摸映射与立刻旋转宿主。"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from system.display import PHYSICAL_H, PHYSICAL_W, logical_size, map_touch, normalize_rotation  # noqa: E402


def test_default_and_invalid_are_90() -> None:
    assert normalize_rotation(None) == 90
    assert normalize_rotation(45) == 90
    assert normalize_rotation(90) == 90


def test_logical_size_swaps_on_90_270() -> None:
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 0) == (1080, 1920)
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 90) == (1920, 1080)
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 180) == (1080, 1920)
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 270) == (1920, 1080)


def test_map_touch_center_90() -> None:
    lx, ly = map_touch(540, 960, 1080, 1920, 90)
    assert lx == pytest.approx(960, abs=1)
    assert ly == pytest.approx(540, abs=1)


def test_map_touch_identity_0() -> None:
    assert map_touch(10, 20, 1080, 1920, 0) == (10, 20)


def test_edu_yaml_path_is_software_var() -> None:
    from system.edu_config import edu_yaml_path

    path = edu_yaml_path()
    assert path.name == "edu.yaml"
    assert path.parent.name == "var"
    assert path.parent.parent == _SOFTWARE


def test_main_rotates_host_before_fullscreen() -> None:
    """RotateHost 先 apply_rotation 再全屏；MainWindow 自己不全屏。"""
    from app.main_window import main

    src = inspect.getsource(main)
    assert "win.showFullScreen()" not in src
    assert "host.showFullScreen()" in src
    assert src.index("host.apply_rotation") < src.index("host.showFullScreen()")
    assert "apply_virtual_keyboard_locale" in src
    assert src.index("apply_virtual_keyboard_locale") < src.index("QApplication")


def test_main_applies_fixed_path_and_yaml_volume() -> None:
    """启动时写固定通路，再按 yaml 音量写 Output；须在 load_edu 之后。"""
    from app.main_window import main

    src = inspect.getsource(main)
    assert "apply_fixed_path()" in src
    assert "apply_volume(cfg.volume_pct)" in src
    assert src.index("cfg = load_edu") < src.index("apply_fixed_path")
    assert src.index("apply_fixed_path") < src.index("apply_volume")
    assert src.index("apply_volume") < src.index("host.showFullScreen")


def test_settings_change_applies_volume() -> None:
    """音量写入 yaml 后立刻 amixer，松手即可变响度。"""
    from app.main_window import MainWindow

    src = inspect.getsource(MainWindow._on_settings_change)
    assert "apply_volume" in src


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qapp():
    """进程内唯一 QApplication（offscreen）。"""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _host_with_probe(qapp, deg: int = 90):
    """构造已设定物理尺寸并转过角的宿主与探针内容。"""
    del qapp
    from PySide6.QtWidgets import QWidget

    from app.rotate_host import RotateHost

    class Probe(QWidget):
        """记录逻辑坐标下的鼠标按下。"""

        def __init__(self) -> None:
            super().__init__()
            self.presses: list[tuple[float, float]] = []

        def mousePressEvent(self, event) -> None:  # noqa: ANN001
            pos = event.position()
            self.presses.append((pos.x(), pos.y()))

    host = RotateHost()
    probe = Probe()
    host.set_content(probe)
    host.resize(PHYSICAL_W, PHYSICAL_H)
    host.show()
    host.apply_rotation(deg)
    return host, probe


def test_content_logical_size_follows_rotation(qapp) -> None:
    host, probe = _host_with_probe(qapp, 90)
    assert (probe.width(), probe.height()) == logical_size(host.width(), host.height(), 90)
    host.apply_rotation(0)
    assert (probe.width(), probe.height()) == logical_size(host.width(), host.height(), 0)
    host.apply_rotation(270)
    assert (probe.width(), probe.height()) == logical_size(host.width(), host.height(), 270)
    host.close()


def test_invalid_rotation_becomes_90(qapp) -> None:
    host, probe = _host_with_probe(qapp, 45)
    assert host.rotation_deg == 90
    assert (probe.width(), probe.height()) == logical_size(host.width(), host.height(), 90)
    host.close()


def test_rotation_exception_keeps_last_ok_angle(qapp) -> None:
    host, probe = _host_with_probe(qapp, 180)
    assert host.rotation_deg == 180

    def boom() -> None:
        raise RuntimeError("layout fail")

    host._relayout = boom  # type: ignore[method-assign]
    host.apply_rotation(0)
    assert host.rotation_deg == 180
    assert (probe.width(), probe.height()) == logical_size(host.width(), host.height(), 180)
    host.close()


def test_map_touch_mouse_press_reaches_content(qapp) -> None:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    host, probe = _host_with_probe(qapp, 90)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(540.0, 960.0),
        QPointF(540.0, 960.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    host.mousePressEvent(event)
    assert len(probe.presses) == 1
    lx, ly = probe.presses[0]
    expect_x, expect_y = map_touch(540, 960, host.width(), host.height(), 90)
    assert lx == pytest.approx(expect_x, abs=1)
    assert ly == pytest.approx(expect_y, abs=1)
    host.close()


def test_settings_patch_rotates_when_deg_in_fields(qapp) -> None:
    host, _probe = _host_with_probe(qapp, 90)
    host.apply_settings_fields(volume_pct=10)
    assert host.rotation_deg == 90
    host.apply_settings_fields(rotation_deg=180)
    assert host.rotation_deg == 180
    host.apply_settings_fields(rotation_deg=45)
    assert host.rotation_deg == 90
    host.close()
