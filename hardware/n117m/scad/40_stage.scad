// N-117M 载物台 + 底部齿轮箱 + XY 垂手轮
//
// 已用量：台面 132×142、行程 75×40；B 组手轮 φ/厚/间隙/轴线偏置；Z 中间焦下轮底 75.5。
// 其余（齿轮箱、滑座、筋、立柱）按照片估，挂电机前用 measure_sheet D 组补卡尺。
//
// 运动：X = 玻片夹具相对台面；Y = 整台相对镜臂；Z = 整台（含本组件）随调焦升降。
// XY 电机应抱右侧齿轮箱，随台走。聚光镜在 Z 滑座上，不随 XY。

part = "stage";

$fn = 40;

stage_x = 132;
stage_y = 142;
plate_t = 11;

travel_x = 75;
travel_y = 40;

optic_y = 16;

xy_up_od = 29;
xy_lo_od = 26;
xy_up_h  = 20;
xy_lo_h  = 15;
xy_gap   = 2;
xy_axis_off = 19;
xy_lo_bottom = (87 + 64) / 2;

shaft_d     = 16;   // 估：齿轮箱到上轮之间的竖轴
shaft_neck  = 7;    // 估：上轮顶到齿轮箱底
gearbox_whh = [42, 32, 18]; // 估：右下齿轮箱 长x宽x高
carriage_t  = 22;   // 估：Z 滑座厚度（Y）
carriage_w  = 48;
rib_t       = 3.5;

show_xy_motors = false; // 电机占位改 10_layout；此处只留挂点面

function xy_axis_x() = -(stage_x / 2 + xy_axis_off);
function xy_axis_y() = optic_y + 22;
function xy_lo_mid_z() = xy_lo_bottom + xy_lo_h / 2;
function xy_up_mid_z() = xy_lo_bottom + xy_lo_h + xy_gap + xy_up_h / 2;
function gearbox_z0() = xy_lo_bottom + xy_lo_h + xy_gap + xy_up_h + shaft_neck;
function plate_z0()   = gearbox_z0() + gearbox_whh[2];
function stage_top_z() = plate_z0() + plate_t;

// 台面中心：光孔大致在台后 1/3，对准灯室
function stage_cy() = optic_y + 18;

/**
 * Z 滑座：黑块，前面贴台，后面伸进镜臂燕尾。聚光镜挂在它下面。
 */
module z_carriage() {
    z0 = plate_z0() - 8;
    h  = plate_t + gearbox_whh[2] + 28;
    yb = -52; // 贴立柱前缘附近，估
    color([0.1, 0.1, 0.12]) {
        translate([0, yb + carriage_t / 2, z0 + h / 2])
            cube([carriage_w, carriage_t, h], center = true);
        // 伸进燕尾的舌
        translate([0, yb - 3, z0 + h / 2])
            cube([18, 8, h - 10], center = true);
    }
}

/**
 * 台板：椭圆通光孔 + 底筋。Y 向整块相对滑座移动（此处画中间位置）。
 */
module stage_plate() {
    z0 = plate_z0();
    cy = stage_cy();
    color([0.08, 0.08, 0.1])
        difference() {
            union() {
                translate([0, cy, z0 + plate_t / 2])
                    cube([stage_x, stage_y, plate_t], center = true);
                // 下翻边，方便侧向抱箍
                translate([0, cy, z0 - 2])
                    difference() {
                        cube([stage_x, stage_y, 4], center = true);
                        cube([stage_x - 8, stage_y - 8, 5], center = true);
                    }
            }
            translate([0, optic_y, z0 - 2])
                scale([1.35, 1, 1])
                    cylinder(d = 36, h = plate_t + 8);
            // 底筋格子（估）
            for (ix = [-2 : 2], iy = [-2 : 2])
                if (!(ix == 0 && iy == 0))
                    translate([ix * 22, cy + iy * 24, z0 - 1])
                        cube([16, 16, 6], center = true);
        }
}

/**
 * X 向玻片夹具（银）：相对台面左右走，台板本身不动。
 */
module x_slide_holder() {
    color([0.62, 0.62, 0.65]) {
        translate([8, optic_y + 6, stage_top_z() + 3])
            cube([88, 26, 6], center = true);
        translate([-28, optic_y + 2, stage_top_z() + 6])
            cube([8, 40, 4], center = true);
    }
}

/**
 * 右侧齿轮箱：XY 电机最可能抱这里。底面三颗螺丝仅示意，孔距未量。
 */
module xy_gearbox() {
    ax = xy_axis_x();
    ay = xy_axis_y();
    z0 = gearbox_z0();
    bw = gearbox_whh[0];
    bd = gearbox_whh[1];
    bh = gearbox_whh[2];
    color([0.1, 0.1, 0.12]) {
        translate([ax + 8, ay, z0 + bh / 2])
            cube([bw, bd, bh], center = true);
        // 竖轴
        translate([ax, ay, xy_up_mid_z() + xy_up_h / 2])
            cylinder(d = shaft_d, h = shaft_neck + 1);
    }
    // 底面螺丝示意（孔距待 D 组）
    color([0.7, 0.7, 0.72])
        for (p = [[-8, -6], [8, -6], [0, 8]])
            translate([ax + 8 + p[0], ay + p[1], z0 - 0.5])
                cylinder(d = 5.5, h = 4);
}

/**
 * 上 Y / 下 X 垂手轮（B 组实测）。
 */
module xy_knob_stack() {
    ax = xy_axis_x();
    ay = xy_axis_y();
    color([0.14, 0.14, 0.16]) {
        translate([ax, ay, xy_lo_mid_z()]) {
            cylinder(d = xy_lo_od, h = xy_lo_h, center = true);
            for (i = [0 : 17])
                rotate(i * 20)
                    translate([xy_lo_od / 2 - 0.4, 0, 0])
                        cube([1.1, 1.6, xy_lo_h], center = true);
        }
        translate([ax, ay, xy_up_mid_z()]) {
            cylinder(d = xy_up_od, h = xy_up_h, center = true);
            for (i = [0 : 19])
                rotate(i * 18)
                    translate([xy_up_od / 2 - 0.4, 0, 0])
                        cube([1.2, 1.8, xy_up_h], center = true);
        }
    }
}

/**
 * 聚光镜：挂 Z 滑座，不随 XY。不电机化。
 */
module condenser() {
    color([0.1, 0.1, 0.12])
        translate([0, optic_y, plate_z0() - 26])
            cylinder(d = 40, h = 18);
}

/**
 * 完整载物台（中间焦、XY 行程居中）。
 */
module stage_assembly() {
    z_carriage();
    stage_plate();
    x_slide_holder();
    xy_gearbox();
    xy_knob_stack();
    condenser();
}

stage_assembly();
