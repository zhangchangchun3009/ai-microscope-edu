// N-117M 臂后 C 形顶丝抱箍 + 矩形板（一件）。
// 后+左右近乎直角，后棱小圆角 r=3。顶丝在左右贴合壁。
// 卡尺约 57.5；内腔 = 57.5 + 两侧各 0.5。禁止 use openscad_V1。
// 导出：openscad -D 'part="clamp"' -o ../stl/arm_clamp.stl

part = "preview"; // preview | clamp

$fn = 40;

inner_w = 57.5;
print_clear = 0.5;
clamp_h = 45.0;
wall = 6.0;
wrap_y = 22.0;
r_rear = 3.0;
plate_x = 70.0;
plate_z = 50.0;
plate_t = 6.0;
plate_pitch = 40.0;
m3_tap_d = 2.4;
m4_tap_d = 3.6;

cavity_w = inner_w + 2 * print_clear;
fillet_r = r_rear + print_clear;

/**
 * XY 内腔：后棱小圆角，开口朝 +Y 让燕尾。
 */
module clamp_cavity_2d() {
    r = fillet_r;
    w = cavity_w;
    hull() {
        translate([-w / 2 + r, r])
            circle(r = r);
        translate([w / 2 - r, r])
            circle(r = r);
        translate([-w / 2, wrap_y - 0.05])
            square([0.1, 0.1]);
        translate([w / 2 - 0.1, wrap_y - 0.05])
            square([0.1, 0.1]);
    }
}

/**
 * 内腔外偏 wall。
 */
module clamp_outer_2d() {
    offset(delta = wall)
        clamp_cavity_2d();
}

/**
 * C 形与后侧矩形板一件。左右各一颗 M4 顶丝；板上 4×M3 自攻底孔对盖。
 */
module arm_clamp_solid() {
    difference() {
        union() {
            linear_extrude(height = clamp_h, center = true)
                difference() {
                    clamp_outer_2d();
                    clamp_cavity_2d();
                    translate([0, wrap_y + 40])
                        square([200, 80], center = true);
                }
            translate([0, -plate_t / 2, 0])
                cube([plate_x, plate_t, plate_z], center = true);
        }
        h = plate_pitch / 2;
        for (x = [-h, h], z = [-h, h])
            translate([x, -plate_t / 2, z])
                rotate([90, 0, 0])
                    cylinder(d = m3_tap_d, h = plate_t + 2, center = true);
        for (side = [-1, 1])
            translate([side * (cavity_w / 2 + wall / 2), wrap_y / 2, 0])
                rotate([0, 90, 0])
                    cylinder(d = m4_tap_d, h = wall + 4, center = true);
    }
}

if (part == "clamp")
    arm_clamp_solid();
else
    color([0.18, 0.18, 0.2])
        arm_clamp_solid();
