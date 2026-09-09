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
    baffle_inward,
    fits_x1c_bed,
    steel_wh,
    steel_window_w,
    tray_half_span,
    tray_inner_wh,
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
        # 两块侧挡内沿间距 = 玻璃宽 + 两侧间隙；底楔伸进开孔小于钢板边距
        self.assertAlmostEqual(
            s["face_wh"][0] + 2.0 * s["edge_clear"], 258.8, places=1
        )
        self.assertLess(
            s["front_lip"] + baffle_inward(s["baffle_bottom"], s["baffle_bottom_deg"]),
            s["steel_inset_tb"],
        )


class TestTraySplitFitsBed(unittest.TestCase):
    def test_each_half_shorter_than_x1c(self):
        s = DIMS["screen"]
        inner_w, inner_h = tray_inner_wh(s["face_wh"][0], s["face_wh"][1], s["edge_clear"])
        half = tray_half_span(inner_w)
        self.assertLess(half, 250.0)
        self.assertTrue(fits_x1c_bed(half + 20.0, inner_h + 20.0))
        self.assertFalse(fits_x1c_bed(258.0, 168.0))


class TestBeamClamp(unittest.TestCase):
    def test_same_width_as_column_caliper(self):
        b = DIMS["beam_clamp"]
        self.assertEqual(b["beam_w_caliper"], 57.5)
        self.assertEqual(b["print_clear"], 1.5)
        self.assertAlmostEqual(
            clamp_cavity_w(b["beam_w_caliper"], b["print_clear"]), 60.5, places=1
        )
        self.assertEqual(b["inner_w"], 60.5)
        self.assertEqual(b["m4_tap_d"], 3.6)
        self.assertEqual(b["wrap_bottom"], False)
        self.assertEqual(b["set_screws"], 2)
        self.assertEqual(b["standoff"], 45.0)
        self.assertEqual(b["slide_slot"], 30.0)
        self.assertEqual(b["open_toward"], "arm")
        self.assertEqual(b["tilt_from_vert"], 45.0)
        self.assertEqual(b["wrap_bottom"], False)
        # 半框 L + 顶条，小于床；整屏 258 打不出
        self.assertTrue(fits_x1c_bed(160.0, 200.0))
        self.assertFalse(fits_x1c_bed(258.0, 168.0))


class TestScad(unittest.TestCase):
    def test_52_has_saddle_baffle_standoff_and_no_v1(self):
        text = (SCAD / "52_beam_clamp.scad").read_text(encoding="utf-8")
        self.assertIn("module beam_saddle()", text)
        self.assertIn("module screen_tray(", text)
        self.assertIn("m4_tap_d", text)
        self.assertIn("m3_through", text)
        self.assertIn('part="clamp"', text)
        self.assertIn("baffle_side = 3.5", text)
        self.assertIn("baffle_bottom = 10.0", text)
        self.assertIn("baffle_bottom_deg = 60.0", text)
        self.assertIn("standoff = 45.0", text)
        self.assertIn("slide_slot = 30.0", text)
        self.assertIn("len_along + 2", text)
        self.assertIn("module top_bar(", text)
        self.assertIn("module back_spine(", text)
        self.assertIn("ox + wall_t / 2", text)
        self.assertIn("cable_gap", text)
        self.assertNotIn('part="arm_l"', text)
        self.assertNotIn("module cross_arm(", text)
        self.assertNotIn("module vert_rail(", text)
        self.assertNotIn("module tray_spokes(", text)
        self.assertIn("glass_t + baffle_side", text)
        # 侧挡不向开孔内翻边
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


if __name__ == "__main__":
    unittest.main()
