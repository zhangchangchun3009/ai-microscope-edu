"""屏支架尺寸：与 spec 和 dims.json 一致。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_N117M))

from board_box_geom import clamp_cavity_w  # noqa: E402
from screen_geom import (  # noqa: E402
    back_beam_interior_deg,
    baffle_inward,
    beam_join_y,
    beam_rise,
    beam_tilt_deg,
    fits_x1c_bed,
    screen_contact_y,
    screen_origin_yz,
    stack_well_h,
    steel_wh,
    steel_window_w,
    patch_r_inner_x,
    tray_half_span,
    tray_inner_wh,
    tube_axis_y,
)

DIMS = json.loads((_N117M / "dims.json").read_text())
SCAD = _N117M / "scad"


class TestScreenFace(unittest.TestCase):
    def test_face_glass_and_steel_insets(self):
        s = DIMS["screen"]
        self.assertEqual(s["face_wh"], [258.0, 168.0])
        self.assertEqual(s["glass_t"], 2.3)
        self.assertEqual(s["steel_proud"], 4.0)
        self.assertEqual(s["steel_inset_tb"], 13.0)
        self.assertEqual(sorted(s["steel_inset_lr"]), [13.0, 17.0])
        sw, sh = steel_wh(
            s["face_wh"][0],
            s["face_wh"][1],
            s["steel_inset_tb"],
            s["steel_inset_lr"][0],
            s["steel_inset_lr"][1],
        )
        self.assertAlmostEqual(sw, 228.0, places=1)
        self.assertAlmostEqual(sh, 142.0, places=1)
        # 后窗按较小侧边距居中，13/17 对调都能过
        self.assertAlmostEqual(
            steel_window_w(s["face_wh"][0], s["steel_inset_lr"]), 232.0, places=1
        )
        inner = tray_inner_wh(s["face_wh"][0], s["face_wh"][1], s["edge_clear"])
        self.assertAlmostEqual(inner[0], 258.8, places=1)
        self.assertAlmostEqual(inner[1], 168.8, places=1)

    def test_baffles_above_steel_plane(self):
        s = DIMS["screen"]
        self.assertEqual(s["baffle_side"], 3.5)
        self.assertEqual(s["baffle_bottom"], 10.0)
        self.assertEqual(s["baffle_bottom_deg"], 60.0)
        self.assertGreater(s["baffle_side"], s["glass_t"])
        self.assertAlmostEqual(baffle_inward(10.0, 60.0), 10.0 / 3**0.5, places=2)
        self.assertAlmostEqual(s["glass_t"] + s["baffle_side"], 5.8, places=1)
        # 底楔先有直角井再 60°，斜边仍伸不进钢板区
        self.assertLess(
            s["front_lip"] + baffle_inward(s["baffle_bottom"], s["baffle_bottom_deg"]),
            s["steel_inset_tb"],
        )
        self.assertAlmostEqual(
            stack_well_h(s["glass_t"], s["steel_pocket_d"]), 7.3, places=1
        )
        self.assertEqual(s["seam_overlap"], 2.0)
        # 两级台阶：外框挡玻璃，内框镂空嵌满 4–5 mm 钢板
        self.assertEqual(s["steel_pocket_d"], 5.0)
        self.assertGreaterEqual(s["steel_pocket_d"], s["steel_proud"])
        self.assertEqual(s["steel_clear"], 2.0)
        self.assertEqual(s["outer_extra"], 4.0)


class TestTraySplitFitsBed(unittest.TestCase):
    def test_each_half_shorter_than_x1c(self):
        s = DIMS["screen"]
        inner_w, inner_h = tray_inner_wh(s["face_wh"][0], s["face_wh"][1], s["edge_clear"])
        half = tray_half_span(inner_w)
        self.assertLess(half, 250.0)
        self.assertTrue(fits_x1c_bed(half + 20.0, inner_h + 20.0))
        self.assertFalse(fits_x1c_bed(258.0, 168.0))


class TestTrayPatchForPrintedLeft(unittest.TestCase):
    """已打左半只包 128 mm；右补救件包剩余 130 mm。正式左右仍中线重叠。"""

    def test_patch_covers_remaining_130(self):
        s = DIMS["screen"]
        p = DIMS["tray_patch"]
        self.assertEqual(p["printed_side"], "left")
        self.assertEqual(p["printed_cover"], 128.0)
        self.assertEqual(p["remain_cover"], 130.0)
        self.assertAlmostEqual(
            p["printed_cover"] + p["remain_cover"], s["face_wh"][0], places=1
        )
        x0 = patch_r_inner_x(s["face_wh"][0], p["printed_cover"])
        self.assertAlmostEqual(x0, -1.0, places=1)
        text = (SCAD / "52_beam_clamp.scad").read_text(encoding="utf-8")
        self.assertIn('part="tray_r_patch"', text)
        self.assertIn("module screen_tray_r_patch(", text)
        self.assertIn("stack_h = glass_t + steel_pocket_d", text)
        self.assertIn("seam_overlap = 2.0", text)
        self.assertIn("print_left_cover = 128.0", text)
        self.assertIn("well = false", text)
        self.assertIn("module bottom_baffle_printed_2d(", text)


class TestBeamClamp(unittest.TestCase):
    def test_same_width_as_column_caliper(self):
        b = DIMS["beam_clamp"]
        self.assertEqual(b["beam_w_caliper"], 57.5)
        self.assertEqual(b["print_clear"], 0.5)
        self.assertAlmostEqual(
            clamp_cavity_w(b["beam_w_caliper"], b["print_clear"]), 58.5, places=1
        )
        self.assertEqual(b["inner_w"], 58.5)
        text = (SCAD / "52_beam_clamp.scad").read_text(encoding="utf-8")
        self.assertIn("print_clear = 0.5", text)
        self.assertEqual(b["m4_tap_d"], 3.6)
        self.assertFalse(b.get("m4_top", False))
        self.assertEqual(b["neck_x"], 5.4)
        self.assertEqual(b["neck_x"], b["tongue_t"])
        self.assertEqual(b["hinge_cut_h"], 9.4)
        self.assertEqual(b["hinge_cut_h"], b["tongue_t"] + 4)
        self.assertEqual(b["wrap_bottom"], False)
        self.assertEqual(b["set_screws"], 2)
        self.assertEqual(b["standoff"], 45.0)
        self.assertEqual(b["slide_slot"], 30.0)
        self.assertEqual(b["open_toward"], "arm")
        self.assertEqual(b["tilt_from_vert"], 45.0)
        self.assertEqual(b["wrap_bottom"], False)
        self.assertEqual(b["m3_hex_len"], 30)
        self.assertEqual(b["m3_nut_af"], 5.5)
        self.assertEqual(b["m3_nut_h"], 2.4)
        self.assertEqual(b["m3_nut_pocket_d"], 3.0)
        self.assertEqual(b["bar_w"], 22.0)
        self.assertEqual(b["arc_a0"], 0.0)
        self.assertEqual(b["arc_a1"], -90.0)
        self.assertNotIn("tilt_range", b)
        self.assertEqual(b["tongue_r"], 16.0)
        self.assertEqual(b["wrap_down"], 15.0)
        self.assertLessEqual(b["wrap_down"], DIMS["cross_beam"]["wrap_max"])
        # 半框 L + 顶条，小于床；整屏 258 打不出
        self.assertTrue(fits_x1c_bed(160.0, 200.0))
        self.assertFalse(fits_x1c_bed(258.0, 168.0))


class TestScad(unittest.TestCase):
    def test_52_has_saddle_baffle_standoff_and_no_v1(self):
        text = (SCAD / "52_beam_clamp.scad").read_text(encoding="utf-8")
        self.assertIn("module beam_saddle()", text)
        self.assertIn("module screen_tray(", text)
        self.assertIn("m4_tap_d", text)
        self.assertIn("hinge_cut_h = tongue_t + 4", text)
        self.assertIn("h = hinge_cut_h", text)
        self.assertIn("cube([tongue_t, 16, 6]", text)
        self.assertNotIn("cube([24, 16, 6]", text)
        self.assertNotIn("m4_top_x", text)
        self.assertNotIn("module beam_saddle_top_m4(", text)
        self.assertIn("module beam_saddle_cavity(", text)
        self.assertIn("beam_saddle_cavity()", text)
        self.assertIn("m3_through", text)
        self.assertIn('part="clamp"', text)
        self.assertIn('part="saddle"', text)
        self.assertIn("module saddle_solid(", text)
        self.assertIn("module beam_clamp_plate(", text)
        self.assertIn("arc_a0 = 0", text)
        self.assertIn("arc_a1 = -90", text)
        self.assertIn("arc_n = 8", text)
        self.assertNotIn("tilt_range = 25.0", text)
        self.assertIn("-tilt_from_vert", text)
        self.assertIn("baffle_side = 3.5", text)
        self.assertIn("baffle_bottom = 10.0", text)
        self.assertIn("baffle_bottom_deg = 60.0", text)
        self.assertIn("stack_h = glass_t + steel_pocket_d", text)
        self.assertIn("seam_overlap = 2.0", text)
        self.assertIn('part="tray_r_patch"', text)
        self.assertIn("module screen_tray_r_patch(", text)
        self.assertIn("wrap_down = 15.0", text)
        self.assertIn("standoff = 45.0", text)
        self.assertIn("slide_slot = 30.0", text)
        self.assertIn("len_along + 2", text)
        self.assertIn("module tray_ring(", text)
        self.assertIn("module mid_bar()", text)
        self.assertIn("module hex_nut_pocket(", text)
        self.assertIn("bar_w = 22.0", text)
        self.assertIn("m3_nut_pocket_d = 3.0", text)
        self.assertNotIn("mid_bar(side)", text)
        self.assertIn("ox + wall_t / 2", text)
        self.assertIn("side * bar_hole_x", text)
        self.assertIn("steel_pocket_d = 5.0", text)
        self.assertIn("outer_extra = 4.0", text)
        self.assertIn("explode_x", text)
        self.assertIn("module beam_clamp_assembled(", text)
        self.assertIn('part="bar"', text)
        self.assertIn('part="explode"', text)
        self.assertIn("cable_gap", text)
        self.assertNotIn('part="arm_l"', text)
        self.assertNotIn("module cross_arm(", text)
        self.assertNotIn("module vert_rail(", text)
        self.assertNotIn("module tray_spokes(", text)
        self.assertIn("glass_t + baffle_side", text)
        self.assertNotIn("edge_clear - front_lip", text)
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            self.assertNotIn("openscad_V1", stripped, msg=f"52:{i}")

    def test_layout_uses_beam_clamp(self):
        text = (SCAD / "10_layout.scad").read_text(encoding="utf-8")
        self.assertIn("52_beam_clamp.scad", text)
        self.assertIn("n117m_screen_placed", text)
        self.assertIn("screen_contact_y()", text)
        self.assertIn('part = "all"', text)
        self.assertIn("n117m_screen_placed();", text)
        self.assertIn("module cross_beam(", (SCAD / "20_arm.scad").read_text(encoding="utf-8"))
        arm = (SCAD / "20_arm.scad").read_text(encoding="utf-8")
        self.assertIn("module beam_bow_2d(", arm)
        self.assertIn("function beam_join_y()   = back_y_column", arm)
        self.assertIn("function y_front(z) = front_y0", arm)


class TestCrossBeamLandmarks(unittest.TestCase):
    """E 组：15 cm 卡尺分段；角度由三角形算，不手量。"""

    def test_tilt_from_hyp_and_horiz(self):
        b = DIMS["cross_beam"]
        self.assertEqual(b["width"], 57.5)
        self.assertEqual(b["wrap_max"], 17.0)
        self.assertEqual(b["bow_r"], 90.0)
        self.assertEqual(b["join_z"], 240.0)
        self.assertEqual(b["hyp"], 98.0)
        self.assertEqual(b["horiz"], 92.0)
        self.assertAlmostEqual(beam_rise(98.0, 92.0), 33.76, places=1)
        self.assertAlmostEqual(beam_tilt_deg(98.0, 92.0), 20.1, places=0)
        self.assertAlmostEqual(b["join_z"] + beam_rise(98.0, 92.0), 273.8, places=0)
        back = DIMS["arm"]["back_y_column"]
        self.assertEqual(beam_join_y(back), back)
        ang = back_beam_interior_deg(98.0, 92.0)
        self.assertGreater(ang, 90.0)
        self.assertLess(ang, 180.0)
        self.assertAlmostEqual(ang, 110.0, places=0)

    def test_tube_contact_from_arm_back(self):
        b = DIMS["cross_beam"]
        arm = DIMS["arm"]
        self.assertEqual(b["tube_d_contact"], 42.0)
        self.assertEqual(b["axis_from_back"], 135.0)
        self.assertAlmostEqual(
            tube_axis_y(arm["back_y_column"], b["axis_from_back"]), 27.0, places=1
        )
        cy = screen_contact_y(
            arm["back_y_column"], b["axis_from_back"], b["tube_d_contact"]
        )
        self.assertAlmostEqual(cy, 6.0, places=1)
        oy, oz = screen_origin_yz(cy, b["contact_z"], 168.0, 45.0)
        self.assertAlmostEqual(oz, 259.2, places=0)
        self.assertLess(oy, arm["back_y_column"] + 10)


if __name__ == "__main__":
    unittest.main()
