# 10 寸屏横梁支架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打出横梁骑坐抱箍 + 左右托盘两半，屏 258×168 三边咬 2.3 mm 边框，可在 X1C 上平放打印。

**Architecture:** 数字在 `dims.json` 的 `screen` / `beam_clamp`，几何函数 `screen_geom.py`，一件 `52_beam_clamp.scad` 用 `part` 导出三件（抱箍、左右托盘）。背面顶条把 U 收成矩形。总装只在 `10_layout.scad` 挂上示意。不 `use` openscad_V1。

**Tech Stack:** OpenSCAD、Python unittest、PETG-CF / 0.6 mm 喷嘴。

## Global Constraints

- 只改 `ai-microscope-edu/`；scad 禁止 `use`/`include` `openscad_V1/`
- 触屏面 258×168、边框 2.3、钢凸 4、槽 2.8、横梁宽 57.5、内腔 60.5
- 不包弓底；顶丝左右 M4 φ3.6；托盘两半 M3 螺杆螺帽
- 单件外廓 < 250 mm；不 commit，除非用户要求

---

### Task 1: dims + screen_geom + 测试

**Files:**
- Modify: `ai-microscope-edu/hardware/n117m/dims.json`
- Create: `ai-microscope-edu/hardware/n117m/screen_geom.py`
- Create: `ai-microscope-edu/hardware/n117m/tests/test_screen_geom.py`

**Interfaces:**
- Consumes: spec 2026-09-09
- Produces: `slot_w(bezel, clear)`, `tray_inner_wh(face_w, face_h, edge_clear)`, `tray_half_span(inner_w)`, `fits_x1c_bed(w, h)`, `clamp_cavity_w` 复用 board_box_geom

- [x] **Step 1: 写失败测试**（见实现时的 `test_screen_geom.py`）
- [x] **Step 2: 跑测试确认 RED**
- [x] **Step 3: 写 dims.json 与 screen_geom.py**
- [x] **Step 4: 测试 GREEN**

不单独 commit。

---

### Task 2: `52_beam_clamp.scad`

**Files:**
- Create: `ai-microscope-edu/hardware/n117m/scad/52_beam_clamp.scad`

**Interfaces:**
- Consumes: Task 1 数字抄到文件顶
- Produces: `beam_saddle()`、`cross_arm(side)`、`screen_tray(side)`；`part` = preview | clamp | arm_l | arm_r | tray_l | tray_r

- [x] **Step 1: 测试解析 scad：无 openscad_V1；含 saddle 开口、m4_tap、tray 槽 2.8、拼缝 m3_through**
- [x] **Step 2: 实现 scad**
- [x] **Step 3: unittest GREEN；openscad 能导出三件**

---

### Task 3: layout、README、螺丝表、spec 状态

**Files:**
- Modify: `scad/10_layout.scad`、`hardware/n117m/README.md`、`measure_sheet.md`、spec 状态行

- [x] **Step 1: 总装置屏支架示意**
- [x] **Step 2: 导出命令与屏支架螺丝**
- [x] **Step 3: 全量 unittest**
