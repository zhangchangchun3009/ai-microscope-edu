// N-117M 剖分皮带轮：小齿圈、实心短腹板、夹耳在齿圈外
//
// 齿数 48，齿顶圆约 30mm，略大于原蓝套手轮 28.5mm（不必 72 齿）。
// 毂到齿根只有约 4mm，不设桥，整圈实心连上。
// 腹板高度 = 带宽 + 一点；两侧薄挡边只做在齿圈上防皮带跑偏。
// 夹耳在齿圈外，皮带从齿与耳之间过。
//
// preview：橙色=腹板+耳朵，蓝色=齿圈+挡边。

include <gt2.scad>

part = "preview";

$fn = 72;

hub_od            = 20.0;
hub_clear         = 0.28;
spline_n          = 10;
groove_r          = 1.8;
groove_depth      = 0.50;
hub_len           = 13.0;
wall_t            = 2.5;
cup_depth         = 9.0;
coarse_od         = 46.0;
coarse_t          = 22.0;

teeth             = 48;
standoff          = 1.5;
flange_t          = 0.8;      // 防皮带跑偏的薄挡边
belt_h            = 6.0;      // GT2 6mm 带宽
web_h             = 6.0;      // 腹板与齿同高，不在齿圈上再加一层
flange_over       = 1.2;
kerf              = 0.35;
belt_gap          = 1.2;      // 挡边外沿到夹耳：刚够带厚，不要长薄片
ear_d             = 7.5;      // 刚够 M3 头
ear_h             = 6.0;      // 与带宽相同；横穿 M3 不能做成 0.8 挡边那么薄
ear_x             = 12.0;
m3_d              = 3.2;
m3_nut_d          = 6.4;
m3_nut_h          = 2.6;
m3_head_d         = 6.0;
m3_head_h         = 2.2;

function pulley_h()     = 2 * flange_t + belt_h;
function z_web()        = flange_t;
function z_ear()        = (pulley_h() - ear_h) / 2;
function flange_d()     = gt2_od(teeth) + 2 * flange_over;
function root_d()       = gt2_od(teeth) - 2 * GT2_TOOTH_H;
function inner_rim_d()  = root_d() - 0.4;
function ear_cy()       = flange_d() / 2 + belt_gap + ear_d / 2;

/**
 * 灰毂横截面：φ20 上切 10 个圆弧槽。
 */
module hub_2d() {
    difference() {
        circle(d = hub_od);
        for (i = [0 : spline_n - 1])
            rotate(i * 360 / spline_n)
                translate([hub_od / 2 + groove_r - groove_depth, 0])
                    circle(r = groove_r, $fn = 28);
    }
}

module pulley_bore_2d() {
    offset(r = hub_clear / 2)
        hub_2d();
}

module pulley_bore_3d(h) {
    translate([0, 0, -0.2])
        linear_extrude(height = h + 0.4)
            pulley_bore_2d();
}

/**
 * 从内孔到齿圈内缘的实心腹板（无桥）。
 */
module web_2d() {
    difference() {
        circle(d = inner_rim_d() + 0.6);
        pulley_bore_2d();
    }
}

module rim_2d() {
    difference() {
        circle(d = flange_d());
        circle(d = inner_rim_d());
    }
}

module ear_pads_2d() {
    for (sy = [-1, 1])
        translate([0, sy * ear_cy()])
            hull() {
                translate([-ear_x / 2 + ear_d / 2, 0])
                    circle(d = ear_d);
                translate([ear_x / 2 - ear_d / 2, 0])
                    circle(d = ear_d);
            }
}

module ear_wings_2d() {
    for (sy = [-1, 1])
        hull() {
            translate([0, sy * (flange_d() / 2 - 0.3)])
                square([7, 1.2], center = true);
            translate([0, sy * ear_cy()])
                circle(d = ear_d);
        }
}

module m3_cuts() {
    h = pulley_h();
    for (sy = [-1, 1]) {
        translate([-ear_x / 2 - 0.2, sy * ear_cy(), h / 2])
            rotate([0, 90, 0])
                cylinder(d = m3_d, h = ear_x + 0.4);
        translate([-ear_x / 2 - 0.05, sy * ear_cy(), h / 2])
            rotate([0, 90, 0])
                cylinder(d = m3_nut_d, h = m3_nut_h, $fn = 6);
        translate([ear_x / 2 - m3_head_h, sy * ear_cy(), h / 2])
            rotate([0, 90, 0])
                cylinder(d = m3_head_d, h = m3_head_h + 0.2);
    }
}

/**
 * 橙色：与齿同高的腹板 + 矮夹耳（高度=带宽，不是整根粗柱）。
 */
module clamp_parts() {
    h = pulley_h();
    difference() {
        union() {
            translate([0, 0, z_web()])
                linear_extrude(height = web_h)
                    web_2d();
            translate([0, 0, z_ear()])
                linear_extrude(height = ear_h)
                    ear_pads_2d();
            linear_extrude(height = flange_t)
                ear_wings_2d();
            translate([0, 0, flange_t + belt_h])
                linear_extrude(height = flange_t)
                    ear_wings_2d();
        }
        pulley_bore_3d(h);
        m3_cuts();
    }
}

/**
 * 蓝色：齿圈 + 两侧薄挡边（与腹板、耳朵在挡边处相连）。
 */
module rim_parts() {
    h = pulley_h();
    difference() {
        union() {
            linear_extrude(height = flange_t)
                union() {
                    rim_2d();
                    ear_wings_2d();
                }
            translate([0, 0, flange_t + belt_h])
                linear_extrude(height = flange_t)
                    union() {
                        rim_2d();
                        ear_wings_2d();
                    }
            translate([0, 0, flange_t])
                difference() {
                    gt2_toothed_cylinder(teeth, belt_h);
                    translate([0, 0, -0.1])
                        cylinder(d = inner_rim_d(), h = belt_h + 0.2);
                }
        }
        pulley_bore_3d(h);
        m3_cuts();
    }
}

module split_kerf() {
    translate([0, 0, pulley_h() / 2])
        cube([kerf, 2 * ear_cy() + ear_d + 8, pulley_h() + 2], center = true);
}

module pulley_kerfed() {
    difference() {
        union() {
            clamp_parts();
            rim_parts();
        }
        split_kerf();
    }
}

module pulley_half(sign) {
    intersection() {
        pulley_kerfed();
        translate([sign * 55 + sign * kerf / 2, 0, pulley_h() / 2])
            cube([110, 2 * ear_cy() + 16, pulley_h() + 4], center = true);
    }
}

module ghost_focus_stack() {
    color([0.45, 0.45, 0.45, 0.28])
        translate([0, 0, -coarse_t])
            cylinder(d = coarse_od, h = coarse_t, $fn = 80);
    color([0.55, 0.55, 0.6, 0.5])
        difference() {
            linear_extrude(height = hub_len)
                hub_2d();
            translate([0, 0, -0.1])
                cylinder(d = hub_od - 2 * wall_t, h = cup_depth + 0.1, $fn = 48);
        }
}

module assembled_preview() {
    ghost_focus_stack();
    translate([0, 0, standoff]) {
        color([0.9, 0.45, 0.1, 0.96])
            difference() {
                clamp_parts();
                split_kerf();
            }
        color([0.15, 0.45, 0.75, 0.9])
            difference() {
                rim_parts();
                split_kerf();
            }
    }
}

if (part == "preview") assembled_preview();
else if (part == "solid") {
    union() {
        clamp_parts();
        rim_parts();
    }
}
else if (part == "half_a") pulley_half(-1);
else if (part == "half_b") pulley_half(1);
else if (part == "print") {
    translate([-22, 0, ear_x / 2])
        rotate([0, -90, 0])
            pulley_half(-1);
    translate([22, 0, ear_x / 2])
        rotate([0, 90, 0])
            pulley_half(1);
}
else assembled_preview();
