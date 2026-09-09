"""总体布局尺寸：B 组行程应接近说明书 24mm 调焦。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
DIMS = json.loads((_N117M / "dims.json").read_text())


class TestLayoutDims(unittest.TestCase):
    def test_xy_follows_focus_travel(self):
        xy = DIMS["xy_knobs"]
        travel = xy["lower_bottom_min_focus"] - xy["lower_bottom_max_focus"]
        self.assertAlmostEqual(travel, 24.0, delta=2.0)

    def test_z_hub_higher_than_xy_at_min_focus(self):
        xy = DIMS["xy_knobs"]
        self.assertGreater(
            xy["z_hub_bottom_from_desk"], xy["lower_bottom_min_focus"]
        )

    def test_trinocular_envelope(self):
        lay = DIMS["layout"]
        self.assertEqual(lay["base_xy"], [167, 224])
        self.assertEqual(lay["height_trinocular"], 430)


if __name__ == "__main__":
    unittest.main()
