// N-117M 镜臂铸造（含底座交接）+ Z 粗微同轴手轮
//
// 坐标：z=0 桌面；+Y 朝目镜（前，载物台一侧）；操作者正视目镜时
// 右手边为 −X。XY / 电机化 Z 都在 −X。
//
// 右视：前缘直线，背面竖直；横梁与后表面圆角接合，梁梢连观察室座与物镜转换器。
// 立柱中间无提手通孔。打开本文件：part = arm | knobs | head | stage | section | profile

use <05_pulley_split.scad>
use <30_head.scad>
use <40_stage.scad>

part = "arm"; // arm | knobs | head | stage | section | profile

$fn = 48;

base_w = 167;
base_d = 224;
base_h = 42;

arm_w         = 57.5;
arm_w_flare   = 74;
r_rear        = 3;    // 后棱小圆角（实物近似直角，16 过大）
r_front       = 5;
front_y0      = -52;  // 立柱前缘（载物台侧）基准
back_y_column = -108; // 背面，近乎竖直线

dovetail_w     = 22;
dovetail_depth = 6;

z_axis_z = 110;
z_boss_d = 30;
z_boss_h = 5;

slice_h = 3.2;

// 横梁（E 组，与 ../dims.json cross_beam 同步）。立柱 loft 停在 C 形肩下。
beam_w         = 57.5;
beam_wrap_max  = 17.0;
beam_join_z    = 240.0;
beam_hyp       = 98.0;
beam_horiz     = 92.0;
beam_r         = 3.0;
beam_bow_r     = 90.0;
axis_from_back = 135.0;
tube_d_contact = 42.0;
contact_z      = 378.0;
z_lo           = 178;   // C 形肩与立柱 loft 重叠
join_fillet    = 14;    // 后表面–梁顶钝角的铸造圆角
bow_n          = 16;

function beam_rise()     = sqrt(beam_hyp * beam_hyp - beam_horiz * beam_horiz);
function beam_tilt()     = acos(beam_horiz / beam_hyp);
function beam_high_z()   = beam_join_z + beam_rise();
function tube_axis_y()   = back_y_column + axis_from_back;
function beam_join_y()   = back_y_column;
function screen_contact_y() = tube_axis_y() - tube_d_contact / 2;
function screen_contact_z() = contact_z;

/**
 * 梁局部 (s, d) 映到世界 Y：s 沿顶面 0..hyp，d 为侧视里相对顶面的坐标（顶 0，弓为负）。
 */
function beam_y(s, d) =
    beam_join_y() + s * cos(beam_tilt()) - d * sin(beam_tilt());

/**
 * 梁局部 (s, d) 映到世界 Z。
 */
function beam_z(s, d) =
    beam_join_z + s * sin(beam_tilt()) + d * cos(beam_tilt());

/**
 * 弓下缘在梁局部里的 d。圆心在跨中下方，中点到顶 beam_wrap_max。
 */
function bow_d(s) =
    -beam_wrap_max - beam_bow_r
    + sqrt(max(0, beam_bow_r * beam_bow_r - pow(s - beam_hyp / 2, 2)));

/** 观察室座上表面（观察头底面落在这里）。 */
function house_top_z() = beam_high_z() + 8;

/** 物镜转换器座下沿。 */
function house_bot_z() = beam_high_z() - 36;

z_top = beam_join_z;

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

/**
 * 某一高度的宽度：根部放宽，z≥90 与横梁卡尺同为 57.5。
 */
function arm_w_at(z) = lookup(z, [
    [0, arm_w_flare],
    [42, 70],
    [90, arm_w],
    [400, arm_w]
]);

/**
 * 后缘：立柱竖直，抱箍贴此后表面。
 */
function y_back(z) = back_y_column;

/**
 * 前缘（载物台侧）：直线，不再拟合 C 弧。
 */
function y_front(z) = front_y0;

function arm_z_axis_y() = (front_y0 + back_y_column) / 2;
function arm_width()    = arm_w;
function arm_front_y()  = front_y0;
function z_knob_side()  = z_side;

/** 镜臂侧面到灰毂外沿，沿 −X。 */
function z_hub_outer_x() =
    z_side * (arm_w / 2 + z_collar_h + z_coarse_h + z_hub_h);

function head_seat_y()     = tube_axis_y();
function head_seat_top_z() = house_top_z();

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
        42, 50, 60, 72, 85, 98, 110, 122, 136, 150, 164, 178
    ];
    for (i = [0 : len(zs) - 2])
        hull() {
            arm_slice(zs[i]);
            arm_slice(zs[i + 1]);
        }
}

/**
 * 前缘燕尾槽：从载物台侧切进立柱，给滑座。
 */
module dovetail_cut() {
    z0 = 72;
    z1 = 232;
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

/**
 * 右视 C 形：立柱肩 + 梁。2D 坐标 x=世界 Y、y=世界 Z。钝角用 join_fillet 圆弧代替尖点。
 */
module arm_c_2d() {
    t  = beam_tilt();
    L  = beam_hyp;
    R  = join_fillet;
    along = R * (1 - sin(t)) / cos(t);
    cx = back_y_column + R;
    cz = beam_join_z + along * sin(t) - R * cos(t);
    tan_y = back_y_column + along * cos(t);
    tan_z = beam_join_z + along * sin(t);
    a0 = 180;
    a1 = atan2(tan_z - cz, tan_y - cx);
    join_arc = [
        for (i = [0 : 8])
            let (a = a0 + (a1 - a0) * i / 8)
                [cx + R * cos(a), cz + R * sin(a)]
    ];
    bow = [
        for (i = [0 : bow_n])
            let (
                s  = L * (1 - i / bow_n),
                d  = bow_d(s),
                yy = beam_y(s, d),
                zz = beam_z(s, d)
            ) if (yy >= front_y0 - 2) [yy, zz]
    ];
    polygon(concat(
        [[back_y_column, z_lo]],
        join_arc,
        [[beam_y(L, 0), beam_z(L, 0)]],
        bow,
        [[front_y0, z_lo]]
    ));
}

/**
 * 把 C 形肩挤成梁宽，左右立面为平面。
 */
module arm_c_solid() {
    rotate([90, 0, 90])
        linear_extrude(height = beam_w, center = true)
            offset(r = beam_r)
                offset(delta = -beam_r)
                    arm_c_2d();
}

/**
 * 梁梢头座：与梁 hulled 成一件。上接观察室，下接物镜转换器。
 */
module head_housing() {
    L = beam_hyp;
    hull() {
        translate([0, beam_y(L, -beam_wrap_max / 2), beam_z(L, -beam_wrap_max / 2)])
            rotate([beam_tilt(), 0, 0])
                cube([beam_w, 22, beam_wrap_max + 8], center = true);
        translate([0, tube_axis_y(), house_top_z() - 16])
            cylinder(d = 74, h = 16);
    }
    hull() {
        translate([0, tube_axis_y(), house_top_z() - 16])
            cylinder(d = 74, h = 8);
        translate([0, tube_axis_y(), house_bot_z()])
            cylinder(d = 52, h = 8);
    }
    translate([37, tube_axis_y() - 6, house_top_z() - 10])
        rotate([0, 90, 0])
            cylinder(d = 12, h = 8);
}

/**
 * 横梁侧视：顶面直线，下缘圆弧弓。中点到顶面 17（抱箍最大下包）。
 */
module beam_bow_2d() {
    L = beam_hyp;
    R = beam_bow_r;
    t = beam_wrap_max;
    a0 = asin((L / 2) / R);
    n = 20;
    arc = [
        for (i = [0 : n])
            let (a = a0 - 2 * a0 * i / n)
                [L / 2 + R * sin(a), -t - R + R * cos(a)]
    ];
    polygon(concat([[0, 0], [L, 0]], arc));
}

/**
 * 横梁铸造：C 形肩（圆角接到后表面）+ 梁梢观察室/转换器座。
 */
module cross_beam() {
    arm_c_solid();
    // 立柱 62 宽接到梁 57.5：在 z_lo 附近 hulled 过渡。
    hull() {
        arm_slice(z_lo);
        intersection() {
            arm_c_solid();
            translate([0, (front_y0 + back_y_column) / 2, z_lo + 8])
                cube([arm_w_flare, 80, 16], center = true);
        }
    }
    head_housing();
}

/**
 * 物镜转换器：挂在头座下，三只物镜朝载物台。
 */
module nosepiece() {
    translate([0, tube_axis_y(), house_bot_z()]) {
        cylinder(d = 58, h = 14);
        for (a = [40, 160, 280])
            rotate([0, 0, a])
                translate([17, 0, 4])
                    rotate([0, 105, 0])
                        cylinder(d1 = 24, d2 = 16, h = 38);
    }
}

/**
 * 三目筒触点：直径 42，给屏上边靠。轴距臂后 135，触点高约 378。
 */
module trinocular_contact() {
    translate([0, tube_axis_y(), contact_z])
        cylinder(d = tube_d_contact, h = 24, center = true);
}

module arm_metal() {
    difference() {
        union() {
            base_casting();
            arm_root();
            arm_loft();
            cross_beam();
        }
        base_cuts();
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
    color([0.55, 0.55, 0.58])
        nosepiece();
    color([0.12, 0.12, 0.14])
        trinocular_contact();
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
