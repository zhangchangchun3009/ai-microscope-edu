"""镜臂轮廓：后表面圆角给抱箍，侧视 C 形按商店图包络。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
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

    def test_handle_sits_above_z_knobs(self):
        arm = DIMS["arm"]
        z_axis = DIMS["xy_knobs"]["z_hub_bottom_from_desk"] + DIMS["z_fine_hub"]["od_peak"] / 2
        handle_bottom = arm["handle"]["cz"] - arm["handle"]["rz"]
        self.assertGreater(handle_bottom, z_axis + 15)

    def test_z_axis_height_matches_caliper(self):
        z_axis = DIMS["xy_knobs"]["z_hub_bottom_from_desk"] + DIMS["z_fine_hub"]["od_peak"] / 2
        self.assertAlmostEqual(z_axis, 110.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
