# N-117M 打印件（相机盒先行）

现行产品计划：[`../../docs/plans/2026-09-07-ai-camera-closed-loop-plan.md`](../../docs/plans/2026-09-07-ai-camera-closed-loop-plan.md)（无电控）。  
电机化旧计划仅作归档：仓库根目录 `docs/plans/2026-08-25-n117m-hardware-retrofit-plan.md`。

对应相机盒做法仍见下文（原 §5.4）。剖分轮 / 电机抱箍本期不打。

打印机：Bambu Lab X1 Carbon。只打 2.4G Wi-Fi；本机用手机热点配网即可。

## 为什么不再打印 C 口

C 口试拧环两版都套不上去（牙型/间隙）。改成拆掉带顶丝的 C 口转接头，打印件套在转接筒剩下的 **φ25×17mm** 圆柱头上，**复用原厂 M4 顶丝**锁高度。

感光开口为圆角矩形 **18×16**（原垫片 15.5×13.5 略放大）。电源凹槽在 USB 侧穿出接线，与感光窗口之间留挡片。

## 先打哪件

| 文件 | 作用 |
|------|------|
| `stl/fit_sleeve.stl` | **先打这个**。能顺滑套满 17mm、M4 顶丝能咬住再打盒子 |
| `stl/camera_box.stl` | 相机盒。对焦靠抽拉盒子 + 原厂顶丝 |

过紧：把 `00_camera_box.scad` / `dims.json` 的 `sleeve_clear`（`print_clear`）加大 0.1。过松：减小 0.1。第一版 0.40 能套上但很紧，现用 **0.60**（内径 25.60）。

## 导出 STL

```bash
cd hardware/n117m/scad
openscad -o ../stl/fit_sleeve.stl -D 'part="sleeve"' 00_camera_box.scad
openscad -o ../stl/camera_box.stl -D 'part="box"' 00_camera_box.scad
```

## 拓竹 X1C

- PETG，耗材烘干
- 层高 **0.16–0.20mm**（无螺纹），壁 ≥4 圈，填充 30–40%
- **口沿 / 倒角朝下**，套筒轴竖直
- 外墙降速（约 40–60mm/s）；共振大就开「共振补偿 / 输入整形」
- 试套筒是直筒 + 同外径顶盖，不要再打向外翻的法兰（会悬空炒面）
- M4 是壁上直孔（无凸环），水平打印；顶丝在 PETG 里自攻，底孔 **φ3.6**

## Z 剖分轮

OpenSCAD 打开 `scad/05_pulley_split.scad`。Customizer 里 `part`：

- `preview`：半透明粗调轮 + 圆弧槽灰毂 + 剖分轮（默认）
- `solid`：未剖分，看齿、颈缩、皮带入口
- `half_a` / `half_b`：单半
- `print`：两半剖分面朝下

默认 **48 齿**（约 30mm）。腹板与齿同高 6mm；夹耳也是 6mm（横穿 M3 做不成 0.8mm 挡边）。夹耳在齿圈外。

## 镜臂（细化中）

OpenSCAD 打开 `scad/20_arm.scad`（或 `10_layout.scad` 且 `part="arm"`）。

- `arm`：底座 + C 臂 + Z 手轮 + 三目头 + 载物台
- `stage`：载物台底部 / 齿轮箱特写
- `head`：三目筒 + 相机盒特写
- `knobs`：Z 手轮特写
- `section`：Z 高度 XY 截面（抱箍内轮廓）
- `profile`：X=0 薄片，对照右视图

载物台在 `scad/40_stage.scad`。台面 132×142、行程 75×40、手轮用 B 组；齿轮箱和 Z 滑座按照片估。挂 XY 电机前填 `measure_sheet.md` **D 组**。

## 主板盒与抱箍

设计：[`../../docs/superpowers/specs/2026-09-08-board-box-arm-clamp-design.md`](../../docs/superpowers/specs/2026-09-08-board-box-arm-clamp-design.md)。

耗材 **PETG-CF**，喷嘴 **0.6 mm 硬化钢**；不要用红色普通 PETG。层高 0.16–0.20，壁 ≥4 圈。壳体后壁朝床；盖平打；抱箍顶丝孔水平打。

```bash
cd hardware/n117m/scad
openscad -o ../stl/board_box_fit.stl   -D 'part="fit"'   50_board_box.scad
openscad -o ../stl/board_box_shell.stl -D 'part="shell"' 50_board_box.scad
openscad -o ../stl/board_box_lid.stl   -D 'part="lid"'   50_board_box.scad
openscad -o ../stl/arm_clamp.stl       -D 'part="clamp"' 51_arm_clamp.scad
```

改孔先打 **`board_box_fit.stl`**（接口顶墙 + 靠近接口的两颗支柱，约 180×50×22 mm，接口面已朝床）。对上了再打整壳体。看形状：打开 `50_board_box.scad`（默认 `preview`，壳体与盖并排，出音孔橙色）；抱箍打开 `51_arm_clamp.scad`。总装打开 `10_layout.scad`（默认 `part="all"`：臂 + 盒抱箍 + 屏框托/横梁抱箍）。`part="box"` 只挂壳体，盖不盖上。

合箱 M3 四角；盖中央 40×40 M3 对抱箍；抱箍左右侧壁各 1×M4 顶丝（底孔 3.6）加垫片。USB 无凸盖。喇叭装在盒内，外壳三条出音缝。

## 10 寸屏横梁支架

设计：[`../../docs/superpowers/specs/2026-09-09-screen-beam-clamp-design.md`](../../docs/superpowers/specs/2026-09-09-screen-beam-clamp-design.md)。

触屏面 **258×168**，大于 X1C 床，托盘拆两半。正式左右平框中线重叠 2 mm，都拧到单独打印的中间竖条上：外沿挡玻璃、底槽先直角井再 60°、中间镂空嵌 4–5 mm 钢板。已打左半（只包 128 mm）配 `screen_tray_r_patch.stl`，不当量产。

耗材同样 **PETG-CF** / **0.6 mm**。托盘两半槽口朝上平打；竖条平打；抱箍贴合面朝上或侧立，顶丝孔水平打。

```bash
cd hardware/n117m/scad
openscad -o ../stl/beam_clamp.stl    -D 'part="clamp"'  52_beam_clamp.scad
openscad -o ../stl/beam_saddle.stl   -D 'part="saddle"' 52_beam_clamp.scad
openscad -o ../stl/beam_bar.stl      -D 'part="bar"'    52_beam_clamp.scad
openscad -o ../stl/screen_tray_l.stl -D 'part="tray_l"' 52_beam_clamp.scad
openscad -o ../stl/screen_tray_r.stl -D 'part="tray_r"' 52_beam_clamp.scad
openscad -o ../stl/screen_tray_r_patch.stl -D 'part="tray_r_patch"' 52_beam_clamp.scad
```

看形状：打开 `52_beam_clamp.scad`（默认 `preview` 是拼好的总装，鞍按 −45°；`part="explode"` 拆开摆）。总装打开 `10_layout.scad`（默认已含框托与横梁抱箍）。

屏支架一律 **M3×30 外六角 + 螺母**（框–条 4 + 座板 2 + 铰链 2）；螺母沉窝，余牙出背面。横梁倒 U 左右 2×M4 顶丝 + 尼龙垫。

## 装配

1. 拆掉带顶丝的 C 口转接头，露出转接筒 φ25 圆柱头
2. 试套筒 / 盒子从口沿套上，坐满 17mm 后顶法兰（或盒内矩形开口）挡住筒顶
3. 转到 USB 朝后，目镜调清样品后抽拉找相机最清位置，拧原厂 M4 顶丝
4. PCB 感光面向下，白色电源插口朝 USB 开口一侧；M2 自攻，USB-C 朝开口
