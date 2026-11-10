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


class MechanismGuardTest(unittest.TestCase):
    """ชั้นป้องกันของกลไกต้องกันได้แม้หัวใจ ด่านซอฟต์แวร์ หรือตัวควบคุมผิดพลาด และต้องไม่รบกวนงานปกติ"""

    def run_case(self, target, **overrides):
        return sim.simulate(target, replace(sim.Params(), duration=2.0, **overrides)).metrics

    def test_normal_work_never_trips_the_guard(self):
        for target in (-2.0, -1.0, 0.5, 1.0, 2.0):
            with self.subTest(target=target):
                m = self.run_case(target)
                self.assertFalse(m["guard_tripped"])
                self.assertFalse(m["crashed"])

    def test_the_comparison_scenarios_at_one_metre_are_not_cut_off(self):
        for label, overrides in sim.SCENARIOS:
            with self.subTest(label=label):
                m = sim.simulate(1.0, replace(sim.Params(), **overrides)).metrics
                self.assertFalse(m["guard_tripped"])

    def test_hallucinated_target_with_the_gate_bypassed_crashes_without_the_guard(self):
        m = self.run_case(5.0, guard=False)
        self.assertTrue(m["crashed"])
        self.assertGreater(m["impact_speed_m_s"], 5.0)

    def test_guard_stops_a_hallucinated_target_before_the_end_of_the_rail(self):
        for target in (5.0, -9.0, 50.0):                     # กฎไม่รู้ว่าเป้าคืออะไร จึงกันได้ทุกค่า
            with self.subTest(target=target):
                m = self.run_case(target)
                self.assertTrue(m["guard_tripped"])
                self.assertFalse(m["crashed"])
                self.assertLess(m["peak_position_m"], sim.Params().hard_stop_m)

    def test_watchdog_catches_a_frozen_controller(self):
        crashed = self.run_case(2.0, guard=False, freeze_at_s=0.2)
        self.assertTrue(crashed["crashed"])
        guarded = self.run_case(2.0, freeze_at_s=0.2)
        self.assertFalse(guarded["crashed"])
        self.assertIn("watchdog", guarded["guard_reason"])
        self.assertAlmostEqual(guarded["guard_trip_s"], 0.2 + sim.Params().watchdog_s, delta=0.01)

    def test_guard_cuts_power_and_the_cut_is_latched(self):
        result = sim.simulate(5.0, replace(sim.Params(), duration=2.0))
        self.assertTrue(result.metrics["guard_tripped"])
        self.assertAlmostEqual(result.force[-1], 0.0, places=9)
        self.assertLess(max(abs(x) for x in result.pos), sim.Params().hard_stop_m)

    def test_guard_only_sees_measurements_not_the_target(self):
        # ตัวควบคุมสั่งผิดมากแค่ไหน ชั้นป้องกันตัดสินจากตำแหน่ง ความเร็ว และชีพจรเท่านั้น
        for kp in (40.0, 1e3):
            with self.subTest(kp=kp):
                m = sim.simulate(5.0, replace(sim.Params(), kp=kp, duration=2.0)).metrics
                self.assertFalse(m["crashed"])

    def test_a_badly_tuned_controller_is_also_cut_when_it_leaves_the_safe_range(self):
        m = sim.simulate(2.0, replace(sim.Params(), kp=200.0, ki=0.0, kd=1.0)).metrics
        self.assertTrue(m["guard_tripped"])
        self.assertFalse(m["crashed"])


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

    def test_bypassed_gate_is_caught_by_the_guard_but_not_when_both_are_off(self):
        code, out, _ = self.run_main(["ไปที่ 5 เมตร", "--bypass-gate"])
        self.assertEqual(code, 0)
        self.assertIn("ข้าม", out)
        self.assertIn("ตัดกำลังและเบรก", out)
        code, _, err = self.run_main(["ไปที่ 5 เมตร", "--bypass-gate", "--no-guard"])
        self.assertEqual(code, 3)
        self.assertIn("ชนปลายราง", err)

    def test_frozen_controller_flag(self):
        self.assertEqual(self.run_main(["ไปที่ 2 เมตร", "--freeze-at", "0.2"])[0], 0)
        self.assertEqual(self.run_main(["ไปที่ 2 เมตร", "--freeze-at", "0.2", "--no-guard"])[0], 3)

    def test_faults_mode_writes_a_chart_with_one_line_per_fault(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.svg"
            code, out, _ = self.run_main(["--faults", "--svg", str(path)])
            self.assertEqual(code, 0)
            ns = "{http://www.w3.org/2000/svg}"
            self.assertEqual(len(ET.parse(path).getroot().findall(f"{ns}polyline")), len(sim.FAULTS))
        self.assertEqual(out.count("[ชน]"), 2)
        self.assertEqual(out.count("[ชั้นป้องกัน]"), 2)

    def test_committed_fault_chart_is_valid(self):
        path = DEMO.parent / "compare-faults.svg"
        self.assertTrue(path.exists(), "ต้องมี compare-faults.svg ที่สร้างจาก simulate.py --faults")
        ns = "{http://www.w3.org/2000/svg}"
        self.assertEqual(len(ET.parse(path).getroot().findall(f"{ns}polyline")), len(sim.FAULTS))

    def test_workspace_flag_changes_the_gate(self):
        self.assertEqual(self.run_main(["ไปที่ 3 เมตร", "--workspace", "3"])[0], 0)


if __name__ == "__main__":
    unittest.main()
