"""浮标位置落盘；无版本或损坏时回退到预览 80%/80%。"""

from __future__ import annotations

import json
import math
from pathlib import Path

from app.shell_state import FabPos, default_fab_pos, place_fab

# 首版 JSON 只有 x/y，默认在左上角。v>=2 才信任已保存坐标。
FAB_FILE_VERSION = 2


def save_fab(path: Path, pos: FabPos) -> None:
    """写入浮标坐标。

    参数：
        path: JSON 文件路径；父目录不存在时会自动创建。
        pos: 要持久化的预览局部坐标。

    副作用：
        覆盖 ``path``，写入包含 ``v``、``x``、``y`` 的 JSON 对象。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"v": FAB_FILE_VERSION, "x": pos.x, "y": pos.y}),
        encoding="utf-8",
    )


def load_fab(path: Path, *, width: float, height: float) -> FabPos:
    """读取并夹紧浮标坐标。

    参数：
        path: 浮标坐标 JSON 文件。
        width: 当前预览宽度。
        height: 当前预览高度。

    返回：
        夹紧在预览边界内的坐标；文件缺失、损坏、无版本、字段无效或
        对当前预览越界时，回到 80%/80% 锚点。
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("v", 0)) < FAB_FILE_VERSION:
            raise ValueError("legacy FAB file without current version")
        x = float(data["x"])
        y = float(data["y"])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("FAB coordinates must be finite")
        pos = FabPos(x, y)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pos = default_fab_pos(width, height)
    return place_fab(pos, width, height)
