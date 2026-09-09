# 主板盒与臂后抱箍 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `hardware/n117m/` 做出可打印的主板五面壳体+盖、C 形顶丝抱箍（含 40×40 矩形板），并在 `10_layout.scad` 里和镜臂总装预览。

**Architecture:** 数字只活在 `dims.json`；`board_box_geom.py` 用同一套常量给 unittest 锁住。`50_board_box.scad` 画壳体和盖；`51_arm_clamp.scad` 用 `use <20_arm.scad>` 取 `y_back` / `arm_slice_2d` 做定位，内宽按卡尺 58 mm 自建 C 形，不改 `20_arm` 的 62 mm 立柱。总装替换原先 `electronics_tray` 占位。

**Tech Stack:** OpenSCAD、Python 3 unittest、`dims.json`。打印 PETG-CF、0.6 mm 硬化钢喷嘴（文档里写，本计划不切片）。

## Global Constraints

- 只改 `ai-microscope-edu/`。
- `hardware/n117m/scad/` 禁止 `use` / `include` `openscad_V1/` 或路径里带 `openscad/openscad_V1` 的文件。旧抽屉孔位必须抄进 `dims.json`。
- 不做 USB 凸盖。喇叭按 36×18×9、沉槽 20.5×39、孔距 45 mm。条纹缝宽 2.4 mm。
- 接口朝上；盖在靠臂面；板在壳体后壁；抱箍与矩形板一件；4 孔 40×40 M3。
- 打印件不测 OpenSCAD 网格；非平凡数字走 unittest。未经用户明确要求不要 `git commit`。
- 坐标：z=0 桌面，+Y 朝目镜，盒在臂后（更负 Y）。回复与注释用简体中文。

---

## File map

| 路径 | 职责 |
|------|------|
| `ai-microscope-edu/hardware/n117m/dims.json` | 新增 `board_box`、`arm_clamp` |
| `ai-microscope-edu/hardware/n117m/board_box_geom.py` | 与 scad 同公式的孔距、缝宽、外廓 |
| `ai-microscope-edu/hardware/n117m/tests/test_board_box_geom.py` | 锁住 spec 数字；禁止 scad 引用 V1 |
| `ai-microscope-edu/hardware/n117m/scad/50_board_box.scad` | `part=shell\|lid\|preview` |
| `ai-microscope-edu/hardware/n117m/scad/51_arm_clamp.scad` | `part=clamp\|preview` |
| `ai-microscope-edu/hardware/n117m/scad/10_layout.scad` | 总装挂盒和抱箍 |
| `ai-microscope-edu/hardware/n117m/README.md` | 导出命令与 PETG-CF |

不创建 `52_box_plate.scad`。不改 `05_pulley_split.scad`。

`50_board_box.scad` 局部坐标：原点在盒外廓中心；+X 右；**+Y 朝臂（盖）**；**+Z 上（接口）**。盖在 `y = +outer_y/2`。世界系里把该局部绕 X 转 0°、再平移到臂后即可（局部 +Y 对齐世界 +Y）。

---

### Task 1: `dims.json` + `board_box_geom.py` + 测试

**Files:**
- Create: `ai-microscope-edu/hardware/n117m/board_box_geom.py`
- Create: `ai-microscope-edu/hardware/n117m/tests/test_board_box_geom.py`
- Modify: `ai-microscope-edu/hardware/n117m/dims.json`

**Interfaces:**
- Consumes: spec `2026-09-08-board-box-arm-clamp-design.md` 第 5–6 节数字
- Produces: `board_box_geom.ffc_slot_w`、`mount_hole_xy`、`port_x` 字典；`DIMS["board_box"]` / `DIMS["arm_clamp"]`

- [ ] **Step 1: Write the failing test**

创建 `tests/test_board_box_geom.py`：

```python
"""主板盒 / 抱箍尺寸：与 spec 和 dims.json 一致，scad 不依赖 openscad_V1。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_N117M))

from board_box_geom import (  # noqa: E402
    ffc_slot_w,
    mount_hole_xy,
    port_centers,
    speaker_pocket,
)

DIMS = json.loads((_N117M / "dims.json").read_text())
SCAD = _N117M / "scad"


class TestBoardEnvelope(unittest.TestCase):
    def test_lubancat_board_150x90_inset_5(self):
        b = DIMS["board_box"]
        self.assertEqual(b["board_xy"], [150.0, 90.0])
        self.assertEqual(b["hole_inset"], 5.0)
        self.assertEqual(b["port_panel_h"], 53.5)

    def test_outer_matches_spec_start(self):
        b = DIMS["board_box"]
        self.assertEqual(b["outer_xyz"], [180.0, 66.0, 115.0])
        self.assertEqual(b["wall"], 2.5)
        self.assertEqual(b["lid_t"], 3.0)

    def test_no_usb_shroud_flag(self):
        self.assertFalse(DIMS["board_box"]["usb_shroud"])


class TestPortsAndFfc(unittest.TestCase):
    def test_copied_drawer_xs(self):
        xs = {p["name"]: p["x"] for p in DIMS["board_box"]["ports"]}
        self.assertEqual(xs["dc"], -62.0)
        self.assertEqual(xs["typec"], -47.5)
        self.assertEqual(xs["mic"], -36.5)
        self.assertEqual(xs["phone"], -27.0)
        self.assertEqual(xs["eth0"], -13.0)
        self.assertEqual(xs["eth1"], 7.0)
        self.assertEqual(xs["hdmi"], 24.0)
        self.assertEqual(xs["usb3"], 41.0)
        self.assertEqual(xs["usb2"], 59.0)
        self.assertEqual(port_centers()["mic"][0], -36.5)

    def test_ffc_slot_is_16_plus_clear(self):
        b = DIMS["board_box"]
        self.assertEqual(b["ffc_w"], 16.0)
        self.assertAlmostEqual(ffc_slot_w(b["ffc_w"], b["ffc_clear"]), 17.2, places=1)


class TestSpeakerAndVents(unittest.TestCase):
    def test_speaker_matches_old_pocket_and_36x18(self):
        s = DIMS["board_box"]["speaker"]
        self.assertEqual(s["body_xyz"], [36.0, 18.0, 9.0])
        self.assertEqual(speaker_pocket(s), (20.5, 39.0))
        self.assertEqual(s["hole_pitch"], 45.0)

    def test_vent_width_for_0_6_nozzle(self):
        self.assertEqual(DIMS["board_box"]["vent_w"], 2.4)


class TestClamp(unittest.TestCase):
    def test_caliper_inner_width_not_arm_model_62(self):
        c = DIMS["arm_clamp"]
        self.assertEqual(c["inner_w"], 58.0)
        self.assertEqual(c["print_clear"], 0.5)
        self.assertEqual(c["h"], 45.0)
        self.assertEqual(c["plate_pitch"], 40.0)
        self.assertEqual(c["m4_tap_d"], 3.6)
        self.assertEqual(c["set_screws"], 2)
        holes = mount_hole_xy(c["plate_pitch"])
        self.assertEqual(len(holes), 4)
        self.assertIn((-20.0, -20.0), holes)
        self.assertEqual(DIMS["arm"]["width_column"], 62.0)

    def test_clamp_sits_above_z_knobs(self):
        z0 = DIMS["arm_clamp"]["z0"]
        z_axis = DIMS["xy_knobs"]["z_hub_bottom_from_desk"] + DIMS["z_fine_hub"]["od_peak"] / 2
        knob_top = z_axis + DIMS["z_fine_hub"]["coarse_od"] / 2
        self.assertGreater(z0, knob_top)
        self.assertLess(z0 + DIMS["arm_clamp"]["h"], 250.0)


class TestNoOpenscadV1Dependency(unittest.TestCase):
    def test_n117m_scad_does_not_include_v1(self):
        texts = []
        for p in SCAD.glob("*.scad"):
            texts.append((p.name, p.read_text(encoding="utf-8")))
        self.assertGreater(len(texts), 0)
        for name, text in texts:
            self.assertNotIn("openscad_V1", text, msg=name)
            self.assertNotIn("openscad/openscad_V1", text, msg=name)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m
python -m unittest tests.test_board_box_geom -v
```

Expected: FAIL / ERROR（`board_box_geom` 不存在或 `dims.json` 无 `board_box`）。

- [ ] **Step 3: Write `board_box_geom.py`**

```python
"""主板盒与抱箍几何（与 scad/50_board_box.scad、51_arm_clamp.scad 同数字）。

单位 mm。接口孔位抄自旧 lubancat_drawer_tray，不引用 openscad_V1。
"""

from __future__ import annotations

PORT_X = {
    "dc": -62.0,
    "typec": -47.5,
    "mic": -36.5,
    "phone": -27.0,
    "eth0": -13.0,
    "eth1": 7.0,
    "hdmi": 24.0,
    "usb3": 41.0,
    "usb2": 59.0,
}


def ffc_slot_w(cable_w: float, clear: float) -> float:
    """屏线槽宽 = 线宽 + 打印间隙。"""
    return cable_w + clear


def mount_hole_xy(pitch: float) -> list[tuple[float, float]]:
    """盖/矩形板 4 孔，相对中心，正方形。"""
    h = pitch / 2.0
    return [(-h, -h), (h, -h), (-h, h), (h, h)]


def port_centers() -> dict[str, tuple[float, float]]:
    """顶面孔中心：X 沿板长边，Y 为相对 PCB 元件面的板厚方向位置。"""
    y = {
        "dc": 12.5,
        "typec": 11.5,
        "mic": 11.6,
        "phone": 11.6,
        "eth0": 16.5,
        "eth1": 16.5,
        "hdmi": 18.5,
        "usb3": 17.8,
        "usb2": 17.8,
    }
    return {name: (PORT_X[name], y[name]) for name in PORT_X}


def speaker_pocket(speaker: dict) -> tuple[float, float]:
    """沉槽宽×高。宽对 18 mm 喇叭厚向，高对 36 mm 加间隙。"""
    return (float(speaker["pocket_wy"][0]), float(speaker["pocket_wy"][1]))
```

- [ ] **Step 4: Append `board_box` and `arm_clamp` to `dims.json`**

在 `dims.json` 根对象里、`z_pulley` 之后加入（保留原有键，只追加）：

```json
  "board_box": {
    "board_xy": [150.0, 90.0],
    "hole_inset": 5.0,
    "port_panel_h": 53.5,
    "outer_xyz": [180.0, 66.0, 115.0],
    "wall": 2.5,
    "lid_t": 3.0,
    "usb_shroud": false,
    "ffc_w": 16.0,
    "ffc_clear": 1.2,
    "vent_w": 2.4,
    "vent_pitch": 6.0,
    "m3_through": 3.2,
    "m3_insert_d": 4.2,
    "standoff_h": 5.0,
    "standoff_tap": 2.4,
    "ports": [
      {"name": "dc", "x": -62.0, "y_from_pcb": 12.5, "kind": "circle", "d": 8.0},
      {"name": "typec", "x": -47.5, "y_from_pcb": 11.5, "kind": "rect", "wh": [10.0, 4.5]},
      {"name": "mic", "x": -36.5, "y_from_pcb": 11.6, "kind": "circle", "d": 2.5},
      {"name": "phone", "x": -27.0, "y_from_pcb": 11.6, "kind": "circle", "d": 7.0},
      {"name": "eth0", "x": -13.0, "y_from_pcb": 16.5, "kind": "rect", "wh": [17.0, 15.0]},
      {"name": "eth1", "x": 7.0, "y_from_pcb": 16.5, "kind": "rect", "wh": [17.0, 15.0]},
      {"name": "hdmi", "x": 24.0, "y_from_pcb": 18.5, "kind": "rect", "wh": [6.0, 18.5]},
      {"name": "usb3", "x": 41.0, "y_from_pcb": 17.8, "kind": "rect", "wh": [17.0, 32.0]},
      {"name": "usb2", "x": 59.0, "y_from_pcb": 17.8, "kind": "rect", "wh": [15.5, 17.5]}
    ],
    "speaker": {
      "body_xyz": [36.0, 18.0, 9.0],
      "pocket_wy": [20.5, 39.0],
      "hole_pitch": 45.0,
      "hole_d": 4.2,
      "slot_wh": [12.0, 4.0]
    },
    "note": "局部：中心原点，+Y 朝臂，+Z 接口朝上。无 USB 凸盖。PETG-CF 0.6mm 喷嘴。"
  },
  "arm_clamp": {
    "inner_w": 58.0,
    "print_clear": 0.5,
    "h": 45.0,
    "wall": 4.0,
    "wrap_y": 22.0,
    "r_rear": 16.0,
    "plate_xy": [70.0, 50.0],
    "plate_t": 6.0,
    "plate_pitch": 40.0,
    "m3_through": 3.2,
    "m4_tap_d": 3.6,
    "set_screws": 2,
    "set_screw_span": 24.0,
    "z0": 188.0,
    "note": "内宽卡尺 58；20_arm 立柱仍 62。z0 为抱箍底面距桌，顶低于 y_back 开始前伸的 250。"
  }
```

注意 JSON 倒数第二个原对象 `z_pulley` 的 `}` 后要加逗号。

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m
python -m unittest tests.test_board_box_geom -v
```

Expected: PASS。此时 `50_*.scad` 还不存在，`TestNoOpenscadV1Dependency` 只扫已有 scad，应仍通过。

---

### Task 2: `50_board_box.scad`

**Files:**
- Create: `ai-microscope-edu/hardware/n117m/scad/50_board_box.scad`

**Interfaces:**
- Consumes: Task 1 `dims.json` 数字（抄到文件顶部变量，注释写明与 json 同步）
- Produces: `board_box_shell()`、`board_box_lid()`、`board_box_preview()`；`part` = `shell` | `lid` | `preview`

- [ ] **Step 1: Create `50_board_box.scad` with this body**

数字必须与 `dims.json` 一致。壳体是开口朝 +Y（盖）的五面盒；后壁在 −Y；顶面 +Z 开孔；左右短边喇叭；左/右/后/底条纹孔。USB3 只通孔。

```openscad
// N-117M 主板盒：五面壳体 + 靠臂盖。接口朝上，板竖在后壁。
// 数字与 ../dims.json board_box 同步。禁止 use openscad_V1。
// 局部：原点=外廓中心；+Y 朝臂；+Z 上。
// 导出：openscad -D 'part="shell"|"lid"' -o ../stl/...

part = "preview"; // preview | shell | lid

$fn = 32;

board_x = 150.0;
board_z = 90.0;
hole_inset = 5.0;
outer_x = 180.0;
outer_y = 66.0;
outer_z = 115.0;
wall = 2.5;
lid_t = 3.0;
port_panel_h = 53.5;
ffc_w = 17.2;
vent_w = 2.4;
vent_pitch = 6.0;
m3_through = 3.2;
m3_insert_d = 4.2;
standoff_h = 5.0;
standoff_tap = 2.4;
plate_pitch = 40.0;
spk_pw = 20.5;
spk_ph = 39.0;
spk_pitch = 45.0;
spk_hd = 4.2;
spk_slot = [12.0, 4.0];

// 顶面孔：X 沿板长边；y_from_pcb 在局部 Y（元件面朝 +Y，PCB 近后壁）
ports = [
    ["dc",    -62.0, 12.5, "circle", 8.0,  0],
    ["typec", -47.5, 11.5, "rect",  10.0, 4.5],
    ["mic",   -36.5, 11.6, "circle", 2.5,  0],
    ["phone", -27.0, 11.6, "circle", 7.0,  0],
    ["eth0",  -13.0, 16.5, "rect",  17.0, 15.0],
    ["eth1",    7.0, 16.5, "rect",  17.0, 15.0],
    ["hdmi",   24.0, 18.5, "rect",   6.0, 18.5],
    ["usb3",   41.0, 17.8, "rect",  17.0, 32.0],
    ["usb2",   59.0, 17.8, "rect",  15.5, 17.5]
];

inner_x = outer_x - 2 * wall;
inner_y = outer_y - wall - lid_t;
inner_z = outer_z - 2 * wall;

function y_pcb() = -outer_y / 2 + wall + 1.6;
function y_lid_inner() = outer_y / 2 - lid_t;

/**
 * 轴对齐圆角矩形，z=0 平面，中心原点。
 */
module rrect(w, h, r) {
    r2 = min(r, min(w, h) / 2 - 0.05);
    hull()
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (w / 2 - r2), sy * (h / 2 - r2)])
                circle(r = r2);
}

module box_outer() {
    cube([outer_x, outer_y, outer_z], center = true);
}

module box_cavity() {
    translate([0, -lid_t / 2, 0])
        cube([inner_x, inner_y, inner_z], center = true);
}

/**
 * 顶面通孔。PCB 元件面朝 +Y；孔中心 y = y_pcb + y_from_pcb。
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

module ffc_slot() {
    top_z = outer_z / 2 - wall / 2;
    translate([0, y_lid_inner() - 6, top_z])
        cube([ffc_w, 8, wall + 4], center = true);
}

module speaker_side(side) {
    sx = side * (outer_x / 2 - wall / 2);
    translate([sx, 0, 0]) {
        cube([wall + 4, spk_pw, spk_ph], center = true);
        for (dz = [-spk_pitch / 2, spk_pitch / 2])
            translate([0, 0, dz])
                rotate([0, 90, 0])
                    cylinder(d = spk_hd, h = wall + 8, center = true);
        for (dz = [-10, 0, 10])
            translate([side * (wall / 2 + 0.5), 0, dz])
                cube([3, spk_slot[0], spk_slot[1]], center = true);
    }
}

module vent_grid_on_face(w, h, t) {
    nx = max(1, floor((w - 12) / vent_pitch));
    for (i = [0 : nx - 1]) {
        x = -w / 2 + 8 + i * vent_pitch;
        translate([x, 0, 0])
            cube([vent_w, t + 0.2, h - 16], center = true);
    }
}

module vent_cutouts() {
    // 后壁 −Y
    translate([0, -outer_y / 2 + wall / 2, 0])
        rotate([90, 0, 0])
            vent_grid_on_face(inner_x - 20, inner_z, wall);
    // 底 −Z
    translate([0, -lid_t / 2, -outer_z / 2 + wall / 2])
        vent_grid_on_face(inner_x - 20, inner_y - 10, wall);
    // 左右：喇叭开口以外、靠后的条纹
    for (side = [-1, 1])
        translate([side * (outer_x / 2 - wall / 2), -outer_y / 6, 0])
            cube([wall + 4, vent_w, inner_z - 24], center = true);
}

module corner_inserts() {
    ix = inner_x / 2 - 6;
    iz = inner_z / 2 - 6;
    for (x = [-ix, ix], z = [-iz, iz])
        translate([x, y_lid_inner() - 6, z])
            rotate([90, 0, 0])
                cylinder(d = m3_insert_d, h = 8, center = true);
}

module lid_through_at_corners() {
    ix = inner_x / 2 - 6;
    iz = inner_z / 2 - 6;
    for (x = [-ix, ix], z = [-iz, iz])
        translate([x, outer_y / 2 - lid_t / 2, z])
            rotate([90, 0, 0])
                cylinder(d = m3_through, h = lid_t + 4, center = true);
}

module clamp_holes_in_lid() {
    h = plate_pitch / 2;
    for (x = [-h, h], z = [-h, h])
        translate([x, outer_y / 2 - lid_t / 2, z])
            rotate([90, 0, 0])
                cylinder(d = m3_insert_d, h = lid_t + 4, center = true);
}

module pcb_standoffs() {
    bx = board_x / 2 - hole_inset;
    bz = board_z / 2 - hole_inset;
    y0 = -outer_y / 2 + wall;
    for (x = [-bx, bx], z = [-bz, bz])
        translate([x, y0 + standoff_h / 2, z])
            difference() {
                cylinder(d = 8, h = standoff_h, center = true);
                cylinder(d = standoff_tap, h = standoff_h + 2, center = true);
            }
}

module board_box_shell() {
    difference() {
        box_outer();
        box_cavity();
        // 去掉盖所在的 +Y 薄板，留下五面
        translate([0, outer_y / 2 - lid_t / 2 + 0.01, 0])
            cube([outer_x + 2, lid_t + 0.2, outer_z + 2], center = true);
        port_cutouts();
        ffc_slot();
        speaker_side(-1);
        speaker_side(1);
        vent_cutouts();
        corner_inserts();
    }
    pcb_standoffs();
}

module board_box_lid() {
    difference() {
        translate([0, outer_y / 2 - lid_t / 2, 0])
            cube([outer_x, lid_t, outer_z], center = true);
        lid_through_at_corners();
        clamp_holes_in_lid();
    }
}

module board_box_preview() {
    color([0.12, 0.12, 0.14])
        board_box_shell();
    color([0.2, 0.2, 0.22, 0.7])
        board_box_lid();
}

if (part == "shell")
    board_box_shell();
else if (part == "lid")
    board_box_lid();
else
    board_box_preview();
```

- [ ] **Step 2: Open in OpenSCAD and check Customizer `part`**

```bash
# 若本机有 openscad CLI：
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m/scad
openscad -o /tmp/board_box_preview.stl --export-format binstl 50_board_box.scad
```

Expected: 退出码 0。若无 CLI，用 GUI 打开，`part=preview` 能看见开口朝外的壳体和半透明盖；`shell` / `lid` 各为一件。顶面一排孔、无 USB 凸包。

- [ ] **Step 3: Re-run unittest including the new scad file**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m
python -m unittest tests.test_board_box_geom.TestNoOpenscadV1Dependency -v
```

Expected: PASS（文件中无 `openscad_V1`）。

若顶面孔的局部 Y 和实物对不上：只改 `y_pcb()` 或 `ports` 的 `y_from_pcb`，并同步 `dims.json` 的 `y_from_pcb`。

---

### Task 3: `51_arm_clamp.scad`

**Files:**
- Create: `ai-microscope-edu/hardware/n117m/scad/51_arm_clamp.scad`

**Interfaces:**
- Consumes: `use <20_arm.scad>` 的 `y_back`、`arm_slice_2d`（`use` 不会执行 `20_arm` 顶层 `part` 渲染）；`dims.json` `arm_clamp`
- Produces: `arm_clamp_solid()`；矩形板在 C 形后侧（局部 −Y），4×M3 通孔，2×M4 φ3.6 顶丝

- [ ] **Step 1: Create `51_arm_clamp.scad`**

抱箍局部：原点在贴臂后表面中心；+Y 朝目镜（包住圆角）；+Z 沿立柱向上；板在 −Y。内宽 58+2×0.5，不调用 `arm_w_at` 当内宽。

```openscad
// N-117M 臂后 C 形顶丝抱箍 + 矩形板（一件）。
// 内宽卡尺 58，与 20_arm 立柱 62 分开。禁止 use openscad_V1。
// 导出：openscad -D 'part="clamp"' -o ../stl/arm_clamp.stl

use <20_arm.scad>

part = "preview"; // preview | clamp

$fn = 40;

inner_w = 58.0;
print_clear = 0.5;
clamp_h = 45.0;
wall = 4.0;
wrap_y = 22.0;
r_rear = 16.0;
plate_x = 70.0;
plate_z = 50.0;
plate_t = 6.0;
plate_pitch = 40.0;
m3_through = 3.2;
m4_tap_d = 3.6;
set_span = 24.0;

cavity_w = inner_w + 2 * print_clear;

/**
 * XY 截面：后圆角跑道，+Y 包到 wrap_y 后切平，前面开口让燕尾。
 */
module clamp_cavity_2d() {
    r = r_rear;
    w = cavity_w;
    hull() {
        translate([-w / 2 + r, r])
            circle(r = r);
        translate([w / 2 - r, r])
            circle(r = r);
        translate([-w / 2 + 1, wrap_y])
            circle(r = 1);
        translate([w / 2 - 1, wrap_y])
            circle(r = 1);
    }
}

module clamp_outer_2d() {
    offset(delta = wall)
        clamp_cavity_2d();
}

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
            // 矩形板在后表面外侧（−Y）
            translate([0, -plate_t / 2, 0])
                cube([plate_x, plate_t, plate_z], center = true);
        }
        h = plate_pitch / 2;
        for (x = [-h, h], z = [-h, h])
            translate([x, -plate_t / 2, z])
                rotate([90, 0, 0])
                    cylinder(d = m3_through, h = plate_t + wall + 4, center = true);
        for (z = [-set_span / 2, set_span / 2])
            translate([0, 0, z])
                rotate([90, 0, 0])
                    cylinder(d = m4_tap_d, h = 40, center = true);
    }
}

module arm_clamp_preview() {
    color([0.15, 0.15, 0.18])
        arm_clamp_solid();
    color([0.85, 0.85, 0.82, 0.25])
        linear_extrude(height = 3.2)
            arm_slice_2d(210);
}

if (part == "clamp")
    arm_clamp_solid();
else
    arm_clamp_preview();
```

`preview` 里半透明 `arm_slice_2d(210)` 会比卡尺内腔略宽（模型 62 vs 58），这是 spec 允许的；不要为了对齐去改 `20_arm`。

- [ ] **Step 2: Render clamp**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m/scad
openscad -o /tmp/arm_clamp.stl --export-format binstl -D 'part="clamp"' 51_arm_clamp.scad
```

Expected: 退出码 0。GUI 中 C 开口朝 +Y，板上 4 孔，后壁 2 个顶丝孔贯穿。

- [ ] **Step 3: Confirm no V1 include**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m
python -m unittest tests.test_board_box_geom.TestNoOpenscadV1Dependency -v
```

Expected: PASS。

---

### Task 4: 总装 `10_layout.scad` + README

**Files:**
- Modify: `ai-microscope-edu/hardware/n117m/scad/10_layout.scad`
- Modify: `ai-microscope-edu/hardware/n117m/README.md`

**Interfaces:**
- Consumes: `board_box_preview()`、`arm_clamp_solid()`；`y_back`、`arm_clamp.z0`
- Produces: `part=all` 时能同时看到臂、抱箍、盒；删掉或不再默认画旧 `electronics_tray`

- [ ] **Step 1: Add uses and assembly modules at the top of `10_layout.scad` after existing uses**

```openscad
use <50_board_box.scad>
use <51_arm_clamp.scad>
```

把文件头 `part` 注释改成：`part：arm | all | body | drive | box`。

在 `electronics_tray()` **之前**加入（数字与 `arm_clamp.z0`、盒 `outer_y` 一致）：

```openscad
clamp_z0 = 188;
clamp_h  = 45;
box_oy   = 66;
box_oz   = 115;

/**
 * 抱箍：后表面贴 y_back，底面在 clamp_z0。
 */
module n117m_arm_clamp_placed() {
    zb = y_back(clamp_z0 + clamp_h / 2);
    translate([0, zb, clamp_z0 + clamp_h / 2])
        arm_clamp_solid();
}

/**
 * 盒：盖朝臂。局部 +Y 已朝臂；盖外表面贴矩形板外侧。
 */
module n117m_board_box_placed() {
    zb = y_back(clamp_z0 + clamp_h / 2);
    plate_t = 6;
    // 抱箍原点在后表面；板在 −Y 占 plate_t；盖在盒局部 +outer_y/2
    translate([0, zb - plate_t - box_oy / 2, clamp_z0 + clamp_h / 2])
        board_box_preview();
}
```

- [ ] **Step 2: Replace `electronics_tray` usage**

删除（或留着但不要调用）`electronics_tray()`。改底部 `if`：

```openscad
if (part == "arm") {
    arm_casting();
}
else if (part == "body") {
    body_simple();
}
else if (part == "drive") {
    drive_z();
    drive_xy();
}
else if (part == "box") {
    arm_casting();
    n117m_arm_clamp_placed();
    n117m_board_box_placed();
}
else {
    body_simple();
    n117m_arm_clamp_placed();
    n117m_board_box_placed();
}
```

`part=="all"` 走最后的 `else`（当前文件里 `else` 就是 all）。不要再调用 `electronics_tray()`。电机皮带仍可留在 `drive`，本期总装默认 `all` 可以不画电机，避免和盒抢臂后空间：上面 `else` 已去掉 `drive_z/drive_xy`。若仍想对照旧电机占位，只在 `part=="drive"` 里画。

- [ ] **Step 3: Open `10_layout.scad` with `part="box"`**

目视清单：

1. 盒在臂后，顶面开孔朝上。  
2. 抱箍在粗调轮之上、z=250 前伸之下。  
3. 抱箍不包前缘燕尾。  
4. 不挡臂后底座 DC 座（近桌面）。  
5. 左右有喇叭开口。

若盒与手轮在 X 向相撞：把 `outer_x` 或 `translate` 的 X 仍保持 0（居中），左右喇叭在 ±90 mm，手轮在 ±X 臂侧约 ±31 mm、Y 在截面中部——盒在更负 Y，一般不相撞。若 GUI 里撞了，只把 `n117m_board_box_placed` 的 Y 再减 4～8 mm，并改 `dims.json` 注释，不要改手轮。

- [ ] **Step 4: Append README sections**（插在「镜臂」节之后，不要删相机盒说明）

```markdown
## 主板盒与抱箍

设计：[`../../docs/superpowers/specs/2026-09-08-board-box-arm-clamp-design.md`](../../docs/superpowers/specs/2026-09-08-board-box-arm-clamp-design.md)。

耗材 **PETG-CF**，喷嘴 **0.6 mm 硬化钢**；不要用红色普通 PETG。层高 0.16–0.20，壁 ≥4 圈。壳体后壁朝床；盖平打；抱箍顶丝孔水平打。

```bash
cd hardware/n117m/scad
openscad -o ../stl/board_box_shell.stl -D 'part="shell"' 50_board_box.scad
openscad -o ../stl/board_box_lid.stl   -D 'part="lid"'   50_board_box.scad
openscad -o ../stl/arm_clamp.stl       -D 'part="clamp"' 51_arm_clamp.scad
```

总装：打开 `10_layout.scad`，`part="box"` 或 `all`。

合箱 M3 四角；盖中央 40×40 M3 对抱箍；抱箍 2×M4 顶丝（底孔 3.6）加垫片。USB 无凸盖。喇叭 36×18，沉槽 20.5×39。
```

- [ ] **Step 5: Run the full n117m unittest set**

```bash
cd /Users/alex/code/ai-microscope-design/ai-microscope-edu/hardware/n117m
python -m unittest discover -s tests -v
```

Expected: 全部 PASS，包括原相机盒 / 镜臂 / 布局测试和新的 `test_board_box_geom`。

---

## Self-review

**Spec coverage:** 依赖边界（Task 1 扫描 + Task 2/3 无 V1）→ 盒体外廓/开孔/无 USB 盖/FFC/喇叭/条纹/合箱（Task 2）→ 抱箍 C 形/58 mm/2×M4/40×40（Task 3）→ 总装高度与 README 材料（Task 4）→ 屏支架未做（非目标）。

**Placeholder scan:** 无 TBD。CLI 没有 OpenSCAD 时用 GUI，步骤里已写。

**Type consistency:** `outer_xyz` [180,66,115]、`inner_w` 58、`z0` 188、`plate_pitch` 40、`vent_w` 2.4、`ffc_slot_w` 17.2 在 json / py / scad 三处同值。
