"""相机盒：φ25 滑套 + 原 OpenFlexure 矩形感光开口。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_N117M))

from camera_box_geom import (  # noqa: E402
    OF_WINDOW_R,
    OF_WINDOW_X,
    OF_WINDOW_Y,
    m4_engagement,
    sensor_z,
    sleeve_id,
    sleeve_wall,
    tube_stopped_by_window,
)

DIMS = json.loads((_N117M / "dims.json").read_text())


class TestSleeveFit(unittest.TestCase):
    def test_bore_is_tube_plus_print_clearance(self):
        sleeve = DIMS["sleeve"]
        self.assertAlmostEqual(
            sleeve_id(sleeve["tube_od"], sleeve["print_clear"]),
            25.60,
            places=2,
        )

    def test_sleeve_uses_full_exposed_cylinder(self):
        self.assertEqual(DIMS["sleeve"]["h"], 17.0)
        self.assertEqual(DIMS["sleeve"]["tube_od"], 25.0)

    def test_wall_plus_boss_gives_m4_thread_length(self):
        sleeve = DIMS["sleeve"]
        inner = sleeve_id(sleeve["tube_od"], sleeve["print_clear"])
        wall = sleeve_wall(sleeve["collar_od"], inner)
        eng = m4_engagement(wall, sleeve["boss_h"])
        self.assertGreaterEqual(wall, 5.0)
        self.assertEqual(sleeve["boss_h"], 0)
        self.assertAlmostEqual(eng, wall, places=2)

    def test_m4_tap_is_smaller_than_major(self):
        self.assertEqual(DIMS["sleeve"]["set_screw"], "M4")
        self.assertAlmostEqual(DIMS["sleeve"]["tap_d"], 3.6, places=1)
        self.assertLess(DIMS["sleeve"]["tap_d"], 4.0)


class TestOpenFlexureSensorWindow(unittest.TestCase):
    def test_window_matches_imx678_20_spacer(self):
        """矩形开口，不小于原垫片，且仍挡住 φ25 筒。"""
        win = DIMS["box"]["sensor_window"]
        self.assertGreaterEqual(win["x"], OF_WINDOW_X)
        self.assertGreaterEqual(win["y"], OF_WINDOW_Y)
        self.assertEqual(win["r"], OF_WINDOW_R)
        self.assertEqual(win["x"], 18.0)
        self.assertEqual(win["y"], 16.0)

    def test_window_stops_25mm_tube(self):
        sleeve = DIMS["sleeve"]
        win = DIMS["box"]["sensor_window"]
        self.assertTrue(
            tube_stopped_by_window(sleeve["tube_od"], win["x"], win["y"])
        )

    def test_pcb_and_holes_stay_on_pc_oic678(self):
        cam = DIMS["camera"]
        self.assertEqual(cam["pcb_xy"], 32.0)
        self.assertEqual(cam["hole_pitch"], 27.0)


class TestOpticalStack(unittest.TestCase):
    def test_seated_sensor_is_c_mount_distance_above_sleeve_top(self):
        sleeve = DIMS["sleeve"]
        box = DIMS["box"]
        z = sensor_z(sleeve["h"], box["sleeve_top_to_sensor"])
        self.assertAlmostEqual(z, 17.0 + 17.526, places=3)
        self.assertAlmostEqual(z - sleeve["h"], 17.526, places=3)


if __name__ == "__main__":
    unittest.main()
