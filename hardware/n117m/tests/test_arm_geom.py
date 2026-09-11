"""镜臂轮廓：背面竖直给抱箍，前缘直线；横梁与观察室/转换器连成一件。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
SCAD = _N117M / "scad"
DIMS = json.loads((_N117M / "dims.json").read_text())


class TestArmGeom(unittest.TestCase):
    def test_arm_section_present(self):
        self.assertIn("arm", DIMS)

    def test_rear_has_flat_plus_small_fillet(self):
        """后视：大平面 + 很小后圆角，近似直角。"""
        arm = DIMS["arm"]
        self.assertGreaterEqual(arm["r_rear"], 2.0)
        self.assertLessEqual(arm["r_rear"], 5.0)
        flat = arm["width_column"] - 2 * arm["r_rear"]
        self.assertGreaterEqual(flat, 48.0)

    def test_column_fits_base_and_sits_at_rear(self):
        arm = DIMS["arm"]
        base_w, base_d = DIMS["layout"]["base_xy"]
        self.assertLess(arm["width_column"], base_w)
        self.assertLess(arm["front_y"], 0)
        self.assertLess(arm["back_y_column"], arm["front_y"])
        self.assertGreaterEqual(arm["back_y_column"], -base_d / 2 - 2)

    def test_no_handle_cutout(self):
        """实物立柱中间没有提手通孔。"""
        self.assertNotIn("handle", DIMS["arm"])
        arm = (SCAD / "20_arm.scad").read_text(encoding="utf-8")
        self.assertNotIn("handle_cut", arm)
        self.assertNotIn("handle_cy", arm)

    def test_column_same_width_as_beam_caliper(self):
        """抱箍以上立柱与横梁同宽，不再上小下大。底座根部仍放宽。"""
        arm = DIMS["arm"]
        self.assertEqual(arm["width_column"], 57.5)
        self.assertEqual(arm["width_column"], DIMS["cross_beam"]["width"])
        self.assertGreater(arm["width_base_flare"], arm["width_column"])
        text = (SCAD / "20_arm.scad").read_text(encoding="utf-8")
        self.assertIn("arm_w         = 57.5", text)
        self.assertNotIn("[400, 58]", text)

    def test_z_axis_height_matches_caliper(self):
        z_axis = DIMS["xy_knobs"]["z_hub_bottom_from_desk"] + DIMS["z_fine_hub"]["od_peak"] / 2
        self.assertAlmostEqual(z_axis, 110.0, delta=0.5)

    def test_beam_reaches_observation_and_nosepiece(self):
        """梁梢到三目轴这一段由头座填满，观察室坐上、转换器挂下。"""
        arm = DIMS["arm"]
        beam = DIMS["cross_beam"]
        back = arm["back_y_column"]
        beam_far_y = back + beam["horiz"]
        tube_y = back + beam["axis_from_back"]
        self.assertGreater(tube_y, beam_far_y)
        self.assertGreater(tube_y - beam_far_y, 30.0)
        text = (SCAD / "20_arm.scad").read_text(encoding="utf-8")
        self.assertIn("module arm_c_2d(", text)
        self.assertIn("module head_housing(", text)
        self.assertIn("module nosepiece(", text)
        self.assertIn("head_housing()", text)
        self.assertIn("nosepiece()", text)
        self.assertIn("join_fillet", text)
        self.assertIn("join_arc", text)


if __name__ == "__main__":
    unittest.main()
