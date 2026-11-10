"""ทดสอบ robokit (fields/robotics/robokit) และ ros2_llm_bridge.py ที่ใช้ด่านตรวจของ robokit

ตรวจสิ่งที่เอกสารสัญญาไว้: ด่านปฏิเสธคำสั่งอันตรายทุกแบบและไม่ปรับค่าให้เงียบๆ, ไฟล์กฎที่ผิดถูกปฏิเสธตั้งแต่โหลด,
สูตรระยะหยุดตรงกับการคำนวณมือ, ตัวจูนได้ค่าที่ผ่านสเปกในทุกกรณีที่ทดสอบ และแผนโปรเจกต์ที่สร้างได้ใช้ได้จริง
"""
import contextlib
import copy
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fields" / "robotics"))

from robokit import Gate, ProfileError, load_profile, validate_profile  # noqa: E402
from robokit import cli, plan, stopping, tune  # noqa: E402

PROFILES = ROOT / "fields" / "robotics" / "robokit" / "profiles"
EXAMPLES = ROOT / "fields" / "robotics" / "robokit" / "examples"
ARM = load_profile(PROFILES / "desk-arm-2axis.json")
HERE = {"x": 0.0, "y": 0.3}


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class ProfileTest(unittest.TestCase):
    def test_example_profiles_are_valid(self):
        for path in PROFILES.glob("*.json"):
            with self.subTest(path.name):
                self.assertEqual(validate_profile(json.loads(path.read_text(encoding="utf-8"))), [])

    def test_bad_profiles_are_refused_with_every_problem_listed(self):
        bad = copy.deepcopy(ARM)
        bad["actions"]["move_to"]["params"]["x"] = {"type": "number", "min": 1, "max": -1}
        bad["actions"]["move_to"]["params"]["speed"] = {"type": "number"}
        bad["keep_out"].append({"name": "ผิด", "z": [0, 1]})
        bad["rate_limt_per_s"] = 3
        problems = validate_profile(bad)
        joined = "\n".join(problems)
        self.assertIn("min ต้องไม่เกิน max", joined)
        self.assertIn("ไม่มีขอบเขต = ไม่มีด่าน", joined)
        self.assertIn("keep_out[2].z", joined)
        self.assertIn("rate_limt_per_s", joined)
        with self.assertRaises(ProfileError):
            Gate(bad)

    def test_default_must_obey_its_own_rule(self):
        bad = copy.deepcopy(ARM)
        bad["actions"]["move_to"]["params"]["speed"]["default"] = 9
        self.assertTrue(any("default" in p for p in validate_profile(bad)))

    def test_missing_or_broken_file(self):
        with self.assertRaises(ProfileError):
            load_profile(PROFILES / "nope.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ProfileError):
                load_profile(path)


class GateTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.gate = Gate(ARM, clock=self.clock)

    def refused(self, command, state=HERE):
        decision = self.gate.check(command, state)
        self.assertFalse(decision, decision)
        self.assertIsNone(decision.command)
        return " ".join(decision.reasons)

    def test_good_command_passes_with_defaults_and_floats(self):
        d = self.gate.check({"action": "move_to", "params": {"x": 0, "y": 0.3}, "confidence": 0.9}, HERE)
        self.assertTrue(d)
        self.assertEqual(d.command, {"action": "move_to", "params": {"x": 0.0, "y": 0.3, "speed": 0.1}})
        self.assertIsInstance(d.command["params"]["x"], float)

    def test_refuses_instead_of_clamping(self):
        self.assertIn("นอกช่วง", self.refused({"action": "move_to", "params": {"x": 0.41, "y": 0.3}}))

    def test_refuses_unknown_action_field_and_param(self):
        self.assertIn("ไม่อนุญาต action", self.refused({"action": "self_destruct"}))
        self.assertIn("override_safety", self.refused(
            {"action": "move_to", "params": {"x": 0, "y": 0.3}, "override_safety": True}))
        self.assertIn("'z'", self.refused({"action": "move_to", "params": {"x": 0, "y": 0.3, "z": 1}}))

    def test_refuses_bad_types(self):
        for value in (float("nan"), float("inf"), "0.1", True, None, [0.1]):
            with self.subTest(value=value):
                self.assertIn("ตัวเลขที่จำกัดค่า", self.refused({"action": "move_to", "params": {"x": value, "y": 0.3}}))
        self.assertIn("หนึ่งใน", self.refused({"action": "gripper", "params": {"state": "smash"}}))
        self.assertIn("ไม่ใช่ JSON", self.refused("ขยับแขนไปทางซ้ายหน่อย"))
        self.assertIn("JSON object", self.refused([1, 2]))
        self.assertIn("params ต้องเป็น object", self.refused({"action": "move_to", "params": [0, 0.3]}))

    def test_json_text_is_accepted_and_missing_required_is_refused(self):
        self.assertTrue(self.gate.check('{"action": "wait", "params": {"seconds": 2}}'))
        self.assertIn("ขาด 'y'", self.refused({"action": "move_to", "params": {"x": 0}}))

    def test_keep_out_zone(self):
        self.assertIn("จุดวางแก้วน้ำ", self.refused({"action": "move_to", "params": {"x": 0.3, "y": 0.4}}))
        self.assertTrue(self.gate.check({"action": "move_to", "params": {"x": 0.24, "y": 0.4}}, {"x": 0.1, "y": 0.3}))

    def test_max_step_fails_closed_without_state(self):
        self.assertIn("เกินที่อนุญาตต่อครั้ง", self.refused({"action": "move_to", "params": {"x": 0.35, "y": 0.3}},
                                                           {"x": -0.3, "y": 0.3}))
        self.assertIn("ไม่รู้ค่าปัจจุบัน", self.refused({"action": "move_to", "params": {"x": 0, "y": 0.3}}, {}))

    def test_rate_limit_but_stop_always_passes(self):
        cmd = {"action": "wait", "params": {"seconds": 1}}
        for _ in range(5):
            self.assertTrue(self.gate.check(cmd))
        self.assertIn("ถี่เกิน", self.refused(cmd))
        self.assertTrue(self.gate.check({"action": "stop"}))
        self.clock.now += 1.0
        self.assertTrue(self.gate.check(cmd))

    def test_audit_log_survives_nan_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "logs" / "audit.jsonl"
            gate = Gate(ARM, log_path=log)
            gate.check({"action": "move_to", "params": {"x": float("nan"), "y": 0.3}}, HERE)
            gate.check({"action": "stop"})
            entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["ok"] for e in entries], [False, True])
        self.assertIsInstance(entries[0]["input"], str)


class StoppingTest(unittest.TestCase):
    def test_matches_hand_calculation(self):
        r = stopping.check(speed=0.5, react_s=0.05, decel=5, available=0.1, safety_factor=1.5)
        self.assertAlmostEqual(r.react_distance, 0.025)
        self.assertAlmostEqual(r.brake_distance, 0.025)
        self.assertAlmostEqual(r.required, 0.075)
        self.assertTrue(r.ok)

    def test_max_safe_speed_is_exactly_at_the_limit(self):
        r = stopping.check(speed=1.0, react_s=0.1, decel=4, available=0.2)
        self.assertFalse(r.ok)
        at_limit = stopping.check(r.max_safe_speed, 0.1, 4, 0.2)
        self.assertAlmostEqual(at_limit.required, 0.2, places=9)
        self.assertAlmostEqual(r.needed_decel, 15.0)

    def test_reaction_alone_can_eat_the_budget(self):
        r = stopping.check(speed=3, react_s=0.1, decel=10, available=0.3)
        self.assertIsNone(r.needed_decel)
        self.assertIn("ช่วงตอบสนองอย่างเดียว", stopping.describe(r))

    def test_invalid_input(self):
        for args in ((-1, 0.1, 1, 1), (1, 0.1, 0, 1), (1, 0.1, 1, 1, 0.5)):
            with self.assertRaises(ValueError):
                stopping.check(*args)


class TuneTest(unittest.TestCase):
    def test_tuned_gains_meet_spec_in_every_case(self):
        plant = tune.Plant(mass=1.0, friction=0.8, max_force=20, motor_lag=0.02, step=0.2, travel=1.0)
        result = tune.tune(plant, max_overshoot_pct=5, uncertainty=0.3)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.cases), 6)
        for label, m in result.cases:
            self.assertLessEqual(m["overshoot_pct"], 5, label)
            self.assertIsNotNone(m["settling_time_s"], label)
            self.assertLessEqual(m["peak_force_n"], 20 + 1e-9, label)

    def test_impossible_spec_says_so(self):
        plant = tune.Plant(mass=1.0, friction=0.8, max_force=20, step=0.2)
        result = tune.tune(plant, max_overshoot_pct=-1, uncertainty=0)
        self.assertFalse(result.ok)
        self.assertIn("ไม่มีชุดไหนผ่านสเปก", tune.describe(result, plant, -1))

    def test_invalid_plant(self):
        with self.assertRaises(ValueError):
            tune.tune(tune.Plant(mass=0, friction=1, max_force=10))
        with self.assertRaises(ValueError):
            tune.tune(tune.Plant(mass=1, friction=1, max_force=10), uncertainty=1.5)


class PlanTest(unittest.TestCase):
    def test_every_answer_combination_builds(self):
        import itertools
        keys = list(plan.QUESTIONS)
        for combo in itertools.product(*(plan.QUESTIONS[k][1] for k in keys)):
            text = plan.build_plan(dict(zip(keys, combo)))
            self.assertIn("## ขั้นตอน", text)
            self.assertIn("ไม่ใช่คำแนะนำด้านวิศวกรรมความปลอดภัย", text)

    def test_risky_answers_add_requirements(self):
        text = plan.build_plan({"kind": "mobile", "stage": "hardware", "ai": "llm", "people": "yes", "use": "work"})
        self.assertIn("ทำงานใกล้คน", text)
        self.assertIn("ISO 10218", text)
        self.assertIn("2410.13691", text)
        self.assertIn("ต่อ AI", text)

    def test_write_plan_creates_valid_profile_and_keeps_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = {"kind": "axis", "stage": "idea", "ai": "none", "people": "no", "use": "learn"}
            written = plan.write_plan(answers, tmp)
            self.assertEqual(len(written), 2)
            load_profile(Path(tmp) / "safety-profile.json")
            again = plan.write_plan(answers, tmp)
            self.assertEqual(len(again), 1)                # ไม่เขียนทับไฟล์กฎที่อาจแก้ไว้แล้ว

    def test_bad_answer(self):
        with self.assertRaises(ValueError):
            plan.build_plan({"kind": "drone", "stage": "idea", "ai": "none", "people": "no", "use": "learn"})


class CliTest(unittest.TestCase):
    def test_gate_check_example_exit_codes(self):
        code, out, _ = run_cli("gate", "check", str(PROFILES / "desk-arm-2axis.json"),
                               str(EXAMPLES / "desk-arm-commands.jsonl"), "--state", json.dumps(HERE))
        self.assertEqual(code, 2)
        self.assertIn("สรุป: ผ่าน 4 · ปฏิเสธ 10", out)

    def test_validate_init_and_broken_profile(self):
        self.assertEqual(run_cli("gate", "validate", str(PROFILES / "rail-1axis.json"))[0], 0)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "mine.json"
            self.assertEqual(run_cli("gate", "init", str(target), "--example", "rail-1axis")[0], 0)
            self.assertEqual(run_cli("gate", "init", str(target))[0], 1)       # ไม่เขียนทับ
            target.write_text('{"actions": {"move_to": {"params": {"x": {"type": "number"}}}}}', encoding="utf-8")
            code, _, err = run_cli("gate", "validate", str(target))
            self.assertEqual(code, 1)
            self.assertIn("min และ max", err)

    def test_stop_exit_code_and_json(self):
        code, out, _ = run_cli("stop", "--speed", "1", "--react", "0.1", "--decel", "4", "--available", "0.2", "--json")
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(out)["ok"])

    def test_plan_without_answers_and_without_tty(self):
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch("sys.stdin", io.StringIO("")):
            code, _, err = run_cli("plan", "--out", tmp)
        self.assertEqual(code, 1)
        self.assertIn("--kind", err)

    def test_hope_py_dispatches_robot(self):
        proc = subprocess.run([sys.executable, str(ROOT / "hope.py"), "robot", "stop", "--speed", "0.5",
                               "--react", "0.05", "--decel", "5", "--available", "0.1"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ผ่าน", proc.stdout)


class BridgeTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("ros2_llm_bridge", ROOT / "domains" / "robotics" / "ros2_llm_bridge.py")
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.mod              # dataclass ที่ใช้ postponed annotations ต้องหาโมดูลเจอ
        spec.loader.exec_module(self.mod)

    def test_offline_demo_only_executes_safe_clear_commands(self):
        ticks = iter(range(0, 1000, 2))
        bridge = self.mod.LLMRobotBridge(llm=self.mod.offline_llm, clock=lambda: next(ticks))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            for text in self.mod.OFFLINE_REPLIES:
                bridge.on_instruction(text)
        self.assertEqual([c["action"] for c in bridge.executed], ["move_to", "rotate", "stop"])
        self.assertIn("override_safety", out.getvalue())
        self.assertIn("[clarify]", out.getvalue())

    def test_non_json_reply_is_refused(self):
        bridge = self.mod.LLMRobotBridge(llm=lambda *_: "I will drive forward now!")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(bridge.on_instruction("go"))
        self.assertEqual(bridge.executed, [])

    def test_extract_json(self):
        self.assertEqual(self.mod.extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertIsNone(self.mod.extract_json("no json"))
        self.assertIsNone(self.mod.extract_json("[1, 2]"))


if __name__ == "__main__":
    unittest.main()
