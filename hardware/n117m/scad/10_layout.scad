// N-117M 总体布局示意
//
// 镜臂见 20_arm.scad（后表面圆角 + 右视 C 形）。主板盒见 50/51。屏支架 52。
// 坐标：z=0 桌面；+Y 朝目镜（前）；+X 朝右。
// part：arm | all | body | drive | box | screen

use <20_arm.scad>
use <40_stage.scad>
use <50_board_box.scad>
use <51_arm_clamp.scad>
use <52_beam_clamp.scad>

part = "box"; // arm | all | body | drive | box | screen

$fn = 40;

base_w = 167;
base_d = 224;
base_h = 42;
h_top  = 430;

arm_w = arm_width();
arm_y = y_back(90);

stage_x = 132;
stage_y = 142;
stage_t = 12;
stage_y0 = 18;            // 台中心略靠前

z_hub_od     = 20;
z_hub_h      = 13;
z_coarse_od  = 46;
z_coarse_h   = 22;
z_hub_bottom = 100;       // A/B：微调毂最低点距桌
z_axis_z     = z_hub_bottom + z_hub_od / 2;
z_axis_y     = arm_z_axis_y();
arm_side     = arm_w / 2;
hub_to_arm   = 50;        // A10 中值 47–52
z_hub_x      = z_hub_outer_x();
z_belt_x     = z_hub_x - z_knob_side() * z_hub_h / 2;

xy_up_od    = 29;
xy_lo_od    = 26;
xy_up_h     = 20;
xy_lo_h     = 15;
xy_gap      = 2;
xy_axis_off = 19;         // B6 中值 18–20
// 中间焦：87 与 64 的平均（相对桌面）
xy_lo_bottom = (87 + 64) / 2;
xy_ax = xy_axis_x();
xy_ay = xy_axis_y();
stage_z = stage_top_z();

nema        = [42, 42, 38];
mot_pulley  = 12.2;
z_pulley_od = 30.0;       // GT2 48 齿示意
belt_w      = 6.0;
belt_t      = 1.4;

/**
 * 闭环皮带截面：两圆外一圈。c1/c2 为该平面内的二维圆心。
 */
module belt_loop_2d(c1, c2, d1, d2, t = belt_t) {
    difference() {
        hull() {
            translate(c1) circle(d = d1 + 2 * t);
            translate(c2) circle(d = d2 + 2 * t);
        }
        hull() {
            translate(c1) circle(d = d1);
            translate(c2) circle(d = d2);
        }
    }
}

/**
 * YZ 平面内的皮带（轴线沿 X）。2D 坐标是 [y, z]。
 */
module belt_yz(x, y1, z1, d1, y2, z2, d2) {
    color([0.07, 0.07, 0.08])
        translate([x, 0, 0])
            rotate([90, 0, 90])
                linear_extrude(height = belt_w, center = true)
                    belt_loop_2d([y1, z1], [y2, z2], d1, d2);
}

/**
 * XY 平面内的皮带（轴线沿 Z）。
 */
module belt_xy(z, x1, y1, d1, x2, y2, d2) {
    color([0.07, 0.07, 0.08])
        translate([0, 0, z])
            linear_extrude(height = belt_w, center = true)
                belt_loop_2d([x1, y1], [x2, y2], d1, d2);
}

/**
 * NEMA17 占位。局部 +Z 为出轴，轴端带 20 齿 GT2 示意轮。
 */
module nema17() {
    color([0.18, 0.18, 0.2]) {
        cube(nema, center = true);
        translate([0, 0, nema[2] / 2])
            cylinder(d = 22, h = 2);
        translate([0, 0, nema[2] / 2])
            cylinder(d = 5, h = 22);
        translate([0, 0, nema[2] / 2 + 8])
            cylinder(d = mot_pulley, h = belt_w);
    }
}

function nema_pulley_along() = nema[2] / 2 + 8 + belt_w / 2;

/**
 * 主体：铸造镜臂 + 头/物镜/载物台占位（后两项下一步细化）。
 */
module body_simple() {
    arm_casting();
    color([0.86, 0.83, 0.76]) {
        translate([0, 18, 278])
            cylinder(d = 68, h = 12);
        for (a = [45, 135, 225, 315])
            rotate([0, 0, a])
                translate([20, 0, 254])
                    cylinder(d = 13, h = 26);
    }
}

/**
 * 右 XY 叠套手轮（上 Y / 下 X），挂在台右侧。
 */
module xy_knobs() {
    color([0.2, 0.2, 0.22]) {
        translate([xy_ax, xy_ay, xy_lo_bottom + xy_lo_h / 2])
            cylinder(d = xy_lo_od, h = xy_lo_h, center = true);
        translate([xy_ax, xy_ay, xy_lo_bottom + xy_lo_h + xy_gap + xy_up_h / 2])
            cylinder(d = xy_up_od, h = xy_up_h, center = true);
    }
}

/**
 * Z：剖分轮抱右灰毂；电机在臂后右侧，短皮带共面（静止臂，不随台）。
 */
module drive_z() {
    mot_y = z_axis_y - 62;
    mot_z = z_axis_z + 8;
    // 机身在毂外侧（−X），出轴朝 +X，20 齿轮落在皮带平面
    translate([z_belt_x - nema_pulley_along(), mot_y, mot_z])
        rotate([0, 90, 0])
            nema17();

    belt_yz(
        z_belt_x,
        z_axis_y, z_axis_z, z_pulley_od,
        mot_y, mot_z, mot_pulley
    );
}

/**
 * XY：两层剖分轮示意套在手轮上；电机随台、在台右侧外，轴朝下以免低焦撞底座。
 */
module drive_xy() {
    z_lo = xy_lo_mid_z();
    z_up = xy_up_mid_z();
    mot_x = xy_axis_x() - 36;
    mot_y_lo = xy_axis_y() - 24;
    mot_y_up = xy_axis_y() + 24;

    color([0.9, 0.45, 0.12]) {
        translate([xy_ax, xy_ay, z_lo])
            cylinder(d = xy_lo_od + 4, h = belt_w, center = true);
        translate([xy_ax, xy_ay, z_up])
            cylinder(d = xy_up_od + 4, h = belt_w, center = true);
    }

    // 轴朝下：机身在皮带上方、台外侧，低焦不插底座
    translate([mot_x, mot_y_lo, z_lo + nema_pulley_along()])
        rotate([180, 0, 0])
            nema17();
    translate([mot_x, mot_y_up, z_up + nema_pulley_along()])
        rotate([180, 0, 0])
            nema17();

    belt_xy(z_lo, xy_ax, xy_ay, xy_lo_od + 4, mot_x, mot_y_lo, mot_pulley);
    belt_xy(z_up, xy_ax, xy_ay, xy_up_od + 4, mot_x, mot_y_up, mot_pulley);
}

/**
 * 臂后主板盒与 C 形抱箍（替换旧 electronics_tray 占位）。
 */
clamp_z0 = 188;
clamp_h  = 45;
box_oy   = 50;

/**
 * 抱箍：后表面贴 y_back，底面在 clamp_z0。
 */
module n117m_arm_clamp_placed() {
    zb = y_back(clamp_z0 + clamp_h / 2);
    translate([0, zb, clamp_z0 + clamp_h / 2])
        arm_clamp_solid();
}

/**
 * 盒：盖朝臂。局部 +Y 已朝臂；盖外表面贴矩形板外侧。
 */
module n117m_board_box_placed() {
    zb = y_back(clamp_z0 + clamp_h / 2);
    plate_t = 6;
    translate([0, zb - plate_t - box_oy / 2, clamp_z0 + clamp_h / 2])
        board_box_shell();
}

/**
 * 臂后电控托盘：已由 n117m_board_box_placed 替代，保留以免旧预览脚本引用。
 */
module electronics_tray() {
    n117m_board_box_placed();
}

/**
 * 屏支架示意：骑坐横梁中段（z≈338，避开观察室头端锁紧螺丝）。
 * 托盘局部 Y 沿屏高、+Z 朝玻璃；转 45° 使屏后仰约 45°、面向 +Y。
 */
beam_z = 338;

module n117m_screen_placed() {
    yb = y_back(beam_z);
    yf = y_front(beam_z);
    translate([0, (yb + yf) / 2 + 55, beam_z - 90])
        rotate([45, 0, 0])
            beam_clamp_preview();
}

if (part == "arm") {
    arm_casting();
}
else if (part == "body") {
    body_simple();
}
else if (part == "drive") {
    drive_z();
    drive_xy();
}
else if (part == "box") {
    arm_casting();
    n117m_arm_clamp_placed();
    n117m_board_box_placed();
}
else if (part == "screen") {
    arm_casting();
    n117m_arm_clamp_placed();
    n117m_board_box_placed();
    n117m_screen_placed();
}
else {
    body_simple();
    n117m_arm_clamp_placed();
    n117m_board_box_placed();
    n117m_screen_placed();
}
