"""主界面壳层纯状态（无 Qt）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SPLIT_MIN = 0.25
SPLIT_MAX = 0.75
SPLIT_DEFAULT = 0.5
FAB_MARGIN = 8.0
FAB_SIZE = 72.0
DRAG_THRESHOLD_PX = 24.0
PTT_HOLD_S = 0.35


class RightPanel(str, Enum):
    """打开后进入分屏的右栏页。"""

    NONE = "none"
    FUSION = "fusion"
    STITCH = "stitch"
    HISTORY = "history"
    SETTINGS = "settings"


class Overlay(str, Enum):
    """仍铺满预览、不打开右栏的工具。"""

    NONE = "none"
    ANNOTATE = "annotate"
    COUNT = "count"


class FabGestureKind(str, Enum):
    """浮标一次按下-抬起的判定。单击不弹窗。"""

    TAP = "tap"
    DRAG = "drag"
    PTT = "ptt"


@dataclass
class FabPos:
    """浮标左上角，预览局部坐标。"""

    x: float
    y: float

    def clamped(self, width: float, height: float, size: float = FAB_SIZE) -> FabPos:
        """把浮标限制在预览内，四周留 `FAB_MARGIN`。"""
        max_x = max(FAB_MARGIN, width - size - FAB_MARGIN)
        max_y = max(FAB_MARGIN, height - size - FAB_MARGIN)
        return FabPos(
            x=min(max(self.x, FAB_MARGIN), max_x),
            y=min(max(self.y, FAB_MARGIN), max_y),
        )


def default_fab_pos(width: float, height: float, size: float = FAB_SIZE) -> FabPos:
    """无存档时的浮标位置：贴预览右侧、垂直居中。

    按传入宽高计算，不依赖屏幕旋转设置。横屏时即右缘中点；竖屏 framebuffer
    未旋转前同样贴当前预览的右边。
    """
    return FabPos(width - size - FAB_MARGIN, (height - size) / 2).clamped(
        width, height, size
    )


def classify_fab_gesture(*, moved: float, held_s: float) -> FabGestureKind:
    """位移达到阈值算拖动；否则按时长区分单击与按住说话。"""
    if moved >= DRAG_THRESHOLD_PX:
        return FabGestureKind.DRAG
    if held_s >= PTT_HOLD_S:
        return FabGestureKind.PTT
    return FabGestureKind.TAP


_TOOL_TO_PANEL = {
    "fusion": RightPanel.FUSION,
    "stitch": RightPanel.STITCH,
    "history": RightPanel.HISTORY,
    "settings": RightPanel.SETTINGS,
}


@dataclass
class ShellState:
    """主窗交互状态。"""

    strip_expanded: bool = True
    right_panel: RightPanel = RightPanel.NONE
    overlay: Overlay = Overlay.NONE
    split_ratio: float = SPLIT_DEFAULT
    fab: FabPos = field(default_factory=lambda: FabPos(FAB_MARGIN, FAB_MARGIN))

    @property
    def split_open(self) -> bool:
        """是否处于分屏（右栏已打开）。只读，由 `right_panel` 推导。"""
        return self.right_panel is not RightPanel.NONE

    def toggle_strip(self) -> None:
        """切换右侧工具条展开/折叠。副作用：修改 `strip_expanded`。"""
        self.strip_expanded = not self.strip_expanded

    def open_tool(self, name: str) -> None:
        """工具条按钮。未知名字抛 KeyError。

        annotate/count 会关闭右栏并设 overlay；其余工具开右栏并清 overlay。
        """
        if name == "annotate":
            self.right_panel = RightPanel.NONE
            self.overlay = Overlay.ANNOTATE
            return
        if name == "count":
            self.right_panel = RightPanel.NONE
            self.overlay = Overlay.COUNT
            return
        self.right_panel = _TOOL_TO_PANEL[name]
        self.overlay = Overlay.NONE

    def close_right(self) -> None:
        """关闭右栏，退出分屏。副作用：`right_panel` 置为 NONE。"""
        self.right_panel = RightPanel.NONE

    def set_split_ratio(self, ratio: float) -> None:
        """设置分屏左右比例。副作用：钳制到 [SPLIT_MIN, SPLIT_MAX] 后写入 `split_ratio`。"""
        self.split_ratio = min(SPLIT_MAX, max(SPLIT_MIN, ratio))
