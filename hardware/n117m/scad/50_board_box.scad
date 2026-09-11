// N-117M 主板盒：五面壳体 + 靠臂盖。接口朝上，板竖在后壁。
// 数字与 ../dims.json board_box 同步。禁止 use openscad_V1。
// 局部：原点=外廓中心；+Y 朝臂；+Z 上。
// 导出：openscad -D 'part="shell"|"lid"|"fit"' -o ../stl/...
// preview：壳体与盖并排；section：切开看后壁螺孔和喇叭沉槽。
// fit：接口顶墙 + 靠近接口的两颗支柱，接口面朝床。

part = "preview"; // preview | shell | lid | section | fit

$fn = 32;

board_x = 150.0;
board_z = 90.0;
hole_inset = 4.0;
outer_x = 180.0;
outer_y = 50.0;
outer_z = 115.0;
wall = 2.5;
lid_t = 3.0;
ffc_w = 17.2;
vent_w = 2.4;
vent_pitch = 6.0;
m3_through = 3.2;
standoff_h = 8.0;
standoff_d = 10.0;
standoff_tap = 2.4;
pcb_z = 10.0;
plate_pitch = 40.0;
lid_boss = 12.0;
lid_boss_y = 8.0;
m3_nut_af = 5.5;
m3_nut_h = 2.4;
m3_nut_clear = 0.35;
spk_pw = 20.5;
spk_ph = 39.0;
spk_pitch = 45.0;
spk_hd = 4.2;
spk_slot = [12.0, 4.0];
spk_boss_t = 5.0;
spk_pocket_d = 4.0;

// 顶面孔：X 相对旧抽屉取负。y_from_pcb 从后壁内侧起（原法兰底 z=0 = 3mm 底板底面）。
// USB3 孔心 23.8 = 原抽屉 local_z_usb+6。支柱高 8 = 原 3mm 底板 + 5mm 柱，不要再把柱高叠进孔位。
// [name, x, y_from_pcb, kind, d_or_w, h]
ports = [
    ["dc",     62.0, 12.5, "circle", 8.0,  0],
    ["typec",  47.5, 11.5, "rect",  10.0, 4.5],
    ["mic",    36.5, 11.6, "circle", 2.5,  0],
    ["phone",  27.0, 11.6, "circle", 7.0,  0],
    ["eth0",   13.0, 16.5, "rect",  17.0, 15.0],
    ["eth1",   -7.0, 16.5, "rect",  17.0, 15.0],
    ["hdmi",  -24.0, 18.5, "rect",   6.0, 18.5],
    ["usb3",  -41.0, 23.8, "rect",  17.0, 32.0],
    ["usb2",  -59.0, 17.8, "rect",  15.5, 17.5]
];

inner_x = outer_x - 2 * wall;
inner_y = outer_y - wall - lid_t;
inner_z = outer_z - 2 * wall;

/**
 * 顶面孔 Y 基准：后壁内侧。与原抽屉法兰底 z=0（底板底面）相同，不要加支柱高。
 */
function y_pcb() = -outer_y / 2 + wall;

/**
 * 盖内表面的局部 Y。
 */
function y_lid_inner() = outer_y / 2 - lid_t;

/**
 * 盒体外廓（含盖所占体积）。
 */
module box_outer() {
    cube([outer_x, outer_y, outer_z], center = true);
}

/**
 * 内腔从后壁内侧一直穿出 +Y 开口（五面盒，盖面没有墙）。
 */
module box_cavity() {
    ymin = -outer_y / 2 + wall;
    ymax = outer_y / 2 - lid_t + 2;
    translate([0, (ymin + ymax) / 2, 0])
        cube([inner_x, ymax - ymin, inner_z], center = true);
}

/**
 * 切掉盖所占的 +Y 薄层，壳体口沿停在合盖平面。
 */
module clip_lid_volume() {
    translate([0, outer_y / 2 - lid_t - 500, 0])
        cube([400, 1000, 400], center = true);
}

/**
 * 顶面通孔。孔中心 y = 后壁内侧 + y_from_pcb（原法兰 z=0）。
 */
module port_cutouts() {
    top_z = outer_z / 2 - wall / 2;
    for (p = ports) {
        px = p[1];
        py = y_pcb() + p[2];
        kind = p[3];
        translate([px, py, top_z]) {
            if (kind == "circle")
                cylinder(d = p[4], h = wall + 4, center = true);
            else
                cube([p[4], p[5], wall + 4], center = true);
        }
    }
}

/**
 * 屏线槽：顶面靠臂棱，宽 16+间隙。
 */
module ffc_slot() {
    top_z = outer_z / 2 - wall / 2;
    translate([0, y_lid_inner() - 6, top_z])
        cube([ffc_w, 8, wall + 4], center = true);
}

/**
 * 内侧喇叭基座。数字抄原底座 speaker_mount_bosses：5×22 立方体 + 向外薄楔。
 */
module speaker_inner_boss(side) {
    hull() {
        translate([side * (inner_x / 2 - 2.5), 0, 0])
            cube([5, 22, spk_ph + 14], center = true);
        translate([side * (inner_x / 2 + 0.1), 0, -(spk_ph + 14) / 4])
            cube([0.2, 22, (spk_ph + 14) / 2], center = true);
    }
}

/**
 * 喇叭开孔。数字抄原底座 speaker_cutouts：内侧沉槽、盒内螺丝孔、打穿外壁的三条缝。
 */
module speaker_cutouts(side) {
    translate([side * (inner_x / 2 - 5 + 4.1 / 2), 0, 0])
        cube([4.1, 20.5, 39], center = true);
    for (dz = [spk_pitch / 2, -spk_pitch / 2])
        translate([side * (inner_x / 2 - 5 + 3), 0, dz])
            rotate([0, 90, 0])
                cylinder(d = spk_hd, h = 6, center = true);
    for (dz = [-10, 0, 10])
        translate([side * (inner_x / 2 + wall / 2 + 6), 0, dz])
            cube([20, 12, 4], center = true);
}

/**
 * 条纹散热孔阵列，位于当前坐标的 XY 平面上、沿 X 排布。
 */
module vent_grid_on_face(w, h, t) {
    nx = max(1, floor((w - 12) / vent_pitch));
    for (i = [0 : nx - 1]) {
        x = -w / 2 + 8 + i * vent_pitch;
        translate([x, 0, 0])
            cube([vent_w, t + 0.2, h - 16], center = true);
    }
}

/**
 * 左、右、后、底四面条纹孔；顶面和盖不开。
 */
module vent_cutouts() {
    translate([0, -outer_y / 2 + wall / 2, 0])
        rotate([90, 0, 0])
            vent_grid_on_face(inner_x - 20, inner_z, wall);
    translate([0, -lid_t / 2, -outer_z / 2 + wall / 2])
        vent_grid_on_face(inner_x - 20, inner_y - 10, wall);
    for (side = [-1, 1])
        translate([side * (outer_x / 2 - wall / 2), -outer_y / 4, 0])
            cube([wall + 4, vent_w, inner_z - 40], center = true);
}

/**
 * 口沿四角实心座，贴侧墙和顶/底墙，内侧嵌 M3 六角螺帽。
 */
module corner_nut_bosses() {
    s = lid_boss;
    by = lid_boss_y;
    for (sx = [-1, 1], sz = [-1, 1])
        translate([
            sx * (inner_x / 2 - s / 2 + 1),
            y_lid_inner() - by / 2,
            sz * (inner_z / 2 - s / 2 + 1)
        ])
            cube([s, by, s], center = true);
}

/**
 * 合箱：盖侧通孔 + 座内侧六角螺帽槽。螺丝从盖外拧，螺帽从盒内卡入。
 */
module corner_bolt_cutouts() {
    ix = inner_x / 2 - 6;
    iz = inner_z / 2 - 6;
    trap_h = m3_nut_h + 0.4;
    y_back = y_lid_inner() - lid_boss_y;
    nut_d = (m3_nut_af + m3_nut_clear) / cos(30);
    for (x = [-ix, ix], z = [-iz, iz]) {
        translate([x, y_lid_inner() - lid_boss_y / 2, z])
            rotate([90, 0, 0])
                cylinder(d = m3_through, h = lid_boss_y + 2, center = true);
        translate([x, y_back + trap_h / 2, z])
            rotate([90, 30, 0])
                cylinder(d = nut_d, h = trap_h + 0.2, center = true, $fn = 6);
    }
}

/**
 * 盖上四角通孔，对准壳体螺杆。
 */
module lid_through_at_corners() {
    ix = inner_x / 2 - 6;
    iz = inner_z / 2 - 6;
    for (x = [-ix, ix], z = [-iz, iz])
        translate([x, outer_y / 2 - lid_t / 2, z])
            rotate([90, 0, 0])
                cylinder(d = m3_through, h = lid_t + 4, center = true);
}

/**
 * 盖中央 40×40 M3 通孔，螺丝穿过盖自攻进抱箍矩形板。
 */
module clamp_holes_in_lid() {
    h = plate_pitch / 2;
    for (x = [-h, h], z = [-h, h])
        translate([x, outer_y / 2 - lid_t / 2, z])
            rotate([90, 0, 0])
                cylinder(d = m3_through, h = lid_t + 4, center = true);
}

/**
 * 后壁 PCB 支柱。孔口朝开口（+Y），φ2.4 给 M3 自攻。
 * pcb_z 把整板朝接口平移：四角距边 4mm（原抽屉 5-1），靠顶一对柱心距
 * 顶墙内表面 4mm，柱 φ10 切入接口面约 1mm。USB2 外边到柱心 4.25mm。
 */
module pcb_standoffs() {
    bx = board_x / 2 - hole_inset;
    bz = board_z / 2 - hole_inset;
    y0 = -outer_y / 2 + wall;
    for (x = [-bx, bx], z = [-bz, bz])
        translate([x, y0 + standoff_h / 2, z + pcb_z])
            rotate([90, 0, 0])
                difference() {
                    cylinder(d = standoff_d, h = standoff_h, center = true);
                    cylinder(d = standoff_tap, h = standoff_h + 2, center = true);
                }
}

/**
 * 五面壳体：开口朝 +Y，板和喇叭在壳上。
 */
module board_box_shell() {
    difference() {
        union() {
            difference() {
                intersection() {
                    box_outer();
                    clip_lid_volume();
                }
                box_cavity();
            }
            speaker_inner_boss(-1);
            speaker_inner_boss(1);
            corner_nut_bosses();
        }
        port_cutouts();
        ffc_slot();
        speaker_cutouts(-1);
        speaker_cutouts(1);
        vent_cutouts();
        corner_bolt_cutouts();
    }
    pcb_standoffs();
}

/**
 * 试打件：整块接口顶墙 + 后壁上靠近接口的两颗螺丝支柱。
 * 切掉盒高下半，远离接口的两颗孔不在件上。
 */
module board_box_fit() {
    z_hi = pcb_z + board_z / 2 - hole_inset;
    zmin = z_hi - 14;
    zmax = outer_z / 2 + 1;
    ymin = -outer_y / 2 - 1;
    ymax = outer_y / 2 - lid_t + 1;
    intersection() {
        board_box_shell();
        translate([0, (ymin + ymax) / 2, (zmin + zmax) / 2])
            cube([outer_x + 2, ymax - ymin, zmax - zmin], center = true);
    }
}

/**
 * 靠臂盖：四角合箱通孔 + 中央抱箍 4 孔。
 */
module board_box_lid() {
    difference() {
        translate([0, outer_y / 2 - lid_t / 2, 0])
            cube([outer_x, lid_t, outer_z], center = true);
        lid_through_at_corners();
        clamp_holes_in_lid();
    }
}

/**
 * 预览用：出音缝（外壁）与内侧沉槽填色。
 */
module speaker_slot_highlights() {
    color([1.0, 0.55, 0.12])
        for (side = [-1, 1], dz = [-10, 0, 10])
            translate([side * (outer_x / 2 + 0.7), 0, dz])
                cube([1.4, 12, 4], center = true);
    color([0.25, 0.72, 0.95])
        for (side = [-1, 1])
            translate([side * (inner_x / 2 - 5 + 4.1 / 2), 0, 0])
                cube([3.2, 20.5, 39], center = true);
}

/**
 * 预览用：口沿四角通孔填色。
 */
module corner_insert_highlights() {
    ix = inner_x / 2 - 6;
    iz = inner_z / 2 - 6;
    color([0.95, 0.75, 0.15])
        for (x = [-ix, ix], z = [-iz, iz])
            translate([x, y_lid_inner() + 0.4, z])
                rotate([90, 0, 0])
                    cylinder(d = 4.0, h = 0.8, center = true);
}

/**
 * 预览用：开口沿绿色框，避免全黑看成六面闭合。
 */
module opening_rim_highlight() {
    y_open = outer_y / 2 - lid_t;
    color([0.15, 0.9, 0.45])
        translate([0, y_open, 0])
            difference() {
                cube([inner_x + 4, 1.2, inner_z + 4], center = true);
                cube([inner_x - 3, 2, inner_z - 3], center = true);
            }
}

/**
 * 客户预览：壳体与盖并排，盖不盖上；开口朝 +Y（绿框）。
 */
module board_box_preview() {
    color([0.22, 0.22, 0.24])
        board_box_shell();
    opening_rim_highlight();
    speaker_slot_highlights();
    corner_insert_highlights();
    color([0.22, 0.48, 0.78])
        translate([outer_x + 22, 0, 0])
            board_box_lid();
}

if (part == "shell")
    board_box_shell();
else if (part == "lid")
    board_box_lid();
else if (part == "fit")
    // 接口面朝床：顶墙放到 z=0 再绕 X 翻 180°。
    rotate([180, 0, 0])
        translate([0, 0, -outer_z / 2])
            board_box_fit();
else if (part == "section")
    intersection() {
        board_box_shell();
        translate([40, 0, 0])
            cube([120, 80, 140], center = true);
    }
else
    board_box_preview();
