// N-117M 10 寸屏：手机支架式矩形框 + 横梁抱箍。
// 数字与 ../dims.json 的 screen / beam_clamp 同步。禁止 use openscad_V1。
// 上边开口可滑入；背面顶条把 U 收成矩形，接到竖脊；竖脊在钢板后面。
// 导出：openscad -D 'part="clamp"'  -o ../stl/beam_clamp.stl
//       openscad -D 'part="tray_l"' -o ../stl/screen_tray_l.stl
//       openscad -D 'part="tray_r"' -o ../stl/screen_tray_r.stl

part = "preview"; // preview | clamp | tray_l | tray_r

$fn = 40;

// --- screen ---
face_w = 258.0;
face_h = 168.0;
glass_t = 2.3;
steel_proud = 4.0;
steel_inset_tb = 13.0;
edge_clear = 0.4;
front_lip = 2.0;
baffle_side = 3.5;
baffle_bottom = 10.0;
baffle_bottom_deg = 60.0;
rail_out = 14.0;
wall_t = 3.0;
lap = 12.0;
cable_gap = 24.0;
m3_through = 3.2;

inner_w = face_w + 2 * edge_clear;
inner_h = face_h + 2 * edge_clear;
win_w = face_w - 2 * steel_inset_tb;
win_h = face_h - 2 * steel_inset_tb;
bottom_inset = baffle_bottom / tan(baffle_bottom_deg);
ox = face_w / 2 + edge_clear;

// --- beam clamp ---
beam_w_caliper = 57.5;
print_clear = 1.5;
cavity_w = beam_w_caliper + 2 * print_clear;
wall = 6.0;
len_along = 40.0;
wrap_down = 22.0;
m4_tap_d = 3.6;
standoff = 45.0;
tilt_from_vert = 45.0;
open_toward = "arm";
slide_slot = 30.0;
plate_t = 6.0;
bar_w = 16.0;
// 竖脊在钢板后面，留 0.5 mm 让钢板坐进槽
spine_z = -steel_proud - plate_t / 2 - 0.5;

hole_bot_y1 = -4.5;
hole_bot_y2 = -10.5;
hole_top_y1 = face_h + 4.0;
hole_top_y2 = face_h + 10.0;
slide_y1 = face_h / 2 - 6;
slide_y2 = face_h / 2 + 6;

/**
 * 半件沿屏宽的 x 范围（中线搭接 lap）。
 */
function half_x0(side) = (side < 0) ? -(ox + rail_out) : -lap;
function half_x1(side) = (side < 0) ? lap : (ox + rail_out);

/**
 * 底边 60° 实心楔截面（YZ）。z=0 为钢板上平面。
 */
module bottom_baffle_2d() {
    h = baffle_bottom;
    inset = bottom_inset;
    polygon([
        [-rail_out, 0],
        [front_lip, 0],
        [front_lip + inset, h],
        [-rail_out, h]
    ]);
}

/**
 * 底挡半件：楔在中线搭接。伸进开孔小于钢板 13 mm 边距。
 */
module bottom_fence(side) {
    x0 = (side < 0) ? -(ox + rail_out) : 0;
    x1 = (side < 0) ? 0 : (ox + rail_out);
    translate([x0, 0, 0])
        rotate([90, 0, 90])
            linear_extrude(height = x1 - x0)
                bottom_baffle_2d();
}

/**
 * 侧挡：两内沿间距 = 玻璃宽 + 两侧间隙。墙在玻璃外沿外侧，不翻进开孔。
 */
module side_fence(side) {
    translate([
        side * (ox + rail_out / 2),
        inner_h / 2,
        glass_t / 2
    ])
        cube([rail_out, inner_h + rail_out, glass_t], center = true);
    translate([
        side * (ox + wall_t / 2),
        inner_h / 2,
        (glass_t + baffle_side) / 2
    ])
        cube([wall_t, inner_h + rail_out, glass_t + baffle_side], center = true);
    // 侧边背面肋，在钢板区以外，把 U 收成矩形
    translate([
        side * (ox + rail_out / 2),
        inner_h / 2,
        spine_z
    ])
        cube([rail_out, inner_h + rail_out, plate_t], center = true);
}

/**
 * 顶条半件：在玻璃上方、钢板后面，接到竖脊。正面中间留排线口。
 */
module top_bar(side) {
    x0 = half_x0(side);
    x1 = half_x1(side);
    translate([(x0 + x1) / 2, face_h + rail_out / 2, spine_z])
        cube([x1 - x0, rail_out, plate_t], center = true);
    // 正面不封顶（cable_gap），屏从上方滑入；矩形靠背面顶条。
}

/**
 * 竖脊半件：钢板后面，下接底框、上接顶条，抱箍骑滑。
 */
module back_spine(side) {
    x0 = (side < 0) ? -bar_w / 2 : 0;
    x1 = (side < 0) ? 0 : bar_w / 2;
    h = face_h + rail_out;
    difference() {
        translate([(x0 + x1) / 2, h / 2 - rail_out / 2, spine_z])
            cube([x1 - x0, h + rail_out / 2, plate_t], center = true);
        hull() {
            translate([0, face_h / 2 - slide_slot / 2, spine_z])
                rotate([0, 90, 0])
                    cylinder(d = m3_through, h = bar_w + 6, center = true);
            translate([0, face_h / 2 + slide_slot / 2, spine_z])
                rotate([0, 90, 0])
                    cylinder(d = m3_through, h = bar_w + 6, center = true);
        }
    }
}

/**
 * 底边背面肋，矩形的底边。
 */
module bottom_back(side) {
    x0 = half_x0(side);
    x1 = half_x1(side);
    translate([(x0 + x1) / 2, -rail_out / 2, spine_z])
        cube([x1 - x0, rail_out, plate_t], center = true);
}

/**
 * 搭接处切掉一半厚度，避免对半叠成双倍。
 */
module lap_step(side, yc, zc, thick) {
    zh = thick / 2 + 0.2;
    zcut = (side < 0) ? (zc + thick / 4) : (zc - thick / 4);
    translate([side * lap / 2, yc, zcut])
        cube([lap + 0.3, rail_out + 1, zh], center = true);
}

/**
 * 托盘半件：L 形框 + 顶条 + 竖脊。
 */
module screen_tray(side) {
    difference() {
        union() {
            bottom_fence(side);
            side_fence(side);
            top_bar(side);
            back_spine(side);
            bottom_back(side);
        }
        lap_step(side, face_h + rail_out / 2, spine_z, plate_t);
        lap_step(side, -rail_out / 2, spine_z, plate_t);
        for (yy = [hole_bot_y1, hole_bot_y2])
            translate([0, yy, -12])
                cylinder(d = m3_through, h = 28);
        for (yy = [hole_top_y1, hole_top_y2])
            translate([0, yy, spine_z])
                cylinder(d = m3_through, h = plate_t + 4, center = true);
    }
}

/**
 * 倒 U：−Z 不包弓底，±Y 都开口，可从梁后套上。
 */
module beam_saddle() {
    ow = cavity_w + 2 * wall;
    oh = wrap_down + wall;
    difference() {
        translate([0, 0, wall - oh / 2])
            cube([ow, len_along, oh], center = true);
        translate([0, 0, -wrap_down / 2 - 0.05])
            cube([cavity_w, len_along + 2, wrap_down], center = true);
        for (s = [-1, 1])
            translate([s * (cavity_w / 2 + wall / 2), 0, -wrap_down / 2])
                rotate([0, 90, 0])
                    cylinder(d = m4_tap_d, h = wall + 4, center = true);
    }
}

/**
 * 抱箍：左右耳夹竖脊，倒 U 沿梁开口。
 */
module beam_clamp_solid() {
    plate_y = face_h / 2;
    ear_w = 14;
    ear_x = bar_w / 2 + 0.6 + ear_w / 2;
    difference() {
        union() {
            for (s = [-1, 1])
                translate([s * ear_x, plate_y, spine_z])
                    cube([ear_w, 36, plate_t], center = true);
            hull() {
                translate([0, plate_y, spine_z - plate_t / 2 - 1])
                    cube([bar_w + 16, 18, 2], center = true);
                translate([0, plate_y, -standoff + wall / 2])
                    cube([20, 18, wall], center = true);
            }
            translate([0, plate_y, -standoff])
                beam_saddle();
        }
        for (yy = [slide_y1, slide_y2])
            translate([0, yy, spine_z])
                rotate([0, 90, 0])
                    cylinder(d = m3_through, h = 2 * ear_x + 20, center = true);
    }
}

/**
 * 玻璃 / 钢板两个立方体，预览时套进框里。
 */
module screen_cubes() {
    color([0.2, 0.7, 0.35, 0.28])
        translate([0, face_h / 2, glass_t / 2])
            cube([face_w, face_h, glass_t], center = true);
    color([0.45, 0.48, 0.5, 0.45])
        translate([0, steel_inset_tb + win_h / 2, -steel_proud / 2])
            cube([win_w - 4, win_h, steel_proud], center = true);
}

/**
 * 装配预览。
 */
module beam_clamp_preview() {
    color([0.25, 0.45, 0.7])
        screen_tray(-1);
    color([0.2, 0.55, 0.45])
        screen_tray(1);
    color([0.18, 0.18, 0.2])
        beam_clamp_solid();
    screen_cubes();
}

if (part == "clamp")
    beam_clamp_solid();
else if (part == "tray_l")
    screen_tray(-1);
else if (part == "tray_r")
    screen_tray(1);
else
    beam_clamp_preview();
