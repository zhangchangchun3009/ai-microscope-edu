// N-117M 三目观察头 + 摄影筒 + φ25 滑套相机盒
//
// 局部坐标：原点在头座上表面中心；+Z 朝上；+Y 朝目镜。
// 相机盒 USB 口朝 −Y（背离操作者）。M4 顶丝在 −X（正视右侧）。
// C 口转接头已拆：剩下转接筒 φ25×17 圆柱头，打印盒套上去。

use <00_camera_box.scad>

head_h        = 42;
head_xy       = [88, 70];
eye_spread    = 32;
eye_ang       = 35;
photo_cone_h  = 12;
tube_od       = 25.0;
tube_h        = 17.0;
tube_id       = 16.0;

/**
 * 白色观察头方壳，目镜朝 +Y 斜出。
 */
module observation_head() {
    color([0.86, 0.83, 0.76]) {
        translate([0, 8, head_h / 2])
            cube([head_xy[0], head_xy[1], head_h], center = true);
        for (sx = [-1, 1])
            translate([sx * eye_spread / 2, 28, 28])
                rotate([-eye_ang, 0, 0])
                    cylinder(d = 23, h = 52);
        translate([0, 22, 36])
            cube([48, 18, 8], center = true);
    }
}

/**
 * 白锥座 + 转接筒露出的 φ25 圆柱头。z=0 为头壳顶面。
 */
module photo_tube() {
    translate([0, 0, head_h]) {
        color([0.86, 0.83, 0.76])
            cylinder(d1 = 48, d2 = 36, h = photo_cone_h);
        color([0.12, 0.12, 0.14])
            translate([0, 0, photo_cone_h])
                difference() {
                    cylinder(d = tube_od, h = tube_h);
                    translate([0, 0, -0.2])
                        cylinder(d = tube_id, h = tube_h + 0.4);
                }
    }
}

function sleeve_mouth_z() = head_h + photo_cone_h;

/**
 * 打印相机盒套在 φ25 圆柱头上。USB 朝后。
 */
module camera_box_mounted() {
    translate([0, 0, sleeve_mouth_z()])
        rotate([0, 0, 180])
            color([0.22, 0.28, 0.32])
                camera_box();
}

/**
 * 头座以上的全部：观察头、摄影筒、相机盒。
 */
module trinocular_stack() {
    observation_head();
    photo_tube();
    camera_box_mounted();
}

trinocular_stack();
