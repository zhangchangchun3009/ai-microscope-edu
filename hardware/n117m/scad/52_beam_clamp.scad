// N-117M 10 寸屏：左右平框拧到中间竖条上；座板夹耳拧竖条，倒 U 圆舌可调角度。
// 数字与 ../dims.json 的 screen / beam_clamp 同步。禁止 use openscad_V1。
// 框板平放打印（背面朝床、挡板朝上）。竖条单独打。
// 导出：openscad -D 'part="clamp"'  -o ../stl/beam_clamp.stl
//       openscad -D 'part="saddle"' -o ../stl/beam_saddle.stl
//       openscad -D 'part="bar"'    -o ../stl/beam_bar.stl
//       openscad -D 'part="tray_l"' -o ../stl/screen_tray_l.stl
//       openscad -D 'part="tray_r"' -o ../stl/screen_tray_r.stl
//       openscad -D 'part="tray_r_patch"' -o ../stl/screen_tray_r_patch.stl
//       part="explode" 拆开；默认 preview 是拼好的总装（鞍按 −45°）。

part = "preview"; // preview | explode | clamp | saddle | bar | tray_l | tray_r | tray_r_patch

$fn = 40;

face_w = 258.0;
face_h = 168.0;
glass_t = 2.3;
steel_proud = 4.0;
steel_pocket_d = 5.0;
steel_clear = 2.0;
steel_inset_tb = 13.0;
edge_clear = 0.4;
front_lip = 2.0;
baffle_side = 3.5;
baffle_bottom = 10.0;
baffle_bottom_deg = 60.0;
rail_out = 14.0;
wall_t = 3.0;
outer_extra = 4.0;
seam_overlap = 2.0;
print_left_cover = 128.0;
cable_gap = 24.0;
m3_through = 3.2;
m3_hex_len = 30;
m3_nut_af = 5.5;
m3_nut_h = 2.4;
m3_nut_pocket_clear = 0.4;
m3_nut_pocket_d = 3.0;
m3_head_h = 2.0;
m3_head_slot_d = 7.2;

inner_h = face_h + 2 * edge_clear;
win_w = 228.0 + 2 * steel_clear;
win_h = 142.0 + 2 * steel_clear;
bottom_inset = baffle_bottom / tan(baffle_bottom_deg);
stack_h = glass_t + steel_pocket_d;
ox = face_w / 2 + edge_clear;
ix = win_w / 2;
explode_x = 28.0;
explode_z = 55.0;

beam_w_caliper = 57.5;
print_clear = 0.5;
cavity_w = beam_w_caliper + 2 * print_clear;
wall = 6.0;
len_along = 40.0;
wrap_down = 15.0;
m4_tap_d = 3.6;
standoff = 45.0;
tilt_from_vert = 45.0;
tongue_r = 16.0;
tongue_t = 5.4;
ear_t = 6.0;
hinge_gap = 0.4;
arc_r = 11.0;
arc_a0 = 0;
arc_a1 = -90;
arc_n = 8;
hinge_cut_h = tongue_t + 4;
hinge_drop = 28.0;
hinge_back = 12.0;
open_toward = "arm";
slide_slot = 30.0;
plate_t = 6.0;
bar_w = 22.0;
bar_hole_x = bar_w / 4;
slide_y1 = face_h / 2 - 6;
slide_y2 = face_h / 2 + 6;

hole_bot_y1 = -4.5;
hole_bot_y2 = -10.5;
hole_top_y1 = face_h + 4.0;
hole_top_y2 = face_h + 10.0;

plate_y = face_h / 2;
back_z = -2 * plate_t;
pivot_y = plate_y - hinge_drop;
pivot_z = back_z - plate_t - hinge_back;
ear_x = tongue_t / 2 + hinge_gap + ear_t / 2;
saddle_tilt = -tilt_from_vert;

/**
 * 半框外沿。正式件中线重叠 seam_overlap，避免收缩后底挡对不上。
 */
function half_x0(side) = (side < 0) ? -(ox + outer_extra) : -seam_overlap;
function half_x1(side) = (side < 0) ? seam_overlap : (ox + outer_extra);

/**
 * 已打左半包 128 mm 时，右补救件内沿（屏宽中点为 0）。
 */
function patch_r_x0() = -(face_w / 2 - print_left_cover);

/**
 * 框板 2D：外矩形减钢板镂空，上边中留排线口。
 */
module tray_ring_2d(x0, x1) {
    y0 = -rail_out;
    y1 = face_h + rail_out;
    sy0 = (face_h - win_h) / 2;
    difference() {
        translate([x0, y0])
            square([x1 - x0, y1 - y0]);
        translate([-ix, sy0])
            square([2 * ix, win_h]);
        translate([-cable_gap / 2, face_h - steel_inset_tb])
            square([cable_gap, steel_inset_tb]);
    }
}

/**
 * 底边：先直角井放下玻璃+钢板总厚，再 60° 斜挡玻璃下沿。
 */
module bottom_baffle_2d() {
    polygon([
        [-rail_out, 0],
        [front_lip, 0],
        [front_lip, stack_h],
        [front_lip + bottom_inset, stack_h + baffle_bottom],
        [-rail_out, stack_h + baffle_bottom]
    ]);
}

/**
 * 已打左半的旧 60° 楔。补救右半必须同高，否则屏会左右歪。
 */
module bottom_baffle_printed_2d() {
    polygon([
        [-rail_out, 0],
        [front_lip, 0],
        [front_lip + bottom_inset, baffle_bottom],
        [-rail_out, baffle_bottom]
    ]);
}

/**
 * M3 六角螺母沉窝。对边 af + 打印间隙，沿 +Z 挤出。
 */
module hex_nut_pocket() {
    flat = m3_nut_af + m3_nut_pocket_clear;
    cylinder(h = m3_nut_pocket_d, d = flat / cos(30), $fn = 6);
}

/**
 * 中间竖条（单独打印）：贴在左右框背面，左右框顶/底各拧上来，抱箍再拧背面。
 * 框–条螺母沉在竖条背面；抱箍从钢板窗侧穿入，正面滑槽沉头以免顶钢板。
 */
module mid_bar() {
    h = face_h + 2 * rail_out;
    difference() {
        translate([0, face_h / 2, -plate_t - plate_t / 2])
            cube([bar_w, h, plate_t], center = true);
        for (s = [-1, 1], yy = [hole_bot_y1, hole_top_y1]) {
            translate([s * bar_hole_x, yy, -plate_t - plate_t / 2])
                cylinder(d = m3_through, h = plate_t + 2, center = true);
            translate([s * bar_hole_x, yy, -2 * plate_t])
                rotate([180, 0, 0])
                    hex_nut_pocket();
        }
        hull() {
            translate([0, face_h / 2 - slide_slot / 2, -plate_t - plate_t / 2])
                cylinder(d = m3_through, h = plate_t + 2, center = true);
            translate([0, face_h / 2 + slide_slot / 2, -plate_t - plate_t / 2])
                cylinder(d = m3_through, h = plate_t + 2, center = true);
        }
        hull() {
            translate([0, face_h / 2 - slide_slot / 2, -plate_t])
                rotate([180, 0, 0])
                    cylinder(d = m3_head_slot_d, h = m3_head_h + 0.4);
            translate([0, face_h / 2 + slide_slot / 2, -plate_t])
                rotate([180, 0, 0])
                    cylinder(d = m3_head_slot_d, h = m3_head_h + 0.4);
        }
    }
}

/**
 * 半框：6 mm 平板 + 玻璃外沿挡板。正式件中线重叠；螺丝穿过本框打进竖条。
 * well=true 用直角井+60°；false 用已打件同款旧楔。
 */
module tray_ring(side, x0, x1, well = true) {
    difference() {
        union() {
            translate([0, 0, -plate_t])
                linear_extrude(height = plate_t)
                    tray_ring_2d(x0, x1);
            translate([
                side * (ox + wall_t / 2),
                inner_h / 2,
                (glass_t + baffle_side) / 2
            ])
                cube([wall_t, inner_h + rail_out, glass_t + baffle_side], center = true);
            translate([x0, 0, 0])
                rotate([90, 0, 90])
                    linear_extrude(height = x1 - x0)
                        if (well)
                            bottom_baffle_2d();
                        else
                            bottom_baffle_printed_2d();
        }
        for (yy = [hole_bot_y1, hole_top_y1])
            translate([side * bar_hole_x, yy, -plate_t - 1])
                cylinder(d = m3_through, h = plate_t + stack_h + baffle_bottom + 4);
    }
}

/**
 * 正式托盘半件。
 */
module screen_tray(side) {
    tray_ring(side, half_x0(side), half_x1(side), well = true);
}

/**
 * 右补救件：包住已打左半剩下的 130 mm。底槽与已打件同款旧楔，不当量产。
 */
module screen_tray_r_patch() {
    tray_ring(1, patch_r_x0(), half_x1(1), well = false);
}

/**
 * 倒 U 内腔：坐梁顶，两端开口。
 */
module beam_saddle_cavity() {
    translate([0, 0, -wrap_down / 2 - 0.05])
        cube([cavity_w, len_along + 2, wrap_down], center = true);
}

/**
 * 倒 U：−Z 不包弓底，±Y 开口。铰链局部坐标原点在轴心。
 */
module beam_saddle() {
    ow = cavity_w + 2 * wall;
    oh = wrap_down + wall;
    difference() {
        translate([0, 0, wall - oh / 2])
            cube([ow, len_along, oh], center = true);
        beam_saddle_cavity();
        for (s = [-1, 1])
            translate([s * (cavity_w / 2 + wall / 2), 0, -wrap_down / 2])
                rotate([0, 90, 0])
                    cylinder(d = m4_tap_d, h = wall + 4, center = true);
    }
}

/**
 * 圆舌上的锁角槽：0°（朝抱箍）到 −90°。总装 −45° 时锁孔对准 0°，对侧开到 −180° 不必。
 * 分段 hull，避免一次凸包挖空圆舌。已打座板锁孔在 −45°，落在此槽内。
 */
module hinge_arc_slot() {
    for (i = [0 : arc_n - 1]) {
        a0 = arc_a0 + (arc_a1 - arc_a0) * i / arc_n;
        a1 = arc_a0 + (arc_a1 - arc_a0) * (i + 1) / arc_n;
        hull() {
            for (a = [a0, a1])
                rotate([a, 0, 0])
                    translate([0, 0, -arc_r])
                        rotate([0, 90, 0])
                            cylinder(d = m3_through, h = hinge_cut_h, center = true);
        }
    }
}

/**
 * 轴孔与锁角孔沿 X。锁孔仍在 −45°，对准已打座板，落在下半圆弧槽内。
 */
module hinge_through_holes(h) {
    rotate([0, 90, 0])
        cylinder(d = m3_through, h = h, center = true);
    rotate([saddle_tilt, 0, 0])
        translate([0, 0, -arc_r])
            rotate([0, 90, 0])
                cylinder(d = m3_through, h = h, center = true);
}

/**
 * 倒 U + 圆舌。打印件原点在铰链轴，0° 时鞍沿 −Z。
 * 圆舌到倒 U 的肋沿 X 必须与圆舌同厚，否则夹不进已打夹耳。
 */
module saddle_solid() {
    difference() {
        union() {
            rotate([0, 90, 0])
                cylinder(d = 2 * tongue_r, h = tongue_t, center = true);
            hull() {
                rotate([0, 90, 0])
                    cylinder(d = 14, h = tongue_t, center = true);
                translate([0, 0, -(tongue_r + 6)])
                    cube([tongue_t, 16, 6], center = true);
            }
            translate([0, 0, -(tongue_r + 8)])
                beam_saddle();
        }
        rotate([0, 90, 0])
            cylinder(d = m3_through, h = tongue_t + 4, center = true);
        hinge_arc_slot();
        // hull 会填回内腔；再切一次。
        translate([0, 0, -(tongue_r + 8)])
            beam_saddle_cavity();
    }
}

/**
 * 座板 + 两片夹耳。拧在竖条上，夹住圆舌。
 */
module beam_clamp_plate() {
    x_nut = ear_x + ear_t / 2;
    difference() {
        union() {
            translate([0, plate_y, back_z - plate_t / 2])
                cube([bar_w + 12, 36, plate_t], center = true);
            for (s = [-1, 1]) {
                hull() {
                    translate([s * ear_x, plate_y - 16, back_z - plate_t / 2])
                        cube([ear_t, 8, plate_t], center = true);
                    translate([s * ear_x, pivot_y, pivot_z])
                        rotate([0, 90, 0])
                            cylinder(d = 2 * tongue_r, h = ear_t, center = true);
                }
            }
        }
        for (yy = [slide_y1, slide_y2]) {
            translate([0, yy, back_z - plate_t / 2])
                cylinder(d = m3_through, h = plate_t + 4, center = true);
            translate([0, yy, back_z - plate_t])
                rotate([180, 0, 0])
                    hex_nut_pocket();
            translate([0, yy, back_z - plate_t])
                rotate([180, 0, 0])
                    cylinder(d = m3_through, h = 16);
        }
        translate([0, pivot_y, pivot_z])
            hinge_through_holes(2 * ear_x + ear_t + 4);
        translate([x_nut, pivot_y, pivot_z]) {
            rotate([0, -90, 0])
                hex_nut_pocket();
            rotate([0, 90, 0])
                cylinder(d = m3_through, h = 14);
            rotate([saddle_tilt, 0, 0])
                translate([0, 0, -arc_r]) {
                    rotate([0, -90, 0])
                        hex_nut_pocket();
                    rotate([0, 90, 0])
                        cylinder(d = m3_through, h = 14);
                }
        }
    }
}

/**
 * 鞍放到轴上并转到预览角（绕 X，朝屏下边）。
 */
module saddle_placed() {
    translate([0, pivot_y, pivot_z])
        rotate([saddle_tilt, 0, 0])
            saddle_solid();
}

/**
 * 座板 + 预览角的鞍（给 layout 用）。
 */
module beam_clamp_solid() {
    beam_clamp_plate();
    saddle_placed();
}

/**
 * 总装。
 */
module beam_clamp_assembled() {
    color([0.25, 0.45, 0.7])
        screen_tray(-1);
    color([0.2, 0.55, 0.45])
        screen_tray(1);
    color([0.75, 0.45, 0.15])
        mid_bar();
    color([0.18, 0.18, 0.2])
        beam_clamp_plate();
    color([0.55, 0.22, 0.18])
        saddle_placed();
    color([0.2, 0.7, 0.35, 0.28])
        translate([0, face_h / 2, glass_t / 2])
            cube([face_w, face_h, glass_t], center = true);
    color([0.45, 0.48, 0.5, 0.45])
        translate([0, face_h / 2, -steel_proud / 2])
            cube([228.0, 142.0, steel_proud], center = true);
}

/**
 * 五个打印件拆开，仍按拼接相对位置。
 */
module beam_clamp_preview() {
    color([0.25, 0.45, 0.7])
        translate([-explode_x, 0, 0])
            screen_tray(-1);
    color([0.2, 0.55, 0.45])
        translate([explode_x, 0, 0])
            screen_tray(1);
    color([0.75, 0.45, 0.15])
        translate([0, 0, -explode_z / 2])
            mid_bar();
    color([0.18, 0.18, 0.2])
        translate([0, 0, -explode_z])
            beam_clamp_plate();
    color([0.55, 0.22, 0.18])
        translate([0, -40, -explode_z])
            saddle_placed();
}

if (part == "clamp")
    beam_clamp_plate();
else if (part == "saddle")
    saddle_solid();
else if (part == "bar")
    mid_bar();
else if (part == "tray_l")
    screen_tray(-1);
else if (part == "tray_r")
    screen_tray(1);
else if (part == "tray_r_patch")
    screen_tray_r_patch();
else if (part == "explode")
    beam_clamp_preview();
else
    beam_clamp_assembled();
