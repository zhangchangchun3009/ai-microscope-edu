// N-117M 相机盒：φ25 滑套 + pc-oic678 裸板
//
// 拆掉原厂带顶丝的 C 口转接头后，打印件套在转接筒 φ25 圆柱头上（露出 17mm）。
// 侧孔复用原厂 M4 顶丝锁高度、抽拉对焦。不再打印 C 口螺纹。
// 感光开口为圆角矩形（原垫片 15.5×13.5，现 18×16）。电源凹槽 USB 侧穿出接线，与窗口之间留挡片。
//
// 坐标：z=0 套筒口沿（先碰到圆柱头）；+z 朝 PCB 背面。
// 坐死时筒顶齐套筒顶（z=17），感光面再往上 17.526。
//
// 导出：openscad -D 'part="box"|"sleeve"' -o out.stl 00_camera_box.scad

part = "preview"; // preview | box | sleeve

$fn = 80;

pcb_xy                 = 32.0;
hole_pitch             = 27.0;
sensor_proud           = 2.0;
sleeve_top_to_sensor   = 17.526;
pcb_clearance          = 1.0;    // 0.3 槽打出来偏小，0.6 喷头再加点
pcb_t_guess            = 1.6;
tube_od                = 25.0;
sleeve_clear           = 0.60;
sleeve_h               = 17.0;
collar_od              = 36.0;
win_x                  = 18.0;   // 原垫片 15.5，封装会蹭，略放大
win_y                  = 16.0;   // 原垫片 13.5
win_r                  = 1.0;
m4_tap_d               = 3.6;
cap_t                  = 2.4;
screw_tap_d            = 2.4;
usb_slot_w             = 14.0;
usb_slot_h             = 8.0;
pwr_w                  = 14.0;
pwr_d                  = 6.5;
pwr_baffle             = 2.5;    // 与感光窗口之间留挡片；凹槽向外穿壁接线
wall                   = 2.4;
chamfer_h              = 1.5;
chamfer_extra          = 1.1;

function sleeve_bore() = tube_od + sleeve_clear;
function z_sensor()    = sleeve_h + sleeve_top_to_sensor;
function z_pcb()       = z_sensor() + sensor_proud;

module hole_grid(d, h) {
    for (x = [-1, 1] * hole_pitch / 2, y = [-1, 1] * hole_pitch / 2)
        translate([x, y, 0]) cylinder(d = d, h = h);
}

/**
 * 感光开口：圆角矩形，比 imx678_20 垫片略大，避免蹭封装。
 * USB 在 +Y。
 */
module sensor_window_2d() {
    w = win_x / 2 - win_r;
    l = win_y / 2 - win_r;
    hull() {
        translate([ w,  l]) circle(r = win_r);
        translate([-w,  l]) circle(r = win_r);
        translate([ w, -l]) circle(r = win_r);
        translate([-w, -l]) circle(r = win_r);
    }
}

/**
 * M4 直孔：打穿套筒壁，和原厂转接头一样没有凸环。
 * 孔略大于攻丝底孔，给水平打印变形留余量，永新顶丝在 PETG 里自攻。
 */
module m4_hole() {
    wall_t = (collar_od - sleeve_bore()) / 2;
    translate([-collar_od / 2 - 0.2, 0, sleeve_h / 2])
        rotate([0, 90, 0])
            cylinder(d = m4_tap_d, h = wall_t + 3);
}

module sleeve_bore_cut() {
    translate([0, 0, -0.2])
        cylinder(h = sleeve_h + 0.4, d = sleeve_bore());
    translate([0, 0, -0.02])
        cylinder(
            h = chamfer_h,
            d1 = sleeve_bore() + 2 * chamfer_extra,
            d2 = sleeve_bore()
        );
}

/**
 * 试套筒：φ25.6 光孔 + 壁上 M4 直孔 + 同外径顶盖（矩形开口当硬限位）。
 * 顶盖不向外翻边，避免口沿朝下打印时上沿悬空炒面。
 */
module fit_sleeve() {
    difference() {
        cylinder(h = sleeve_h + cap_t, d = collar_od);
        sleeve_bore_cut();
        m4_hole();
        translate([0, 0, sleeve_h - 0.05])
            linear_extrude(height = cap_t + 0.3)
                sensor_window_2d();
    }
}

/**
 * 相机盒。z=0 套筒口沿；感光面在 z_sensor()。
 * 电源凹槽与感光窗口之间留挡片；凹槽从 USB 侧穿出，便于接线，光路不连通。
 */
module camera_box() {
    zs      = z_sensor();
    zp      = z_pcb();
    well_z  = zs - 0.4;
    body_h  = zp + pcb_t_guess + 2.0;
    pocket  = pcb_xy + pcb_clearance;
    outer   = pocket + 2 * wall;

    difference() {
        union() {
            cylinder(h = sleeve_h, d = collar_od);
            translate([0, 0, sleeve_h - 0.2])
                cylinder(h = well_z - sleeve_h + 0.4, d1 = collar_od, d2 = outer * 1.15);
            translate([0, 0, well_z])
                linear_extrude(height = body_h - well_z)
                    offset(r = 3, $fn = 32)
                        square(outer - 6, center = true);
        }

        sleeve_bore_cut();
        m4_hole();

        translate([0, 0, sleeve_h - 0.05])
            linear_extrude(height = zp - sleeve_h + 0.15)
                sensor_window_2d();

        // 电源凹槽：挡片之后向外穿壁，接线从 USB 侧进出，不打通感光窗口
        translate([-pwr_w / 2, win_y / 2 + pwr_baffle, zp - pwr_d])
            cube([
                pwr_w,
                outer / 2 + wall + 4 - (win_y / 2 + pwr_baffle),
                pwr_d + pcb_t_guess + usb_slot_h
            ]);

        translate([-pocket / 2, -pocket / 2, zp])
            cube([pocket, pocket, 12]);

        translate([0, 0, well_z - 1]) hole_grid(screw_tap_d, 12);

        translate([0, outer / 2, zp + pcb_t_guess + usb_slot_h / 2 - 1])
            cube([usb_slot_w, wall + 8, usb_slot_h], center = true);
    }
}

if (part == "box") camera_box();
else if (part == "sleeve") fit_sleeve();
else {
    camera_box();
    translate([52, 0, 0]) fit_sleeve();
}
