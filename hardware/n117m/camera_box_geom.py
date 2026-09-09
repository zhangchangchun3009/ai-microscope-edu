"""N-117M 相机盒几何（与 scad/00_camera_box.scad 同公式）。

单位 mm。转接筒圆柱头 φ25 滑配；感光开口搬自 OpenFlexure
`imx678_20.scad` 垫片中心避让（15.5×13.5 圆角矩形），不再用圆孔。
"""

from __future__ import annotations

# OpenFlexure imx678_20.scad：orig_clear_x / orig_clear_y / 圆角
OF_WINDOW_X = 15.5
OF_WINDOW_Y = 13.5
OF_WINDOW_R = 1.0


def sleeve_id(tube_od: float, clear: float) -> float:
    """套筒内径 = 圆柱头外径 + 打印间隙。"""
    return tube_od + clear


def sleeve_wall(collar_od: float, inner: float) -> float:
    """套筒径向壁厚。"""
    return (collar_od - inner) / 2.0


def m4_engagement(wall: float, boss_h: float) -> float:
    """M4 顶丝牙长。直孔时 boss_h=0，就是壁厚。"""
    return wall + boss_h


def tube_stopped_by_window(tube_od: float, win_x: float, win_y: float) -> bool:
    """25mm 筒进不了矩形感光开口，开口兼硬限位。"""
    return max(win_x, win_y) < tube_od


def sensor_z(sleeve_h: float, sleeve_top_to_sensor: float) -> float:
    """坐死时筒顶齐套筒顶；感光面再往上 17.526（原 C 口法兰距）。"""
    return sleeve_h + sleeve_top_to_sensor
