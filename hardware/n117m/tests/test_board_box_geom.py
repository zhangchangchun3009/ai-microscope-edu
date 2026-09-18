"""主板盒 / 抱箍尺寸：与 spec 和 dims.json 一致，scad 不依赖 openscad_V1。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_N117M = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_N117M))

from board_box_geom import (  # noqa: E402
    DRAWER_PORT_X,
    clamp_cavity_w,
    ffc_slot_w,
    lid_nut_boss_xz_y,
    m3_nut_af,
    m3_nut_h,
    m3_self_tap_d,
    min_outer_y_for_usb3,
    mount_hole_xy,
    pcb_standoff_axis,
    pcb_standoff_z,
    pcb_z_offset,
    port_centers,
    port_fit_clip_z,
    speaker_old_stand_boss_xy,
    speaker_old_stand_pocket,
    speaker_old_stand_slot,
    speaker_old_stand_slot_z,
    speaker_pocket,
    speaker_pocket_x,
    speaker_screw_x,
    usb2_outer_to_standoff_x,
    y_port_datum,
)

DIMS = json.loads((_N117M / "dims.json").read_text())
SCAD = _N117M / "scad"


class TestBoardEnvelope(unittest.TestCase):
    def test_lubancat_board_150x90_inset_4(self):
        b = DIMS["board_box"]
        self.assertEqual(b["board_xy"], [150.0, 90.0])
        self.assertEqual(b["hole_inset"], 4.0)
        self.assertEqual(b["port_panel_h"], 53.5)

    def test_outer_matches_spec_start(self):
        b = DIMS["board_box"]
        self.assertEqual(b["outer_xyz"], [180.0, 50.0, 115.0])
        self.assertEqual(b["wall"], 2.5)
        self.assertEqual(b["lid_t"], 3.0)
        self.assertGreaterEqual(
            b["outer_xyz"][1],
            min_outer_y_for_usb3(y_from_pcb=23.8),
        )

    def test_no_usb_shroud_flag(self):
        self.assertFalse(DIMS["board_box"]["usb_shroud"])


class TestPortsAndFfc(unittest.TestCase):
    def test_ports_mirrored_vs_old_drawer_when_components_face_lid(self):
        """旧抽屉从盒外看 DC 在 −X；竖盒且元件朝盖时左右对调。"""
        self.assertEqual(DRAWER_PORT_X["dc"], -62.0)
        self.assertEqual(DRAWER_PORT_X["usb2"], 59.0)
        xs = {p["name"]: p["x"] for p in DIMS["board_box"]["ports"]}
        self.assertEqual(xs["dc"], 62.0)
        self.assertEqual(xs["typec"], 47.5)
        self.assertEqual(xs["mic"], 36.5)
        self.assertEqual(xs["phone"], 27.0)
        self.assertEqual(xs["eth0"], 13.0)
        self.assertEqual(xs["eth1"], -7.0)
        self.assertEqual(xs["hdmi"], -24.0)
        self.assertEqual(xs["usb3"], -41.0)
        self.assertEqual(xs["usb2"], -59.0)
        self.assertEqual(port_centers()["mic"][0], 36.5)
        self.assertEqual(port_centers()["dc"][0], -DRAWER_PORT_X["dc"])
        ys = {p["name"]: p["y_from_pcb"] for p in DIMS["board_box"]["ports"]}
    def test_usb2_edge_to_standoff_matches_old_drawer(self):
        """沿接口面长边：靠 USB2 柱心到 USB2 开口外侧边 = 原抽屉 71−66.75 = 4.25 mm。

        开口高度（Y）已用 USB3 下沿核对；这一向防止接口进槽后螺丝沿 150 mm 偏 1 mm。
        """
        b = DIMS["board_box"]
        usb2 = next(p for p in b["ports"] if p["name"] == "usb2")
        gap = usb2_outer_to_standoff_x(
            b["board_xy"][0], b["hole_inset"], usb2["x"], usb2["wh"][0]
        )
        self.assertAlmostEqual(gap, 4.25, places=2)
        self.assertEqual(b["hole_inset"], 4.0)
        text = (SCAD / "50_board_box.scad").read_text(encoding="utf-8")
        self.assertIn("hole_inset = 4.0", text)

    def test_ffc_slot_is_16_plus_clear(self):
        b = DIMS["board_box"]
        self.assertEqual(b["ffc_w"], 16.0)
        self.assertAlmostEqual(ffc_slot_w(b["ffc_w"], b["ffc_clear"]), 17.2, places=1)


def _scad_module(name: str) -> str:
    """取出 50_board_box.scad 里一个 module 的正文（到下一个 module）。"""
    text = (SCAD / "50_board_box.scad").read_text(encoding="utf-8")
    key = f"module {name}("
    start = text.index(key)
    rest = text[start + len(key) :]
    nxt = rest.find("\nmodule ")
    return text[start : start + len(key) + nxt] if nxt >= 0 else text[start:]


class TestSpeakerAndVents(unittest.TestCase):
    def test_speaker_matches_old_pocket_and_36x18(self):
        s = DIMS["board_box"]["speaker"]
        self.assertEqual(s["body_xyz"], [36.0, 18.0, 9.0])
        self.assertEqual(speaker_pocket(s), (20.5, 39.0))
        self.assertEqual(s["hole_pitch"], 45.0)
        self.assertEqual(s["mount"], "inside")
        self.assertGreaterEqual(s["boss_t"], 5.0)
        self.assertGreaterEqual(s["pocket_depth"], 4.0)
        self.assertEqual(s["slot_span_x"], 20.0)
        self.assertEqual(s["screw_faces"], "inside")
        self.assertEqual(s["boss_wy"], 22.0)

    def test_speaker_cutouts_copy_old_stand(self):
        self.assertEqual(speaker_old_stand_pocket(), (4.1, 20.5, 39.0))
        self.assertEqual(speaker_old_stand_slot(), (20.0, 12.0, 4.0))
        self.assertEqual(speaker_old_stand_slot_z(), (-10.0, 0.0, 10.0))
        self.assertEqual(speaker_old_stand_boss_xy(), (5.0, 22.0))
        inner_half = (DIMS["board_box"]["outer_xyz"][0] - 2 * DIMS["board_box"]["wall"]) / 2
        self.assertAlmostEqual(speaker_screw_x(inner_half, 1.0), 85.5, places=1)
        self.assertAlmostEqual(speaker_pocket_x(inner_half, 1.0), 84.55, places=2)
        cut = _scad_module("speaker_cutouts")
        self.assertIn("cube([4.1, 20.5, 39]", cut)
        self.assertIn("cube([20, 12, 4]", cut)
        self.assertIn("inner_x / 2 - 5", cut)
        self.assertNotIn("outer_x / 2 - wall / 2", cut)
        boss = _scad_module("speaker_inner_boss")
        self.assertIn("cube([5, 22,", boss)

    def test_pcb_standoff_holes_face_opening(self):
        self.assertEqual(pcb_standoff_axis(), "y")
        self.assertEqual(DIMS["board_box"]["standoff_axis"], "y")
        block = _scad_module("pcb_standoffs")
        compact = block.replace(" ", "")
        self.assertIn("rotate([90,0,0])", compact)

    def test_port_side_standoffs_match_old_drawer(self):
        """原抽屉 inset=5-1=4、柱 φ10：柱心距接口内表面 4mm，柱面切入约 1mm。"""
        b = DIMS["board_box"]
        outer_z = b["outer_xyz"][2]
        wall = b["wall"]
        board_z = b["board_xy"][1]
        self.assertEqual(b["standoff_to_port"], 4.0)
        self.assertEqual(b["standoff_d"], 10.0)
        z0 = pcb_z_offset(
            outer_z, wall, board_z, b["hole_inset"], b["standoff_to_port"]
        )
        self.assertAlmostEqual(z0, 10.0, places=1)
        self.assertAlmostEqual(b["pcb_z"], z0, places=1)
        z_lo, z_hi = pcb_standoff_z(z0, board_z, b["hole_inset"])
        inner_top = outer_z / 2.0 - wall
        self.assertAlmostEqual(inner_top - z_hi, b["standoff_to_port"], places=1)
        overlap = b["standoff_d"] / 2.0 - b["standoff_to_port"]
        self.assertAlmostEqual(overlap, 1.0, places=1)
        self.assertGreater(overlap, 0.0)
        self.assertAlmostEqual(z_lo, z0 - (board_z / 2.0 - b["hole_inset"]), places=1)
        text = (SCAD / "50_board_box.scad").read_text(encoding="utf-8")
        self.assertIn("pcb_z = 10.0", text)
        self.assertIn("standoff_d = 10.0", text)
        block = _scad_module("pcb_standoffs")
        self.assertIn("z + pcb_z", block)
        self.assertIn("cylinder(d = standoff_d", block)

    def test_port_y_from_back_inner_matches_old_drawer_flange(self):
        """顶面孔从后壁内侧起算（原法兰 z=0），不要再加支柱高。"""
        b = DIMS["board_box"]
        y0 = y_port_datum(b["outer_xyz"][1], b["wall"])
        self.assertAlmostEqual(y0, -25.0 + 2.5, places=1)
        y_fn = (SCAD / "50_board_box.scad").read_text(encoding="utf-8")
        self.assertIn("function y_pcb() = -outer_y / 2 + wall;", y_fn)
        self.assertNotIn("wall + standoff_h", y_fn.split("function y_pcb()")[1][:80])

    def test_standoff_h_matches_old_tray_deck_plus_boss(self):
        """原抽屉法兰底 z=0 是 3mm 底板底面；柱在板顶上 h=5，焊盘距开孔基准 8mm。

        开孔已按法兰底抄（USB3 心 23.8）。柱只有 6mm 时孔位对、板悬空。
        """
        b = DIMS["board_box"]
        self.assertEqual(b["standoff_h"], 8.0)
        usb3 = next(p for p in b["ports"] if p["name"] == "usb3")
        usb2 = next(p for p in b["ports"] if p["name"] == "usb2")
        usb3_bottom = usb3["y_from_pcb"] - usb3["wh"][1] / 2.0
        usb2_bottom = usb2["y_from_pcb"] - usb2["wh"][1] / 2.0
        self.assertAlmostEqual(usb3_bottom - b["standoff_h"], -0.2, places=1)
        self.assertAlmostEqual(usb2_bottom - b["standoff_h"], 1.05, places=2)
        text = (SCAD / "50_board_box.scad").read_text(encoding="utf-8")
        self.assertIn("standoff_h = 8.0", text)

    def test_vent_width_for_0_6_nozzle(self):
        self.assertEqual(DIMS["board_box"]["vent_w"], 2.4)

    def test_port_fit_coupon_keeps_two_near_port_standoffs(self):
        """试打件：顶墙接口面 + 后壁，只留靠近接口的两颗螺丝孔。"""
        b = DIMS["board_box"]
        z0 = b["pcb_z"]
        z_lo, z_hi = pcb_standoff_z(z0, b["board_xy"][1], b["hole_inset"])
        zmin, zmax = port_fit_clip_z(
            z0, b["board_xy"][1], b["hole_inset"], b["outer_xyz"][2]
        )
        self.assertLess(zmin, z_hi)
        self.assertGreater(zmin, z_lo)
        self.assertGreater(zmax, b["outer_xyz"][2] / 2)
        text = (SCAD / "50_board_box.scad").read_text(encoding="utf-8")
        self.assertIn('part="shell"|"lid"|"fit"', text)
        fit = _scad_module("board_box_fit")
        self.assertIn("board_box_shell()", fit)
        self.assertIn("pcb_z + board_z / 2 - hole_inset", fit)
        self.assertIn('part == "fit"', text)


class TestLidBoltNutAndSelfTap(unittest.TestCase):
    def test_lid_corners_are_bolt_and_captured_nut(self):
        b = DIMS["board_box"]
        self.assertEqual(b["lid_fastener"], "bolt_nut")
        self.assertEqual(b["m3_through"], 3.2)
        self.assertEqual(b["m3_nut_af"], m3_nut_af())
        self.assertEqual(b["m3_nut_h"], m3_nut_h())
        self.assertEqual(b["lid_boss_xz"], 12.0)
        self.assertEqual(b["lid_boss_y"], 8.0)
        self.assertEqual(lid_nut_boss_xz_y(), (12.0, 8.0))
        shell = _scad_module("board_box_shell")
        self.assertIn("corner_nut_bosses()", shell)
        bosses = _scad_module("corner_nut_bosses")
        self.assertIn("cube([", bosses)
        cut = _scad_module("corner_bolt_cutouts")
        self.assertIn("m3_through", cut)
        self.assertIn("$fn = 6", cut)
        self.assertNotIn("m3_insert_d", cut)

    def test_clamp_plate_and_pcb_are_self_tap(self):
        self.assertEqual(DIMS["board_box"]["standoff_tap"], m3_self_tap_d())
        self.assertGreaterEqual(DIMS["board_box"]["standoff_h"], 8.0)
        lid = _scad_module("clamp_holes_in_lid")
        self.assertIn("m3_through", lid)
        clamp = (SCAD / "51_arm_clamp.scad").read_text(encoding="utf-8")
        plate = clamp[clamp.index("h = plate_pitch / 2") : clamp.index("for (side")]
        self.assertIn("m3_tap_d", plate)
        self.assertNotIn("m3_insert_d", plate)
        self.assertNotIn("m3_through", plate)


class TestClamp(unittest.TestCase):
    def test_caliper_inner_width_not_arm_model_62(self):
        c = DIMS["arm_clamp"]
        self.assertEqual(c["arm_w_caliper"], 57.5)
        self.assertEqual(c["print_clear"], 0.5)
        cavity = clamp_cavity_w(c["arm_w_caliper"], c["print_clear"])
        self.assertAlmostEqual(cavity, 58.5, places=1)
        self.assertEqual(c["inner_w"], 58.5)
        text = (SCAD / "51_arm_clamp.scad").read_text(encoding="utf-8")
        self.assertIn("print_clear = 0.5", text)
        self.assertEqual(c["h"], 45.0)
        self.assertEqual(c["plate_pitch"], 40.0)
        self.assertEqual(c["m4_tap_d"], 3.6)
        self.assertEqual(c["set_screws"], 2)
        self.assertEqual(c["profile"], "rect_fillet")
        self.assertEqual(c["set_screw_faces"], "sides")
        self.assertEqual(c["r_rear"], 3.0)
        holes = mount_hole_xy(c["plate_pitch"])
        self.assertEqual(len(holes), 4)
        self.assertIn((-20.0, -20.0), holes)
        self.assertEqual(DIMS["arm"]["width_column"], 57.5)

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
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("//"):
                    continue
                self.assertNotIn("openscad_V1", stripped, msg=f"{name}:{i}")
                self.assertNotIn("openscad/openscad_V1", stripped, msg=f"{name}:{i}")


if __name__ == "__main__":
    unittest.main()
