// N-117M 镜臂铸造（含底座交接）+ Z 粗微同轴手轮
//
// 坐标：z=0 桌面；+Y 朝目镜（前，载物台一侧）；操作者正视目镜时
// 右手边为 −X。XY / 电机化 Z 都在 −X。
//
// 右视：弧在前（靠载物台），背面近乎直线（抱箍贴后表面）。
// 打开本文件：part = arm | knobs | head | stage | section | profile

use <05_pulley_split.scad>
use <30_head.scad>
use <40_stage.scad>

part = "arm"; // arm | knobs | head | stage | section | profile

$fn = 48;

base_w = 167;
base_d = 224;
base_h = 42;

arm_w         = 62;
arm_w_flare   = 74;
r_rear        = 3;    // 后棱小圆角（实物近似直角，16 过大）
r_front       = 5;
front_y0      = -52;  // 立柱前缘（载物台侧）基准
back_y_column = -108; // 背面，近乎竖直线

dovetail_w     = 22;
dovetail_depth = 6;

handle_cy = -68;
handle_cz = 215;
handle_ry = 14;
handle_rz = 42;

z_axis_z = 110;
z_boss_d = 30;
z_boss_h = 5;

slice_h = 3.2;
z_top   = 358;

// 操作者右侧 = −1。粗调 22 + 灰毂 13 + 衬套 12 ≈ A10 的 47。
z_side      = -1;
z_collar_h  = 12;
z_coarse_od = 46;
z_coarse_h  = 22;
z_hub_od    = 20;
z_hub_h     = 13;
z_wall_t    = 2.5;
z_cup_depth = 9;
z_nut_af    = 5.5;
z_pulley_standoff = 1.5;

show_split_pulley = true;

function arm_w_at(z) = lookup(z, [
    [0, arm_w_flare],
    [42, 70],
    [90, arm_w],
    [400, 58]
]);

/**
 * 后缘：立柱段基本竖直，仅悬臂段随颈部前伸。
 */
function y_back(z) = lookup(z, [
    [0, back_y_column],
    [250, back_y_column],
    [275, -95],
    [300, -55],
    [322, -12],
    [345, 18],
    [370, 24]
]);

/**
 * 前缘（载物台侧）：C 形弧 + 提手鼓包，再向前伸去托头。
 */
function y_front(z) = lookup(z, [
    [0, front_y0],
    [90, -50],
    [140, -42],
    [180, -32],
    [215, -28],
    [250, -36],
    [270, -18],
    [290, 6],
    [310, 28],
    [330, 48],
    [350, 58],
    [370, 62]
]);

function arm_z_axis_y() = (front_y0 + back_y_column) / 2;
function arm_width()    = arm_w;
function arm_front_y()  = front_y0;
function z_knob_side()  = z_side;

/** 镜臂侧面到灰毂外沿，沿 −X。 */
function z_hub_outer_x() =
    z_side * (arm_w / 2 + z_collar_h + z_coarse_h + z_hub_h);

function head_seat_y()     = (y_front(z_top) + y_back(z_top)) / 2;
function head_seat_top_z() = z_top + 8;

function x_out(side, dist) = side * (arm_w / 2 + dist);
function x_from_arm(dist) = x_out(z_side, dist);

/**
 * 某一高度的 XY 截面：后大圆角、前小圆角。
 */
module arm_slice_2d(z) {
    w  = arm_w_at(z);
    yf = y_front(z);
    yb = y_back(z);
    hull() {
        translate([-w / 2 + r_rear, yb + r_rear])
            circle(r = r_rear);
        translate([w / 2 - r_rear, yb + r_rear])
            circle(r = r_rear);
        translate([-w / 2 + r_front, yf - r_front])
            circle(r = r_front);
        translate([w / 2 - r_front, yf - r_front])
            circle(r = r_front);
    }
}

module arm_slice(z) {
    translate([0, 0, z])
        linear_extrude(height = slice_h)
            arm_slice_2d(z);
}

module arm_loft() {
    zs = [
        42, 50, 60, 72, 85, 98, 110, 122, 136, 150, 164,
        178, 192, 206, 220, 234, 246, 258, 268, 278, 288,
        298, 308, 318, 328, 338, 348, 355
    ];
    for (i = [0 : len(zs) - 2])
        hull() {
            arm_slice(zs[i]);
            arm_slice(zs[i + 1]);
        }
}

module handle_cut() {
    translate([0, handle_cy, handle_cz])
        rotate([0, 90, 0])
            linear_extrude(height = arm_w_flare + 40, center = true)
                scale([handle_rz, handle_ry])
                    circle(d = 2);
}

/**
 * 前缘燕尾槽：从载物台侧切进立柱，给滑座。
 */
module dovetail_cut() {
    z0 = 72;
    z1 = 252;
    zm = (z0 + z1) / 2;
    yf = y_front(160);
    hull() {
        translate([0, yf - 0.2, zm])
            cube([dovetail_w + 5, 0.4, z1 - z0], center = true);
        translate([0, yf - dovetail_depth, zm])
            cube([dovetail_w, 0.4, z1 - z0], center = true);
    }
}

module z_shaft_cut() {
    translate([0, arm_z_axis_y(), z_axis_z])
        rotate([0, 90, 0])
            cylinder(d = 14, h = arm_w_flare + 80, center = true);
}

module base_casting() {
    hull() {
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (base_w / 2 - 18), sy * (base_d / 2 - 18), 0])
                cylinder(r = 18, h = base_h);
    }
    translate([0, 16, base_h - 1])
        cylinder(d = 46, h = 9);
}

module base_cuts() {
    translate([0, 16, base_h + 4])
        cylinder(d = 36, h = 8);
    // 开关、调光：正视目镜时在右侧（−X）
    translate([-base_w / 2 + 2, 48, 18])
        cube([8, 22, 14], center = true);
    translate([-base_w / 2 + 1, 18, 18])
        cube([6, 28, 8], center = true);
    translate([0, y_back(18) - 2, 18])
        rotate([90, 0, 0])
            cylinder(d = 9.5, h = 18);
}

module arm_root() {
    hull() {
        arm_slice(42);
        translate([0, 0, 12])
            linear_extrude(height = 4)
                offset(delta = 4)
                    arm_slice_2d(42);
        translate([0, (y_back(42) + front_y0) / 2, 8])
            cube([arm_w_flare, 28, 4], center = true);
    }
}

module z_bosses() {
    for (s = [-1, 1])
        translate([s * (arm_w / 2 + z_boss_h / 2), arm_z_axis_y(), z_axis_z])
            rotate([0, 90, 0])
                difference() {
                    cylinder(d = z_boss_d, h = z_boss_h, center = true);
                    cylinder(d = 14, h = z_boss_h + 2, center = true);
                }
}

module head_seat() {
    y = (y_front(z_top) + y_back(z_top)) / 2;
    translate([0, y, z_top - 2])
        cylinder(d = 72, h = 10);
}

module arm_metal() {
    difference() {
        union() {
            base_casting();
            arm_root();
            arm_loft();
            head_seat();
        }
        base_cuts();
        handle_cut();
        dovetail_cut();
        z_shaft_cut();
    }
}

// ----- Z 粗微同轴（卡尺 A 组） -----

/**
 * 滚花圆柱：外圈竖棱，模拟粗调手轮。
 */
module knurled_cyl(d, h, n = 28) {
    translate([0, 0, -h / 2]) {
        cylinder(d = d - 1.6, h = h);
        for (i = [0 : n - 1])
            rotate(i * 360 / n)
                translate([d / 2 - 0.7, 0, h / 2])
                    cube([1.4, 2.4, h], center = true);
    }
}

/**
 * 微调刻度盘（贴在粗调外端面外的薄环）。
 */
module scale_ring() {
    difference() {
        cylinder(d = 38, h = 1.6);
        translate([0, 0, -0.2])
            cylinder(d = 21, h = 2.1);
    }
    for (i = [0 : 31])
        rotate(i * 11.25)
            translate([16.5, 0, 0.8])
                cube([2.2, i % 4 == 0 ? 0.6 : 0.3, 1.2], center = true);
}

/**
 * 灰色 10 槽圆弧毂 + 杯底 M3 螺母。轴向从粗调外端面伸出 13mm。
 */
module grey_hub() {
    difference() {
        linear_extrude(height = z_hub_h)
            hub_2d();
        translate([0, 0, -0.05])
            cylinder(d = z_hub_od - 2 * z_wall_t, h = z_cup_depth + 0.05);
    }
    color([0.55, 0.52, 0.42])
        translate([0, 0, 1.2])
            cylinder(d = z_nut_af / cos(30), h = 2.4, $fn = 6);
}

/**
 * 左侧（+X）留下的锥形蓝套，手拧微调。
 */
module blue_sleeve() {
    // 大端朝臂（z=0），小端朝手指。卡尺小端 24 / 大端 28.5。
    difference() {
        cylinder(d1 = 28.5, d2 = 24, h = 18);
        translate([0, 0, -0.2])
            cylinder(d = 19, h = 18.4);
    }
}

/**
 * 把剖分轮套到灰毂上。05 的局部 +Z 为毂轴。
 */
module split_pulley_on_hub() {
    translate([0, 0, z_pulley_standoff]) {
        color([0.9, 0.45, 0.1])
            difference() {
                clamp_parts();
                split_kerf();
            }
        color([0.15, 0.45, 0.75])
            difference() {
                rim_parts();
                split_kerf();
            }
    }
}

/**
 * 一侧粗调轮：衬套 + 滚花大轮。side = ±1，从臂侧面沿该符号向外。
 */
module coarse_stack(side) {
    ay = arm_z_axis_y();
    az = z_axis_z;
    translate([x_out(side, z_collar_h / 2), ay, az])
        rotate([0, 90, 0])
            color([0.12, 0.12, 0.14])
                cylinder(d = 28, h = z_collar_h, center = true);
    translate([x_out(side, z_collar_h + z_coarse_h / 2), ay, az])
        rotate([0, 90 * side, 0])
            color([0.22, 0.22, 0.24])
                knurled_cyl(z_coarse_od, z_coarse_h);
}

/**
 * 右侧（−X）：粗调 + 刻度环 + 裸灰毂 + 剖分轮。
 */
module z_knobs_right() {
    ay = arm_z_axis_y();
    az = z_axis_z;
    side = z_side;
    coarse_stack(side);
    translate([x_from_arm(z_collar_h + z_coarse_h), ay, az])
        rotate([0, 90 * side, 0]) {
            color([0.82, 0.82, 0.84])
                scale_ring();
            color([0.5, 0.5, 0.54])
                grey_hub();
            if (show_split_pulley)
                split_pulley_on_hub();
        }
}

/**
 * 左侧（+X）：粗调 + 蓝套，继续手拧。
 */
module z_knobs_left() {
    ay = arm_z_axis_y();
    az = z_axis_z;
    coarse_stack(1);
    translate([x_from_arm_left(z_collar_h + z_coarse_h), ay, az])
        rotate([0, 90, 0])
            color([0.2, 0.38, 0.72])
                blue_sleeve();
}

function x_from_arm_left(dist) = 1 * (arm_w / 2 + dist);

module z_focus_knobs() {
    z_knobs_right();
    z_knobs_left();
}

/**
 * 完整铸造 + 两侧 Z 手轮。
 */
module arm_casting() {
    color([0.86, 0.83, 0.76])
        arm_metal();
    color([0.18, 0.18, 0.2])
        z_bosses();
    color([0.12, 0.12, 0.12]) {
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (base_w / 2 - 22), sy * (base_d / 2 - 22), -2])
                cylinder(d = 14, h = 4);
    }
    z_focus_knobs();
    translate([0, head_seat_y(), head_seat_top_z()])
        trinocular_stack();
    stage_assembly();
}

module arm_section_z() {
    color([0.22, 0.42, 0.68])
        linear_extrude(height = 1.2)
            arm_slice_2d(z_axis_z);
    color([0.15, 0.15, 0.18])
        translate([0, arm_z_axis_y(), 0])
            cylinder(d = 14, h = 1.4);
}

module arm_profile_yz() {
    intersection() {
        arm_casting();
        cube([1.6, 400, 800], center = true);
    }
}

if (part == "section")
    arm_section_z();
else if (part == "profile")
    arm_profile_yz();
else if (part == "stage") {
    stage_assembly();
    color([0.86, 0.83, 0.76, 0.22])
        arm_metal();
}
else if (part == "head") {
    translate([0, head_seat_y(), head_seat_top_z()])
        trinocular_stack();
    color([0.86, 0.83, 0.76, 0.25])
        arm_metal();
}
else if (part == "knobs") {
    z_focus_knobs();
    color([0.86, 0.83, 0.76, 0.35])
        arm_metal();
}
else
    arm_casting();
