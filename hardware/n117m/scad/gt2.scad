// GT2 2mm 齿形（同步带轮外齿 = 带齿的凹模）。
// 公式与 hardware/n117m/pulley_geom.py 一致：PD = n*2/π，OD = PD − 2*0.254。

GT2_PITCH  = 2.0;
GT2_U      = 0.254;
GT2_TOOTH_H = 0.75;

/**
 * 节圆直径。
 * teeth: 齿数。
 */
function gt2_pd(teeth) = teeth * GT2_PITCH / PI;

/**
 * 齿顶圆直径。
 * teeth: 齿数。
 */
function gt2_od(teeth) = gt2_pd(teeth) - 2 * GT2_U;

/**
 * 单个带齿截面，+Y 为离开轮心（从齿顶再往外）。
 * 放在 r = OD/2 处用 difference 切出轮齿槽。
 */
module gt2_belt_tooth_2d() {
    hull() {
        translate([-0.40, 0.12]) circle(r = 0.12, $fn = 20);
        translate([ 0.40, 0.12]) circle(r = 0.12, $fn = 20);
        translate([-0.22, GT2_TOOTH_H]) circle(r = 0.22, $fn = 20);
        translate([ 0.22, GT2_TOOTH_H]) circle(r = 0.22, $fn = 20);
    }
}

/**
 * 带 GT2 外齿的圆柱（实心，未挖内孔）。
 * 带齿槽从齿顶圆向内切；teeth: 齿数；h: 齿宽（轴向）。
 */
module gt2_toothed_cylinder(teeth, h) {
    od = gt2_od(teeth);
    difference() {
        cylinder(d = od, h = h, $fn = max(80, teeth * 3));
        for (i = [0 : teeth - 1])
            rotate(i * 360 / teeth)
                translate([0, od / 2, -0.1])
                    rotate(180)
                        linear_extrude(height = h + 0.2)
                            gt2_belt_tooth_2d();
    }
}
