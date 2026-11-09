"""ทดสอบเดโมหุ่นยนต์ fields/robotics/heart-to-mechanism/simulate.py

ตรวจพฤติกรรมที่บทเรียนอ้างถึง: ด่านความปลอดภัยปฏิเสธคำสั่งที่ไม่ปลอดภัย, ตัวควบคุมที่จูนแล้วนิ่งตามเป้า,
ตัวควบคุมที่จูนผิดแกว่ง, มอเตอร์ไม่ให้แรงเกินขีดจำกัด, และ anti-windup ลดการเกินเป้าเมื่อมอเตอร์อิ่มตัว
"""
import contextlib
import importlib.util
import io
import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "fields" / "robotics" / "heart-to-mechanism" / "simulate.py"

spec = importlib.util.spec_from_file_location("robotics_simulate", DEMO)
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


class DecideTest(unittest.TestCase):
    def test_thai_and_english_commands(self):
        self.assertEqual(sim.decide("ไปที่ 1.5 เมตร"), {"action": "move_to", "target_m": 1.5})
        self.assertEqual(sim.decide("move to -0.5"), {"action": "move_to", "target_m": -0.5})
        self.assertEqual(sim.decide("GO TO 2"), {"action": "move_to", "target_m": 2.0})

    def test_relative_commands_use_the_start_position(self):
        self.assertEqual(sim.decide("เดินหน้า 2 เมตร", start_m=0.5)["target_m"], 2.5)
        self.assertEqual(sim.decide("ถอยหลัง 1 เมตร", start_m=0.5)["target_m"], -0.5)
        self.assertEqual(sim.decide("ถอยหลัง -1", start_m=0.0)["target_m"], -1.0)   # เครื่องหมายลบไม่ทำให้กลับทิศ

    def test_stop_wins_over_everything(self):
        self.assertEqual(sim.decide("หยุดเดี๋ยวนี้ ไปที่ 3 เมตร"), {"action": "stop"})
        self.assertEqual(sim.decide("please STOP"), {"action": "stop"})

    def test_does_not_guess(self):
        for text in ("", "สวัสดี", "ไปที่ เมตร", "move somewhere"):
            with self.subTest(text=text), self.assertRaises(sim.CommandError):
                sim.decide(text)


class GateTest(unittest.TestCase):
    def test_accepts_valid_commands_including_the_boundary(self):
        self.assertEqual(sim.gate({"action": "move_to", "target_m": 2.0}), {"action": "move_to", "target_m": 2.0})
        self.assertEqual(sim.gate({"action": "move_to", "target_m": -2}), {"action": "move_to", "target_m": -2.0})
        self.assertEqual(sim.gate({"action": "stop"}), {"action": "stop"})

    def test_rejects_unsafe_or_malformed_commands(self):
        bad = [
            {"action": "move_to", "target_m": 2.01},
            {"action": "move_to", "target_m": -9},
            {"action": "move_to", "target_m": float("nan")},
            {"action": "move_to", "target_m": float("inf")},
            {"action": "move_to", "target_m": "1.0"},
            {"action": "move_to", "target_m": True},
            {"action": "move_to"},
            {"action": "self_destruct"},
            {"action": "move_to", "target_m": 1.0, "speed": 99},
            {"target_m": 1.0},
            "move_to 1",
            None,
        ]
        for command in bad:
            with self.subTest(command=command), self.assertRaises(sim.CommandError):
                sim.gate(command)

    def test_limits_are_configurable_and_never_clamp_silently(self):
        self.assertEqual(sim.gate({"action": "move_to", "target_m": 3.0}, sim.Limits(workspace_m=3.0))["target_m"], 3.0)
        with self.assertRaises(sim.CommandError):
            sim.gate({"action": "move_to", "target_m": 3.0}, sim.Limits(workspace_m=2.0))


class SimulationTest(unittest.TestCase):
    def test_tuned_controller_reaches_the_target_quickly_and_calmly(self):
        m = sim.simulate(1.0).metrics
        self.assertLess(m["final_error_m"], 0.02)
        self.assertLess(m["overshoot_pct"], 5.0)
        self.assertIsNotNone(m["settling_time_s"])
        self.assertLess(m["settling_time_s"], 2.0)

    def test_negative_and_zero_steps(self):
        self.assertLess(sim.simulate(-1.0).metrics["final_error_m"], 0.02)
        zero = sim.simulate(0.0)
        self.assertEqual(zero.metrics["overshoot_pct"], 0.0)
        self.assertLess(zero.metrics["final_error_m"], 1e-6)

    def test_motor_never_exceeds_its_force_limit(self):
        for max_force in (3.0, 8.0, 20.0):
            result = sim.simulate(2.0, replace(sim.Params(), max_force=max_force))
            self.assertLessEqual(max(abs(f) for f in result.force), max_force + 1e-9, max_force)

    def test_too_gentle_is_slow_and_too_aggressive_rings(self):
        gentle = sim.simulate(1.0, replace(sim.Params(), kp=6.0, ki=0.0, kd=12.0)).metrics
        self.assertGreater(gentle["rise_time_s"], 3.0)
        self.assertIsNone(gentle["settling_time_s"])
        ringing = sim.simulate(1.0, replace(sim.Params(), kp=200.0, ki=0.0, kd=1.0)).metrics
        self.assertGreater(ringing["overshoot_pct"], 50.0)
        self.assertIsNone(ringing["settling_time_s"])

    def test_anti_windup_reduces_overshoot_when_the_motor_saturates(self):
        base = replace(sim.Params(), ki=60.0, max_force=8.0)
        without = sim.simulate(1.0, replace(base, anti_windup=False)).metrics["overshoot_pct"]
        with_aw = sim.simulate(1.0, replace(base, anti_windup=True)).metrics["overshoot_pct"]
        self.assertGreater(without, with_aw + 10.0)

    def test_deterministic(self):
        a, b = sim.simulate(1.0), sim.simulate(1.0)
        self.assertEqual(a.pos, b.pos)
        self.assertEqual(a.metrics, b.metrics)

    def test_physics_is_finite_for_extreme_inputs(self):
        result = sim.simulate(2.0, replace(sim.Params(), kp=1e4, kd=0.0, ki=0.0, duration=1.0))
        self.assertTrue(all(math.isfinite(x) for x in result.pos))


class OutputTest(unittest.TestCase):
    def test_svg_is_valid_xml_with_one_line_per_run_and_escaped_labels(self):
        runs = [("a < b & c", sim.simulate(1.0)), ("ปกติ", sim.simulate(1.0, replace(sim.Params(), kp=20.0)))]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.svg"
            sim.write_svg(str(path), runs, 1.0)
            tree = ET.parse(path)
        ns = "{http://www.w3.org/2000/svg}"
        self.assertEqual(len(tree.getroot().findall(f"{ns}polyline")), 2)
        self.assertIn("a < b & c", "".join(t.text or "" for t in tree.getroot().iter(f"{ns}text")))

    def test_committed_comparison_svg_is_valid(self):
        path = DEMO.parent / "compare.svg"
        self.assertTrue(path.exists(), "ต้องมี compare.svg ที่สร้างจาก simulate.py --compare")
        ns = "{http://www.w3.org/2000/svg}"
        self.assertEqual(len(ET.parse(path).getroot().findall(f"{ns}polyline")), len(sim.SCENARIOS))


class CommandLineTest(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sim.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_normal_run_shows_every_stage_of_the_pipeline(self):
        code, out, _ = self.run_main(["ไปที่ 1 เมตร"])
        self.assertEqual(code, 0)
        for stage in ("[หัวใจ]", "[ด่านความปลอดภัย]", "[ตัวควบคุม]", "[ตัวขับเคลื่อน]", "[กลไก]"):
            self.assertIn(stage, out)

    def test_unsafe_command_is_refused_before_any_physics_runs(self):
        code, out, err = self.run_main(["ไปที่ 5 เมตร"])
        self.assertEqual(code, 2)
        self.assertIn("ปฏิเสธ", err)
        self.assertNotIn("[ตัวควบคุม]", out)

    def test_unknown_command_and_stop(self):
        self.assertEqual(self.run_main(["สวัสดี"])[0], 2)
        code, out, _ = self.run_main(["หยุด"])
        self.assertEqual(code, 0)
        self.assertIn("แรง = 0", out)

    def test_compare_writes_a_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.svg"
            code, out, _ = self.run_main(["--compare", "--svg", str(path)])
            self.assertEqual(code, 0)
            self.assertTrue(path.exists())
        self.assertEqual(out.count("เกินเป้าสูงสุด"), len(sim.SCENARIOS))

    def test_workspace_flag_changes_the_gate(self):
        self.assertEqual(self.run_main(["ไปที่ 3 เมตร", "--workspace", "3"])[0], 0)


if __name__ == "__main__":
    unittest.main()
