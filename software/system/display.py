"""物理屏尺寸、旋转归一化与触摸坐标映射（物理→逻辑，顺时针）。"""

from __future__ import annotations

PHYSICAL_W: int = 1080
PHYSICAL_H: int = 1920

_VALID_ROTATIONS = frozenset({0, 90, 180, 270})


def normalize_rotation(deg: object) -> int:
    """将任意输入归一化为合法顺时针旋转角（度）。

    参数:
        deg: 期望为 0/90/180/270 或可转为 int 的值。

    返回:
        合法角度；无法转换或不在合法集合时返回 90。
    """
    try:
        value = int(deg)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 90
    if value in _VALID_ROTATIONS:
        return value
    return 90


def logical_size(pw: int, ph: int, deg: int) -> tuple[int, int]:
    """给定物理宽高与旋转角，返回逻辑视口 (宽, 高)。

    参数:
        pw: 物理宽度（像素）。
        ph: 物理高度（像素）。
        deg: 旋转角（度），会先经 normalize_rotation 处理。

    返回:
        逻辑宽度与高度；90°/270° 时宽高互换。
    """
    rotation = normalize_rotation(deg)
    if rotation in (90, 270):
        return ph, pw
    return pw, ph


def map_touch(px: float, py: float, pw: int, ph: int, deg: int) -> tuple[float, float]:
    """将物理触摸坐标映射为逻辑坐标（顺时针旋转约定）。

    参数:
        px, py: 物理坐标。
        pw, ph: 物理宽高。
        deg: 旋转角（度）。

    返回:
        逻辑坐标 (lx, ly)。
    """
    rotation = normalize_rotation(deg)
    if rotation == 0:
        return px, py
    if rotation == 90:
        return py, pw - px
    if rotation == 180:
        return pw - px, ph - py
    # 270
    return ph - py, px
