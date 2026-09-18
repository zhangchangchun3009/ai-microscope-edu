"""主板盒与抱箍几何（与 scad/50_board_box.scad、51_arm_clamp.scad 同数字）。

单位 mm。旧抽屉孔位抄自 lubancat_drawer_tray；竖盒元件朝盖时 X 取负。不引用 openscad_V1。
"""

from __future__ import annotations

# 旧抽屉从盒外看面板的 X。竖盒、焊盘贴后壁、元件朝盖时左右对调。
DRAWER_PORT_X = {
    "dc": -62.0,
    "typec": -47.5,
    "mic": -36.5,
    "phone": -27.0,
    "eth0": -13.0,
    "eth1": 7.0,
    "hdmi": 24.0,
    "usb3": 41.0,
    "usb2": 59.0,
}

PORT_X = {name: -x for name, x in DRAWER_PORT_X.items()}


def ffc_slot_w(cable_w: float, clear: float) -> float:
    """屏线槽宽 = 线宽 + 打印间隙。"""
    return cable_w + clear


def mount_hole_xy(pitch: float) -> list[tuple[float, float]]:
    """盖/矩形板 4 孔，相对中心，正方形。"""
    h = pitch / 2.0
    return [(-h, -h), (h, -h), (-h, h), (h, h)]


def port_centers() -> dict[str, tuple[float, float]]:
    """顶面孔中心：X 沿板长边，Y 为相对后壁内侧（原法兰 z=0）。"""
    y = {
        "dc": 12.5,
        "typec": 11.5,
        "mic": 11.6,
        "phone": 11.6,
        "eth0": 16.5,
        "eth1": 16.5,
        "hdmi": 18.5,
        "usb3": 23.8,
        "usb2": 17.8,
    }
    return {name: (PORT_X[name], y[name]) for name in PORT_X}


def usb2_outer_to_standoff_x(
    board_x: float, hole_inset: float, usb2_x: float, usb2_w: float
) -> float:
    """靠 USB2 那颗柱心到 USB2 开口外侧边的距离（沿板长边，mm）。

    原抽屉 USB2 心 59、宽 15.5、inset=4 → 柱在 71，外边 66.75，间距 4.25。
    """
    standoff = board_x / 2.0 - hole_inset
    outer = abs(usb2_x) + usb2_w / 2.0
    return standoff - outer


def speaker_pocket(speaker: dict) -> tuple[float, float]:
    """沉槽宽×高。宽对 18 mm 喇叭厚向，高对 36 mm 加间隙。"""
    return (float(speaker["pocket_wy"][0]), float(speaker["pocket_wy"][1]))


def pcb_standoff_axis() -> str:
    """后壁支柱孔轴线。从开口沿 +Y 伸进去拧，不是沿高度 Z。"""
    return "y"


def pcb_z_offset(
    outer_z: float,
    wall: float,
    board_z: float,
    hole_inset: float = 4.0,
    standoff_to_port: float = 4.0,
) -> float:
    """板中心相对盒中心的 +Z。

    四角距边与原抽屉相同：``inset = 5-1 = 4`` mm。靠接口一对支柱中心
    到顶墙内表面也是 4 mm；板接口边贴内表面，柱 φ10 切入接口面约 1 mm。
    """
    inner_top = outer_z / 2.0 - wall
    return inner_top - standoff_to_port - (board_z / 2.0 - hole_inset)


def pcb_standoff_z(
    pcb_z: float, board_z: float, hole_inset: float
) -> tuple[float, float]:
    """四角支柱两个 Z：远离 / 靠近接口面。"""
    h = board_z / 2.0 - hole_inset
    return (pcb_z - h, pcb_z + h)


def port_fit_clip_z(
    pcb_z: float,
    board_z: float,
    hole_inset: float,
    outer_z: float,
    below: float = 14.0,
) -> tuple[float, float]:
    """试打件 Z 范围：包住靠近接口的两颗孔，切掉远离接口的两颗。"""
    z_hi = pcb_z + board_z / 2.0 - hole_inset
    return (z_hi - below, outer_z / 2.0 + 1.0)


def y_port_datum(outer_y: float, wall: float) -> float:
    """顶面孔 Y 基准：后壁内侧，与原抽屉法兰底 z=0（3mm 底板底面）相同。不要加支柱高。"""
    return -outer_y / 2.0 + wall


def y_solder_plane(outer_y: float, wall: float, standoff_h: float) -> float:
    """焊盘平面局部 Y：后壁内侧 + 支柱高（原 3+5=8 mm）。开孔不从这里起算。"""
    return y_port_datum(outer_y, wall) + standoff_h


def y_component_face(
    outer_y: float, wall: float, standoff_h: float, pcb_t: float = 1.6
) -> float:
    """元件面局部 Y：焊盘平面 + 板厚。"""
    return y_solder_plane(outer_y, wall, standoff_h) + pcb_t


def speaker_old_stand_pocket() -> tuple[float, float, float]:
    """原底座 speaker_cutouts 沉槽：沿墙厚 × 宽 × 高。"""
    return (4.1, 20.5, 39.0)


def speaker_old_stand_slot() -> tuple[float, float, float]:
    """原底座透音缝 cube([20, 12, 4])，X 向打穿外壁。"""
    return (20.0, 12.0, 4.0)


def speaker_old_stand_slot_z() -> tuple[float, float, float]:
    """原底座三条出音缝的 Z 偏移。"""
    return (-10.0, 0.0, 10.0)


def speaker_old_stand_boss_xy() -> tuple[float, float]:
    """原底座 speaker_mount_bosses 内侧立方体：厚 × 沿开口方向。"""
    return (5.0, 22.0)


def speaker_screw_x(inner_half: float, side: float, boss_t: float = 5.0, half_h: float = 3.0) -> float:
    """安装孔中心 X：从基座朝盒内的那一面伸入，孔口朝盒内。"""
    return side * (inner_half - boss_t + half_h)


def speaker_pocket_x(inner_half: float, side: float, boss_t: float = 5.0, depth: float = 4.1) -> float:
    """沉槽中心 X：从基座内表面向墙挖 depth，槽口开在立方体上。"""
    return side * (inner_half - boss_t + depth / 2.0)


def clamp_cavity_w(arm_w: float, clear_each: float) -> float:
    """抱箍内腔宽 = 卡尺臂宽 + 两侧间隙。首打每侧 1.5 过宽，改为 0.5，靠顶丝收紧。"""
    return arm_w + 2.0 * clear_each


def m3_self_tap_d() -> float:
    """M3 自攻进 PETG-CF 的底孔。"""
    return 2.4


def m3_nut_af() -> float:
    """M3 六角螺帽对边。"""
    return 5.5


def m3_nut_h() -> float:
    """M3 标准螺帽厚度。"""
    return 2.4


def min_outer_y_for_usb3(
    wall: float = 2.5,
    lid_t: float = 3.0,
    y_from_pcb: float = 23.8,
    hole_y: float = 32.0,
    clear_to_lid: float = 3.5,
) -> float:
    """离臂厚度下限：后壁 + USB3 开孔远边（原法兰 z=0 的 17.8+6）+ 到盖余量 + 盖厚。"""
    return wall + y_from_pcb + hole_y / 2.0 + clear_to_lid + lid_t


def lid_nut_boss_xz_y() -> tuple[float, float]:
    """合箱角座：XZ 边长 × 沿开口方向深度，内侧嵌 M3 螺帽。"""
    return (12.0, 8.0)
