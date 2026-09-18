"""主界面壳层状态：与 edu-kiosk-ui-design §3–§5 一致，无 Qt。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.shell_state import (  # noqa: E402
    DRAG_THRESHOLD_PX,
    FAB_MARGIN,
    FAB_SIZE,
    FabGestureKind,
    FabPos,
    Overlay,
    RightPanel,
    SPLIT_DEFAULT,
    SPLIT_HANDLE_PX,
    ShellState,
    classify_fab_gesture,
    default_fab_pos,
)


def test_default_is_full_preview_with_strip_open() -> None:
    s = ShellState()
    assert s.strip_expanded is True
    assert s.right_panel is RightPanel.NONE
    assert s.overlay is Overlay.NONE
    assert s.split_open is False
    assert s.split_ratio == SPLIT_DEFAULT


def test_toggle_strip() -> None:
    s = ShellState()
    s.toggle_strip()
    assert s.strip_expanded is False
    s.toggle_strip()
    assert s.strip_expanded is True


def test_annotate_and_count_do_not_open_split() -> None:
    s = ShellState()
    s.open_tool("annotate")
    assert s.overlay is Overlay.ANNOTATE
    assert s.split_open is False
    s.open_tool("count")
    assert s.overlay is Overlay.COUNT
    assert s.right_panel is RightPanel.NONE


def test_annotate_closes_right_panel_from_split() -> None:
    s = ShellState()
    s.open_tool("settings")
    assert s.split_open is True
    s.open_tool("annotate")
    assert s.split_open is False
    assert s.right_panel is RightPanel.NONE
    assert s.overlay is Overlay.ANNOTATE


def test_fusion_stitch_history_settings_open_split() -> None:
    s = ShellState()
    for name, panel in (
        ("fusion", RightPanel.FUSION),
        ("stitch", RightPanel.STITCH),
        ("history", RightPanel.HISTORY),
        ("settings", RightPanel.SETTINGS),
    ):
        s.open_tool(name)
        assert s.right_panel is panel
        assert s.split_open is True
        assert s.overlay is Overlay.NONE
        assert s.strip_expanded is True
    s.close_right()
    assert s.split_open is False
    assert s.right_panel is RightPanel.NONE
    assert s.strip_expanded is True


def test_split_handle_meets_touch_minimum() -> None:
    """分界线命中宽度至少 24 px，供十寸触屏拖动。"""
    assert SPLIT_HANDLE_PX >= 24


def test_split_ratio_clamped() -> None:
    s = ShellState()
    s.set_split_ratio(0.05)
    assert s.split_ratio == pytest.approx(0.25)
    s.set_split_ratio(0.95)
    assert s.split_ratio == pytest.approx(0.75)
    s.set_split_ratio(0.4)
    assert s.split_ratio == pytest.approx(0.4)


def test_fab_size_is_easy_to_touch() -> None:
    """语音浮标加大，方便点触（对照 mipi-hmi 列表钮 96）。"""
    assert FAB_SIZE >= 96


def test_fab_clamped_inside_preview() -> None:
    pos = FabPos(x=-10, y=5000).clamped(width=1080, height=1920, size=72)
    assert 8 <= pos.x <= 1080 - 72 - 8
    assert 8 <= pos.y <= 1920 - 72 - 8


def test_default_fab_pos_lower_right_anchor() -> None:
    """无存档时浮标在预览约 80%、80%（对角线靠右下），不挡标本中心。"""
    pos = default_fab_pos(1920, 1080)
    assert pos.x == pytest.approx(1920 * 0.8 - FAB_SIZE / 2)
    assert pos.y == pytest.approx(1080 * 0.8 - FAB_SIZE / 2)


def test_place_fab_keeps_in_bounds_drag() -> None:
    """仍在预览内的拖动位置保持，不强制回锚点。"""
    from app.shell_state import place_fab

    pos = FabPos(200, 300)
    out = place_fab(pos, 1920, 1080)
    assert out.x == pytest.approx(200)
    assert out.y == pytest.approx(300)


def test_place_fab_out_of_bounds_resets_to_anchor() -> None:
    """展开工具条后预览变窄、原坐标越界时回到 80%/80%，不贴死在新右缘。"""
    from app.shell_state import place_fab

    pos = FabPos(1800, 200)
    out = place_fab(pos, 1200, 1080)
    expected = default_fab_pos(1200, 1080)
    assert out.x == pytest.approx(expected.x)
    assert out.y == pytest.approx(expected.y)


def test_fab_gesture_drag_vs_tap_vs_ptt() -> None:
    assert classify_fab_gesture(moved=DRAG_THRESHOLD_PX, held_s=0.1) is FabGestureKind.DRAG
    assert classify_fab_gesture(moved=0.0, held_s=0.1) is FabGestureKind.TAP
    assert classify_fab_gesture(moved=0.0, held_s=0.4) is FabGestureKind.PTT


def test_unknown_tool_raises() -> None:
    with pytest.raises(KeyError):
        ShellState().open_tool("wifi")
