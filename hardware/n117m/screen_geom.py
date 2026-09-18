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


def stack_well_h(glass_t: float, steel_pocket_d: float) -> float:
    """底槽直角井高度：先放下玻璃+钢板总厚，再接 60° 斜挡。"""
    return glass_t + steel_pocket_d


def patch_r_inner_x(face_w: float, printed_left_cover: float) -> float:
    """已打左半包住 printed_left_cover 时，右补救件内沿 X（原点在屏宽中点）。"""
    return -(face_w / 2.0 - printed_left_cover)


def tray_half_span(inner_w: float) -> float:
    """单半沿屏宽方向的跨度（不含侧墙外翻）。"""
    return inner_w / 2.0


def fits_x1c_bed(w: float, h: float, bed: float = 256.0, margin: float = 6.0) -> bool:
    """平放是否进拓竹 X1C 热床（留边）。整屏 258 面应失败。"""
    limit = bed - margin
    return w <= limit and h <= limit


def beam_rise(hyp: float, horiz: float) -> float:
    """横梁斜边 hyp、水平投影 horiz 时的升高（不量角度）。"""
    return math.sqrt(hyp * hyp - horiz * horiz)


def beam_tilt_deg(hyp: float, horiz: float) -> float:
    """横梁相对水平的倾角（度），由斜边与水平边算出。"""
    return math.degrees(math.acos(horiz / hyp))


def tube_axis_y(back_y: float, axis_from_back: float) -> float:
    """三目筒轴的世界 Y：臂后表面 + 卡尺水平距。"""
    return back_y + axis_from_back


def screen_contact_y(back_y: float, axis_from_back: float, tube_d: float) -> float:
    """屏上边触点 Y。屏朝 −Y，碰到筒靠近臂背面的一侧。"""
    return tube_axis_y(back_y, axis_from_back) - tube_d / 2.0


def screen_origin_yz(
    contact_y: float,
    contact_z: float,
    face_h: float,
    tilt_deg: float,
) -> tuple[float, float]:
    """layout 里 rotate([tilt,0,0]) 后，屏顶 (0, face_h, 0) 落到触点时，屏原点的世界 y、z。"""
    a = math.radians(tilt_deg)
    return (
        contact_y - face_h * math.cos(a),
        contact_z - face_h * math.sin(a),
    )


def beam_join_y(back_y: float) -> float:
    """横梁顶面在臂背面的接合 Y。"""
    return back_y


def back_beam_interior_deg(hyp: float, horiz: float) -> float:
    """臂背面向下与横梁出去之间的夹角。背面竖直、梁向上扬时应为钝角。"""
    return math.degrees(math.acos(-beam_rise(hyp, horiz) / hyp))
