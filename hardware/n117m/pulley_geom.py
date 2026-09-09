"""GT2 剖分轮几何（与 scad/gt2.scad、05_pulley_split.scad 同公式）。

单位 mm。市售 GT2 轮：节圆直径 = 齿数 × 2 / π，外径 ≈ 节圆 − 2×0.254。
同平面腹板要放下 M3：牙根到毂的径向距离须大于螺母+壁。
"""

from __future__ import annotations

import math

GT2_PITCH = 2.0
GT2_U = 0.254
GT2_TOOTH_H = 0.75
MIN_RIM_MM = 2.0
M3_NUT_R = 3.2
WEB_WALL = 1.4


def gt2_pd(teeth: int, pitch: float = GT2_PITCH) -> float:
    """节圆直径。"""
    return teeth * pitch / math.pi


def gt2_od(teeth: int, pitch: float = GT2_PITCH, u: float = GT2_U) -> float:
    """齿顶圆直径。"""
    return gt2_pd(teeth, pitch) - 2 * u


def rim_radial(teeth: int, hub_od: float) -> float:
    """牙根到灰毂外圆的径向壁厚。"""
    root_d = gt2_od(teeth) - 2 * GT2_TOOTH_H
    return (root_d - hub_od) / 2.0


def m3_fits_in_web(teeth: int, hub_od: float) -> bool:
    """同平面抱箍能否在毂与齿根之间放下 M3 螺母。"""
    return rim_radial(teeth, hub_od) >= (M3_NUT_R * 2 + WEB_WALL)


def web_just_taller_than_belt(web_h: float, belt_h: float, extra_max: float = 1.2) -> bool:
    """抱箍到齿圈的腹板只需比带宽略高，不必撑满两侧挡边总高。"""
    return belt_h - 1e-6 <= web_h <= belt_h + extra_max + 1e-6


def pulley_fits_hub(pulley_h: float, hub_protrusion: float, standoff: float) -> bool:
    """剖分轮轴向是否落在灰毂伸出段内（允许最多 1.2mm 伸出毂外沿）。"""
    return pulley_h + standoff <= hub_protrusion + 1.2 + 1e-6


def ear_h_fits_m3(ear_h: float, m3_d: float = 3.2, wall: float = 1.2) -> bool:
    """横穿 M3 的夹耳轴向高度须包住孔径+两侧壁，不能做成挡边那么薄。"""
    return ear_h + 1e-6 >= m3_d + 2 * wall


def belt_clears_outer_ears(
    ear_inner_r: float,
    tooth_od: float,
    belt_thick: float = 1.4,
    gap: float = 3.0,
) -> bool:
    """外侧夹耳内缘须在齿顶圆 + 带厚 + 间隙之外，皮带才能绕齿圈。"""
    return ear_inner_r + 1e-6 >= tooth_od / 2.0 + belt_thick + gap
