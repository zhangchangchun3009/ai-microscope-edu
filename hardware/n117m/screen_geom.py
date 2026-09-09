"""10 寸屏托盘 / 横梁抱箍几何（与 scad/52_beam_clamp.scad 同数字）。

单位 mm。不引用 openscad_V1。
"""

from __future__ import annotations

import math


def steel_wh(
    face_w: float,
    face_h: float,
    inset_tb: float,
    inset_l: float,
    inset_r: float,
) -> tuple[float, float]:
    """钢板宽×高。左右边距可以不同；旋转 180° 后仍是同一块板。"""
    return (face_w - inset_l - inset_r, face_h - 2.0 * inset_tb)


def steel_window_w(face_w: float, inset_lr: list[float] | tuple[float, float]) -> float:
    """托盘后窗宽：按较小侧边距居中，13/17 对调都能过。"""
    return face_w - 2.0 * min(inset_lr)


def baffle_inward(height: float, deg: float) -> float:
    """挡板相对屏面夹角 deg 时，法向高度 height 在屏面上的内伸。"""
    return height / math.tan(math.radians(deg))


def tray_inner_wh(face_w: float, face_h: float, edge_clear: float) -> tuple[float, float]:
    """托盘内腔宽×高，每边加放进间隙。"""
    return (face_w + 2.0 * edge_clear, face_h + 2.0 * edge_clear)


def tray_half_span(inner_w: float) -> float:
    """单半沿屏宽方向的跨度（不含侧墙外翻）。"""
    return inner_w / 2.0


def fits_x1c_bed(w: float, h: float, bed: float = 256.0, margin: float = 6.0) -> bool:
    """平放是否进拓竹 X1C 热床（留边）。整屏 258 面应失败。"""
    limit = bed - margin
    return w <= limit and h <= limit
