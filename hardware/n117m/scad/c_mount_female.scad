// C 口内螺纹（1"-32 UN）——已停用。
// N-117M 相机盒改为 φ25 滑套 + 原厂 M4 顶丝（见 00_camera_box.scad），不再引用本文件。
// 保留以免旧试拧环 STL 对不上来源。
//
// 原先：供相机盒旋到永新转接筒外牙上。
//
// 第一版误用 RMS 牙（螺距 0.706mm），入口无倒角，FDM 拉丝后看起来像光孔，
// 孔约 24.6mm，套不上 25.4mm 外牙。本文件改为梯形牙、32 牙/英寸，并做导入倒角。
//
// inner_thread 的 radius = 牙尖所在半径（内牙小径/2）；牙体向外长到牙根。
// 必须把通孔开得比牙尖略大，牙尖才会伸进孔里咬外牙——不能当套管硬套。

// 已停用。螺纹库不是本产品依赖；若要重开 C 口，把 threads 拷进本目录再引用。

// 1"-32 UN
c_pitch            = 25.4 / 32;   // 0.79375mm
c_male_major       = 25.4;
// FDM 内牙略放大。过紧加大本值 0.1，过松减小 0.1。
c_print_clear      = 0.25;
c_female_crest_d   = 24.70 + c_print_clear; // 牙尖围成的小径，必须 < 25.4
c_inward           = 0.45;        // 牙尖伸进通孔的径向深度
c_bore_d           = c_female_crest_d + 2 * c_inward;
c_thread_height    = 0.60;        // 牙高 → 牙根埋进壁里
c_thread_base_w    = 0.62;        // 牙根宽（梯形大边）
c_thread_top_w     = 0.16;        // 牙尖宽（梯形小边）
c_chamfer_h        = 2.0;
c_chamfer_d        = 27.0;        // 入口大于外牙大径，对准后再咬牙

/**
 * 在已挖好通孔的圆柱体内补上 C 口内牙（梯形截面）。
 * 坐标系：z=0 为法兰面，+z 进入盒子。
 */
module c_mount_internal_thread(h) {
    inner_thread(
        radius = c_female_crest_d / 2,
        thread_height = c_thread_height,
        thread_base_width = c_thread_base_w,
        thread_top_width = c_thread_top_w,
        thread_length = h,
        pitch = c_pitch,
        extra = -0.4,
        overlap = 0.15,
        number_divisions = 60
    );
}

/**
 * 从实心圆柱做出「倒角 + 通孔 + 内牙」，得到可拧的螺母段。
 *
 * od: 外径；h: 轴向高度。
 */
module c_mount_female_in(od, h) {
    difference() {
        union() {
            difference() {
                cylinder(h = h, d = od, $fn = 80);
                translate([0, 0, -1])
                    cylinder(h = h + 2, d = c_bore_d, $fn = 80);
            }
            c_mount_internal_thread(h);
        }
        // 导入倒角：让 25.4mm 外牙先对中，再拧进螺纹
        translate([0, 0, -0.02])
            cylinder(h = c_chamfer_h, d1 = c_chamfer_d, d2 = c_female_crest_d, $fn = 80);
    }
}
