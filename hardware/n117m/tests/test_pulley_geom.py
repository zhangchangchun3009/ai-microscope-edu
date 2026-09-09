"""Z 微调剖分轮：齿圈略大于原蓝套手轮；腹板短而薄。"""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_N117M))

from pulley_geom import (  # noqa: E402
    MIN_RIM_MM,
    belt_clears_outer_ears,
    gt2_od,
    gt2_pd,
    m3_fits_in_web,
    pulley_fits_hub,
    rim_radial,
    web_just_taller_than_belt,
)

HUB = json.loads((_N117M / "dims.json").read_text())["z_fine_hub"]
HUB_OD = HUB["od_peak"]
BLUE_OD = HUB["blue_sleeve_od_max"]


class TestPulleyGeom(unittest.TestCase):
    def test_gt2_20t_od_matches_common_stock(self):
        self.assertAlmostEqual(gt2_od(20), 12.224, delta=0.05)

    def test_48t_rim_thick_enough_for_fdm(self):
        self.assertGreaterEqual(rim_radial(48, HUB_OD), MIN_RIM_MM)

    def test_40t_rim_too_thin_for_20mm_hub(self):
        self.assertLess(rim_radial(40, HUB_OD), MIN_RIM_MM)

    def test_48t_od_just_above_blue_knob(self):
        """齿顶圆略大于原蓝套 28.5mm，不必撑到 72 齿。"""
        od = gt2_od(48)
        self.assertGreater(od, BLUE_OD)
        self.assertLess(od, BLUE_OD + 6.0)

    def test_48t_web_cannot_fit_m3_so_ears_stay_outside(self):
        self.assertFalse(m3_fits_in_web(48, HUB_OD))

    def test_web_height_only_slightly_above_belt(self):
        self.assertTrue(web_just_taller_than_belt(6.0, 6.0))

    def test_ear_cannot_be_as_thin_as_flange(self):
        from pulley_geom import ear_h_fits_m3

        self.assertFalse(ear_h_fits_m3(0.8))
        self.assertTrue(ear_h_fits_m3(6.0))

    def test_coplanar_height_fits_z_hub(self):
        pulley_h = 0.8 + 6.0 + 0.8
        self.assertTrue(
            pulley_fits_hub(pulley_h, HUB["axial_protrusion"], standoff=1.5)
        )

    def test_pitch_diameter_formula(self):
        self.assertAlmostEqual(gt2_pd(48), 48 * 2.0 / math.pi)

    def test_outer_ears_leave_belt_gap(self):
        """夹耳贴着挡边，只留带厚量级的缝，不拉长薄片。"""
        od = gt2_od(48)
        flange_over, belt_gap = 1.2, 1.2
        ear_inner = od / 2.0 + flange_over + belt_gap
        self.assertTrue(belt_clears_outer_ears(ear_inner, od, gap=0.5))
        self.assertLess(belt_gap, 2.0)


if __name__ == "__main__":
    unittest.main()
