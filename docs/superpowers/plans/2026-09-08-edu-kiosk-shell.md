# 教学 kiosk 主界面壳 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 211 无相机条件下，全屏教学窗能点：占位预览、可折叠右工具条、可拖动 AI 浮标（按住发 PTT 信号、单击无面板）、融合/拼接/历史/设置打开左右分屏。

**Architecture:** 壳层状态是无 Qt 的 `ShellState`（工具条、右栏、叠层、分割比、浮标坐标、手势分类）。`MainWindow` 只订阅状态并组控件。`python -m app` 取代探测页。相机、ASR、格子向导、历史数据、设置表单不在本计划。

**Tech Stack:** Python 3.11、PySide6-Essentials、pytest。板端 `linuxfb`（已验证）。Mac 可有桌面窗口。

## Global Constraints

- 只改 `ai-microscope-edu/`。不改 `microscope/`、`microclaw/`、235。
- UI/交互以 [`docs/superpowers/specs/2026-09-08-edu-kiosk-ui-design.md`](../specs/2026-09-08-edu-kiosk-ui-design.md) §3–§5 为准。
- 学生问答路径不打字；本计划右栏只放标题占位，不放输入框。
- 无相机：预览「等待相机」。标注/计数只切 overlay 标志，不画 ROI、不跑模型。
- 板端继续 `QT_QPA_PLATFORM=linuxfb:fb=/dev/fb0`。不要默认改回 eglfs。
- 非平凡逻辑先测后写。Qt 布局在 211 点验，不强制 pytest-qt。
- 未经用户明确要求不要 `git commit`。计划步骤里的 commit 一律跳过。
- 回复与源码注释用简体中文。

---

## File map

| 路径 | 职责 |
|------|------|
| `software/app/shell_state.py` | 工具条展开、右栏、overlay、分割比、浮标夹紧、手势分类 |
| `software/tests/test_shell_state.py` | 上述纯逻辑 |
| `software/app/platform.py` | 无桌面时选 linuxfb（从探测页抽出） |
| `software/app/preview_pane.py` | 占位预览 |
| `software/app/tool_strip.py` | 右工具条 + 折叠柄 |
| `software/app/ai_fab.py` | 浮标拖动 / 按住 PTT 信号 |
| `software/app/fab_store.py` | 浮标坐标 json |
| `software/app/stub_pages.py` | 右栏四页占位 |
| `software/app/main_window.py` | 分屏 + 叠浮标 |
| `software/app/__main__.py` | `python -m app` |
| `software/deploy/edu-app.service` | 板端自启 |
| `software/app/kiosk_probe.py` | 保留，不再作为默认入口 |
| `software/README.md` | 同步 rsync 与服务名 |

后续计划（本文件不做）：拍照计划/蛇形编号、PTT→ASR/TTS、历史存储、设置 ISP/Wi-Fi/USER.md、知识库 HTTP、UVC。

---

### Task 1: `ShellState` 纯逻辑

**Files:**
- Create: `ai-microscope-edu/software/app/shell_state.py`
- Create: `ai-microscope-edu/software/tests/test_shell_state.py`
- Modify: `ai-microscope-edu/software/app/__init__.py`

**Interfaces:**
- Consumes: spec §3–§5
- Produces: `RightPanel`、`Overlay`、`FabPos`、`ShellState`、`FabGestureKind`、`classify_fab_gesture`、`SPLIT_DEFAULT`

- [ ] **Step 1: Write the failing test**

创建 `ai-microscope-edu/software/tests/test_shell_state.py`：

```python
"""主界面壳层状态：与 edu-kiosk-ui-design §3–§5 一致，无 Qt。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.shell_state import (  # noqa: E402
    DRAG_THRESHOLD_PX,
    FabGestureKind,
    FabPos,
    Overlay,
    RightPanel,
    SPLIT_DEFAULT,
    ShellState,
    classify_fab_gesture,
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
    s.close_right()
    assert s.split_open is False
    assert s.right_panel is RightPanel.NONE


def test_split_ratio_clamped() -> None:
    s = ShellState()
    s.set_split_ratio(0.05)
    assert s.split_ratio == pytest.approx(0.25)
    s.set_split_ratio(0.95)
    assert s.split_ratio == pytest.approx(0.75)
    s.set_split_ratio(0.4)
    assert s.split_ratio == pytest.approx(0.4)


def test_fab_clamped_inside_preview() -> None:
    pos = FabPos(x=-10, y=5000).clamped(width=1080, height=1920, size=72)
    assert 8 <= pos.x <= 1080 - 72 - 8
    assert 8 <= pos.y <= 1920 - 72 - 8


def test_fab_gesture_drag_vs_tap_vs_ptt() -> None:
    assert classify_fab_gesture(moved=DRAG_THRESHOLD_PX, held_s=0.1) is FabGestureKind.DRAG
    assert classify_fab_gesture(moved=0.0, held_s=0.1) is FabGestureKind.TAP
    assert classify_fab_gesture(moved=0.0, held_s=0.4) is FabGestureKind.PTT


def test_unknown_tool_raises() -> None:
    with pytest.raises(KeyError):
        ShellState().open_tool("wifi")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m pytest tests/test_shell_state.py -q
```

Expected: FAIL，`ModuleNotFoundError: app.shell_state` 或收集错误。

- [ ] **Step 3: Write minimal implementation**

`ai-microscope-edu/software/app/__init__.py` 改为：

```python
"""教学一体机 PySide6 入口包。壳层在 `main_window`；`kiosk_probe` 仅作无桌面探测留档。"""
```

创建 `ai-microscope-edu/software/app/shell_state.py`：

```python
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
        return self.right_panel is not RightPanel.NONE

    def toggle_strip(self) -> None:
        self.strip_expanded = not self.strip_expanded

    def open_tool(self, name: str) -> None:
        """工具条按钮。未知名字抛 KeyError。"""
        if name == "annotate":
            self.overlay = Overlay.ANNOTATE
            return
        if name == "count":
            self.overlay = Overlay.COUNT
            return
        self.right_panel = _TOOL_TO_PANEL[name]
        self.overlay = Overlay.NONE

    def close_right(self) -> None:
        self.right_panel = RightPanel.NONE

    def set_split_ratio(self, ratio: float) -> None:
        self.split_ratio = min(SPLIT_MAX, max(SPLIT_MIN, ratio))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m pytest tests/test_shell_state.py -q
```

Expected: `8 passed`。若本机无 pytest：`python3 -m pip install pytest` 后再跑。

- [ ] **Step 5: Commit**

跳过（用户未要求 commit）。

---

### Task 2: 平台选择 + 占位预览 + 工具条窗

**Files:**
- Create: `ai-microscope-edu/software/app/platform.py`
- Create: `ai-microscope-edu/software/app/preview_pane.py`
- Create: `ai-microscope-edu/software/app/tool_strip.py`
- Create: `ai-microscope-edu/software/app/stub_pages.py`
- Create: `ai-microscope-edu/software/app/main_window.py`
- Create: `ai-microscope-edu/software/app/__main__.py`
- Modify: `ai-microscope-edu/software/app/kiosk_probe.py`（改为调用 `platform.ensure_embedded_platform`）

**Interfaces:**
- Consumes: `ShellState.open_tool`、`toggle_strip`、`close_right`、`set_split_ratio`
- Produces: `ensure_embedded_platform()`、`MainWindow`、`main()`

- [ ] **Step 1: 抽出平台选择（无新测；探测页行为不变）**

创建 `ai-microscope-edu/software/app/platform.py`：

```python
"""无桌面时的 Qt 平台插件。211 上必须 linuxfb，eglfs_kms 会 ABRT。"""

from __future__ import annotations

import os


def ensure_embedded_platform() -> None:
    """已有 DISPLAY/WAYLAND 或已设 QT_QPA_PLATFORM 时不改。"""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb:fb=/dev/fb0")
```

`kiosk_probe.py` 删除 `_ensure_embedded_platform`，`main` 里改为 `from app.platform import ensure_embedded_platform`。

- [ ] **Step 2: 预览、工具条、占位右页、主窗**

`preview_pane.py`：

```python
"""占位预览。相机接入前只显示等待文案。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.shell_state import Overlay


class PreviewPane(QWidget):
    """铺满左侧（或全屏）的预览区。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPane")
        self.setStyleSheet("QWidget#previewPane { background: #1a1a1a; }")
        layout = QVBoxLayout(self)
        self._label = QLabel("等待相机")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #dddddd; font-size: 36px;")
        layout.addWidget(self._label)

    def set_overlay(self, overlay: Overlay) -> None:
        """标注/计数尚未实现，只改角标提示。"""
        extra = {
            Overlay.NONE: "",
            Overlay.ANNOTATE: "（标注）",
            Overlay.COUNT: "（计数）",
        }[overlay]
        self._label.setText("等待相机" + extra)
```

`tool_strip.py`：

```python
"""右侧工具条：展开为全部入口，折叠为窄柄。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

# 顺序与 spec §3 表格一致（AI 浮标不在此列）。
TOOLS: tuple[tuple[str, str], ...] = (
    ("annotate", "标注"),
    ("count", "计数"),
    ("fusion", "融合"),
    ("stitch", "拼接"),
    ("history", "历史"),
    ("settings", "设置"),
)


class ToolStrip(QWidget):
    """右缘工具条。"""

    def __init__(
        self,
        on_tool: Callable[[str], None],
        on_toggle: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_tool = on_tool
        self._buttons: list[QPushButton] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._fold = QPushButton("‹")
        self._fold.setFixedHeight(56)
        self._fold.clicked.connect(on_toggle)
        layout.addWidget(self._fold)
        for key, title in TOOLS:
            btn = QPushButton(title)
            btn.setFixedSize(72, 72)
            btn.clicked.connect(lambda _=False, k=key: self._on_tool(k))
            layout.addWidget(btn)
            self._buttons.append(btn)
        layout.addStretch(1)

    def set_expanded(self, expanded: bool) -> None:
        """折叠时只留折叠柄。"""
        self._fold.setText("‹" if expanded else "›")
        for btn in self._buttons:
            btn.setVisible(expanded)
        self.setFixedWidth(96 if expanded else 48)
```

`stub_pages.py`：

```python
"""右栏占位页。本计划不实现向导/历史/设置表单。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.shell_state import RightPanel

_TITLES = {
    RightPanel.FUSION: "融合（下期）",
    RightPanel.STITCH: "拼接（下期）",
    RightPanel.HISTORY: "历史（下期）",
    RightPanel.SETTINGS: "设置（下期）",
}


class StubPage(QWidget):
    """带关闭的右栏占位。"""

    def __init__(self, panel: RightPanel, on_close: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel(_TITLES[panel])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px;")
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(56)
        close_btn.clicked.connect(on_close)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(close_btn)
```

`main_window.py`（本任务先做预览+工具条全宽，分屏在 Task 3 接上；若一次写完分屏也可以，但必须先让 Task 1 测试保持绿）：

```python
"""教学主窗：占位预览 + 工具条 +（Task 3）分屏 +（Task 4）浮标。"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QWidget

from app.platform import ensure_embedded_platform
from app.preview_pane import PreviewPane
from app.shell_state import RightPanel, ShellState
from app.stub_pages import StubPage
from app.tool_strip import ToolStrip


class MainWindow(QWidget):
    """全屏 kiosk 壳。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("eduMain")
        self.setWindowTitle("教学显微镜")
        self._state = ShellState()
        self._preview = PreviewPane()
        self._right = QStackedWidget()
        self._pages = {
            RightPanel.FUSION: StubPage(RightPanel.FUSION, self._close_right),
            RightPanel.STITCH: StubPage(RightPanel.STITCH, self._close_right),
            RightPanel.HISTORY: StubPage(RightPanel.HISTORY, self._close_right),
            RightPanel.SETTINGS: StubPage(RightPanel.SETTINGS, self._close_right),
        }
        for panel, page in self._pages.items():
            self._right.addWidget(page)
        self._right.hide()
        self._strip = ToolStrip(self._on_tool, self._toggle_strip)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._mid = QWidget()
        mid_l = QHBoxLayout(self._mid)
        mid_l.setContentsMargins(0, 0, 0, 0)
        mid_l.setSpacing(0)
        mid_l.addWidget(self._preview, 1)
        mid_l.addWidget(self._right, 1)
        root.addWidget(self._mid, 1)
        root.addWidget(self._strip, 0)
        self._apply()

    def _on_tool(self, name: str) -> None:
        self._state.open_tool(name)
        self._apply()

    def _toggle_strip(self) -> None:
        self._state.toggle_strip()
        self._apply()

    def _close_right(self) -> None:
        self._state.close_right()
        self._apply()

    def _apply(self) -> None:
        self._strip.set_expanded(self._state.strip_expanded)
        self._preview.set_overlay(self._state.overlay)
        if self._state.split_open:
            self._right.show()
            page = self._pages[self._state.right_panel]
            self._right.setCurrentWidget(page)
        else:
            self._right.hide()


def main(argv: list[str] | None = None) -> int:
    """启动全屏教学壳。"""
    ensure_embedded_platform()
    app = QApplication(argv if argv is not None else sys.argv)
    win = MainWindow()
    win.showFullScreen()
    return app.exec()
```

`__main__.py`：

```python
from app.main_window import main

raise SystemExit(main())
```

本任务用 `QHBoxLayout` 两栏等分模拟分屏；Task 3 换成可拖 `QSplitter` 并接 `set_split_ratio`。

- [ ] **Step 3: 再跑 Task 1 测试，确认未破坏**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m pytest tests/test_shell_state.py -q
```

Expected: `8 passed`。

- [ ] **Step 4: Mac 冒烟（有桌面）**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m app
```

Expected: 全屏（或桌面上的全屏窗）：黑底「等待相机」、右侧六个圆钮；点融合出现右栏「融合（下期）」与关闭；点标注预览文字带「（标注）」且右栏关掉后仍全屏预览。关窗即退。

- [ ] **Step 5: Commit**

跳过。

---

### Task 3: 可拖分割条

**Files:**
- Modify: `ai-microscope-edu/software/app/main_window.py`

**Interfaces:**
- Consumes: `ShellState.set_split_ratio`、`split_ratio`、`SPLIT_DEFAULT`
- Produces: 中间 `QSplitter`，拖动后写回状态

- [ ] **Step 1: 用 QSplitter 替换 `_mid` 里的等分 layout**

在 `main_window.py` 增加：

```python
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSplitter, QStackedWidget, QWidget
```

`MainWindow.__init__` 里：

```python
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._preview)
        self._splitter.addWidget(self._right)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.splitterMoved.connect(self._on_splitter)
        # ...
        mid_l.addWidget(self._splitter, 1)
```

删除 `mid_l.addWidget(self._preview)` / `addWidget(self._right)` 的旧两行。

```python
    def _on_splitter(self, _pos: int, _index: int) -> None:
        sizes = self._splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        self._state.set_split_ratio(sizes[0] / total)

    def _apply(self) -> None:
        self._strip.set_expanded(self._state.strip_expanded)
        self._preview.set_overlay(self._state.overlay)
        if self._state.split_open:
            self._right.show()
            page = self._pages[self._state.right_panel]
            self._right.setCurrentWidget(page)
            QTimer.singleShot(0, self._sync_splitter)
        else:
            self._right.hide()

    def _sync_splitter(self) -> None:
        w = max(self._splitter.width(), 1)
        left = int(w * self._state.split_ratio)
        self._splitter.setSizes([left, max(w - left, 1)])
```

打开分屏时若 `sizes` 尚未布局完成，用 `QTimer.singleShot(0, self._sync_splitter)` 在下一拍按 1:1（默认 `SPLIT_DEFAULT`）设置。

- [ ] **Step 2: pytest 仍绿**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m pytest tests/test_shell_state.py -q
```

Expected: `8 passed`。

- [ ] **Step 3: Mac 点验分屏**

`PYTHONPATH=. python3 -m app`：打开设置，拖中间条，左右比例变化；关闭后预览铺满（右栏隐藏）。

- [ ] **Step 4: Commit**

跳过。

---

### Task 4: AI 浮标

**Files:**
- Create: `ai-microscope-edu/software/app/ai_fab.py`
- Modify: `ai-microscope-edu/software/app/main_window.py`
- Create: `ai-microscope-edu/software/tests/test_fab_persist.py`

**Interfaces:**
- Consumes: `FabPos.clamped`、`classify_fab_gesture`、`FabGestureKind`
- Produces: `AiFab` 的 `ptt_changed(bool)` 信号；位置写入 `var/ui/fab.json`

- [ ] **Step 1: Write the failing persist test**

`ai-microscope-edu/software/tests/test_fab_persist.py`：

```python
"""浮标坐标读写：损坏文件则回默认并仍能夹紧。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.fab_store import load_fab, save_fab  # noqa: E402
from app.shell_state import FAB_MARGIN, FabPos  # noqa: E402


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "fab.json"
    save_fab(path, FabPos(40, 80))
    loaded = load_fab(path, width=1080, height=1920)
    assert loaded.x == 40
    assert loaded.y == 80


def test_missing_and_corrupt_use_margin(tmp_path: Path) -> None:
    missing = load_fab(tmp_path / "nope.json", width=1080, height=1920)
    assert missing.x == FAB_MARGIN
    (tmp_path / "bad.json").write_text("{")
    bad = load_fab(tmp_path / "bad.json", width=1080, height=1920)
    assert bad.x == FAB_MARGIN
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m pytest tests/test_fab_persist.py -q
```

Expected: FAIL，`app.fab_store` 不存在。

- [ ] **Step 3: `fab_store.py` + `AiFab` + 挂到预览**

`ai-microscope-edu/software/app/fab_store.py`：

```python
"""浮标位置落盘。文件坏了就回到边距默认。"""

from __future__ import annotations

import json
from pathlib import Path

from app.shell_state import FAB_MARGIN, FabPos


def save_fab(path: Path, pos: FabPos) -> None:
    """写入 `{"x":..., "y":...}`。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"x": pos.x, "y": pos.y}), encoding="utf-8")


def load_fab(path: Path, *, width: float, height: float) -> FabPos:
    """缺文件或 JSON 损坏时返回 `(FAB_MARGIN, FAB_MARGIN)` 并夹紧。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pos = FabPos(float(data["x"]), float(data["y"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pos = FabPos(FAB_MARGIN, FAB_MARGIN)
    return pos.clamped(width, height)
```

`ai-microscope-edu/software/app/ai_fab.py`：

```python
"""可拖动 AI 浮标：单击无事，按住发 PTT，位移超过阈值则拖动。"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QPushButton, QWidget

from app.shell_state import (
    FAB_SIZE,
    FabGestureKind,
    FabPos,
    classify_fab_gesture,
)


class AiFab(QPushButton):
    """叠在预览上的圆钮。"""

    ptt_changed = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__("AI", parent)
        self.setFixedSize(int(FAB_SIZE), int(FAB_SIZE))
        self.setCheckable(False)
        self._press_pos = QPoint()
        self._press_t = 0.0
        self._ptt_on = False
        self.setStyleSheet(
            "QPushButton { background: #2b6cb0; color: white; border-radius: 36px; font-size: 22px; }"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._press_t = time.monotonic()
            self._ptt_on = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_pos
            moved = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            kind = classify_fab_gesture(moved=moved, held_s=time.monotonic() - self._press_t)
            if kind is FabGestureKind.DRAG:
                if self._ptt_on:
                    self._ptt_on = False
                    self.ptt_changed.emit(False)
                np = self.mapToParent(event.position().toPoint())
                self.move(np.x() - int(FAB_SIZE / 2), np.y() - int(FAB_SIZE / 2))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_pos
            moved = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            kind = classify_fab_gesture(moved=moved, held_s=time.monotonic() - self._press_t)
            if self._ptt_on or kind is FabGestureKind.PTT:
                if self._ptt_on:
                    self._ptt_on = False
                    self.ptt_changed.emit(False)
            # TAP：什么都不做
        super().mouseReleaseEvent(event)

    def pos_state(self) -> FabPos:
        return FabPos(float(self.x()), float(self.y()))
```

PTT 需要在按住超过 `PTT_HOLD_S` 且未进入拖动时开始。在 `AiFab` 用 `QTimer` 更干净。把上面的 press/move/release 换成：

```python
from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QPushButton, QWidget

from app.shell_state import FAB_SIZE, PTT_HOLD_S, FabGestureKind, FabPos, classify_fab_gesture


class AiFab(QPushButton):
    """叠在预览上的圆钮。"""

    ptt_changed = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__("AI", parent)
        self.setFixedSize(int(FAB_SIZE), int(FAB_SIZE))
        self._press_global = QPoint()
        self._max_moved = 0.0
        self._ptt_on = False
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._start_ptt)
        self.setStyleSheet(
            "QPushButton { background: #2b6cb0; color: white; border-radius: 36px; font-size: 22px; }"
        )

    def _start_ptt(self) -> None:
        if self._max_moved < 24.0 and not self._ptt_on:
            self._ptt_on = True
            self.ptt_changed.emit(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._max_moved = 0.0
            self._ptt_on = False
            self._hold.start(int(PTT_HOLD_S * 1000))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_global
            moved = float((delta.x() ** 2 + delta.y() ** 2) ** 0.5)
            self._max_moved = max(self._max_moved, moved)
            if classify_fab_gesture(moved=self._max_moved, held_s=1.0) is FabGestureKind.DRAG:
                self._hold.stop()
                if self._ptt_on:
                    self._ptt_on = False
                    self.ptt_changed.emit(False)
                gp = self.parent().mapFromGlobal(event.globalPosition().toPoint())
                self.move(int(gp.x() - FAB_SIZE / 2), int(gp.y() - FAB_SIZE / 2))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._hold.stop()
            if self._ptt_on:
                self._ptt_on = False
                self.ptt_changed.emit(False)
        super().mouseReleaseEvent(event)

    def pos_state(self) -> FabPos:
        return FabPos(float(self.x()), float(self.y()))
```

实现时 **只保留这一份带 QTimer 的 `AiFab`**，不要把两段都写进文件。

在 `MainWindow`：`self._fab = AiFab(self._preview)`，启动时 `load_fab`，关闭/移动结束 `save_fab`。路径：`Path(__file__).resolve().parents[1] / "var" / "ui" / "fab.json"`。`ptt_changed` 暂接到预览标签：`等待相机（说话中）`，无 ASR。

把浮标夹紧：每次 move 后 `FabPos(...).clamped(self._preview.width(), self._preview.height())` 再 `move`。

`software/var/` 应进 `.gitignore`（在仓库根 `.gitignore` 增加 `ai-microscope-edu/software/var/`）。

- [ ] **Step 4: Run persist tests**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/software
PYTHONPATH=. python3 -m pytest tests/test_shell_state.py tests/test_fab_persist.py -q
```

Expected: 全部 passed（Task 1 的 8 个 + persist 2 个）。

- [ ] **Step 5: Mac 点验浮标**

拖动 AI 圆不打开任何面板；短点无面板；按住超过约 0.35s 预览出现「说话中」，松开消失。

- [ ] **Step 6: Commit**

跳过。

---

### Task 5: 板端入口换成教学壳

**Files:**
- Create: `ai-microscope-edu/software/deploy/edu-app.service`
- Modify: `ai-microscope-edu/software/README.md`

**Interfaces:**
- Consumes: `python -m app`
- Produces: 211 上 `edu-app.service` 替代 `edu-kiosk-probe`

- [ ] **Step 1: unit 文件**

`edu-app.service` 从 `edu-kiosk-probe.service` 复制，改 Description、`ExecStart=... python -m app`、Conflicts 仍含 scandog/mipi-hmi。WorkingDirectory 仍是 `software/`。

- [ ] **Step 2: README** 写 rsync 与：

```bash
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude 'var' \
  software/ cat@10.198.24.211:/home/cat/ai-microscope-edu/software/
ssh cat@10.198.24.211 'sudo cp /home/cat/ai-microscope-edu/software/deploy/edu-app.service /etc/systemd/system/edu-app.service && sudo systemctl disable --now edu-kiosk-probe && sudo systemctl daemon-reload && sudo systemctl enable --now edu-app && journalctl -u edu-app -n 30 --no-pager'
```

- [ ] **Step 3: 同步并在 211 点验**

Expected：MIPI 不再是蓝底探测字；黑底「等待相机」+ 右工具条 + AI 圆。`systemctl is-active edu-app` 为 `active`。scandog 仍 disable。

- [ ] **Step 4: Commit**

跳过。

---

## Spec coverage（本计划）

| spec | 本计划 |
|------|--------|
| §3 预览铺满、工具条折叠、六入口 | Task 2 |
| §3 浮标不进工具条、可拖、位置记忆 | Task 4 |
| §4 单击无面板、按住 PTT（仅信号） | Task 4 |
| §5 分屏 1:1 可拖、关闭恢复、浮标在左预览 | Task 3–4 |
| §4 真 ASR/字幕、§6–§8 向导/历史/设置/KB | **否，后续计划** |

## 执行方式

计划写在 `ai-microscope-edu/docs/superpowers/plans/2026-09-08-edu-kiosk-shell.md`。

**1. Subagent-Driven（推荐）** — 每任务新子代理，任务间你过一眼  

**2. Inline Execution** — 本会话按 executing-plans 逐任务做  

选哪种？
