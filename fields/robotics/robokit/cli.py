"""คำสั่งของ robokit (ใช้ผ่าน python hope.py robot ... หรือ cd fields/robotics && python -m robokit ...)

exit code: 0 = ผ่าน, 1 = ใช้คำสั่งหรือไฟล์ผิด, 2 = มีคำสั่งถูกปฏิเสธ / ไม่ผ่านเกณฑ์
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import gate as gate_mod
from . import plan as plan_mod
from . import stopping
from .plan import PROFILES_DIR


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _read_lines(source: str):
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip() and not line.lstrip().startswith("#"):
            yield number, line.strip()


def _parse_state(raw: str | None) -> dict:
    if not raw:
        return {}
    path = Path(raw)
    data = json.loads(path.read_text(encoding="utf-8") if path.is_file() else raw)
    if not isinstance(data, dict):
        raise ValueError("--state ต้องเป็น JSON object เช่น '{\"x\": 0, \"y\": 0.3}'")
    return data


def cmd_gate(args) -> int:
    if args.gate_cmd == "examples":
        for path in sorted(PROFILES_DIR.glob("*.json")):
            name = json.loads(path.read_text(encoding="utf-8")).get("name", "")
            print(f"{path.stem:<16} {name}")
        return 0
    if args.gate_cmd == "init":
        source = PROFILES_DIR / f"{args.example}.json"
        if not source.exists():
            print(f"ไม่มีตัวอย่าง {args.example!r} ดูรายชื่อด้วย: robot gate examples", file=sys.stderr)
            return 1
        target = Path(args.path)
        if target.exists() and not args.force:
            print(f"มีไฟล์ {target} อยู่แล้ว ไม่เขียนทับ (ใส่ --force ถ้าต้องการ)", file=sys.stderr)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        print(f"สร้าง {target} จากตัวอย่าง {args.example} แล้ว แก้ตัวเลขให้ตรงกับเครื่องจริง แล้วรัน: robot gate validate {target}")
        return 0
    try:
        profile = gate_mod.load_profile(args.profile)
    except gate_mod.ProfileError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.gate_cmd == "validate":
        actions = profile["actions"]
        print(f"ไฟล์กฎใช้ได้: {profile.get('name', args.profile)}")
        print(f"  action ที่อนุญาต: {', '.join(actions)}")
        print(f"  เขตห้ามเข้า: {len(profile.get('keep_out', []))} เขต · ผ่านเสมอ: {profile.get('always_allow', [])}"
              f" · จำกัด {profile.get('rate_limit_per_s', 'ไม่จำกัด')} ครั้ง/วินาที")
        return 0
    try:
        state = _parse_state(args.state)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"--state ใช้ไม่ได้: {exc}", file=sys.stderr)
        return 1
    g = gate_mod.Gate(profile, log_path=args.log)
    passed = refused = 0
    try:
        lines = list(_read_lines(args.commands))
    except FileNotFoundError:
        print(f"ไม่พบไฟล์คำสั่ง {args.commands}", file=sys.stderr)
        return 1
    for number, line in lines:
        decision = g.check(line, state)
        if decision:
            passed += 1
            print(f"ผ่าน    บรรทัด {number}: {json.dumps(decision.command, ensure_ascii=False)}")
        else:
            refused += 1
            print(f"ปฏิเสธ  บรรทัด {number}: {line[:80]}")
            for reason in decision.reasons:
                print(f"         - {reason}")
    print(f"\nสรุป: ผ่าน {passed} · ปฏิเสธ {refused}" + (f" · บันทึกไว้ที่ {args.log}" if args.log else ""))
    return 2 if refused else 0


def cmd_stop(args) -> int:
    try:
        report = stopping.check(args.speed, args.react, args.decel, args.available, args.safety_factor)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(stopping.describe(report, args.unit))
    return 0 if report.ok else 2


def cmd_tune(args) -> int:
    from . import tune as tune_mod             # โหลดแบบจำลองเฉพาะตอนใช้
    plant = tune_mod.Plant(args.mass, args.friction, args.max_force, args.motor_lag, args.step, args.travel)
    try:
        print("กำลังจำลองราว 100 ชุดค่า x ทุกกรณี (ไม่กี่วินาที)...", file=sys.stderr)
        result = tune_mod.tune(plant, args.max_overshoot, args.uncertainty)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": result.ok, "kp": result.kp, "ki": result.ki, "kd": result.kd, "wn": result.wn,
                          "zeta": result.zeta, "worst_overshoot_pct": result.worst_overshoot_pct,
                          "worst_settling_s": result.worst_settling_s,
                          "cases": [{"case": c, **m} for c, m in result.cases]}, ensure_ascii=False, indent=2))
    else:
        print(tune_mod.describe(result, plant, args.max_overshoot))
    if args.svg:
        tune_mod.write_chart(args.svg, plant, result, args.uncertainty)
        print(f"เขียนกราฟแล้ว: {args.svg}", file=sys.stderr)
    return 0 if result.ok else 2


def _ask_choice(question: str, options: dict) -> str:
    keys = list(options)
    print(f"\n{question}")
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {options[key]}")
    while True:
        raw = input("เลือกเลข: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        print(f"พิมพ์เลข 1 ถึง {len(keys)}")


def cmd_plan(args) -> int:
    answers = {k: getattr(args, k) for k in plan_mod.QUESTIONS}
    missing = [k for k, v in answers.items() if v is None]
    if missing:
        if not sys.stdin.isatty():
            print(f"ต้องใส่ {', '.join('--' + k for k in missing)} (หรือรันในหน้าต่างคำสั่งเพื่อตอบทีละข้อ)",
                  file=sys.stderr)
            return 1
        try:
            for key in missing:
                question, options = plan_mod.QUESTIONS[key]
                answers[key] = _ask_choice(question, options)
        except (EOFError, KeyboardInterrupt):
            print("\nยกเลิก")
            return 1
    written = plan_mod.write_plan(answers, args.out, args.name)
    for path in written:
        print(f"เขียนแล้ว: {path}")
    print("ขั้นต่อไป: เปิด plan.md แล้วเริ่มที่ขั้น 0 (แก้ safety-profile.json ให้ตรงกับเครื่องจริง)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="robot", description="robokit: เครื่องมือหุ่นยนต์ที่ใช้กับเครื่องของคุณ (Python มาตรฐานล้วน)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("plan", help="วางแผนโปรเจกต์ ได้ plan.md + ไฟล์กฎตั้งต้น")
    for key, (question, options) in plan_mod.QUESTIONS.items():
        pl.add_argument(f"--{key}", choices=list(options), help=question)
    pl.add_argument("--out", default="my-robot", help="โฟลเดอร์ที่จะเขียน (ค่าเริ่มต้น my-robot)")
    pl.add_argument("--name", default="หุ่นยนต์ของฉัน")
    pl.set_defaults(func=cmd_plan)

    g = sub.add_parser("gate", help="ด่านตรวจคำสั่งจากไฟล์กฎ")
    gsub = g.add_subparsers(dest="gate_cmd", required=True)
    gsub.add_parser("examples", help="รายชื่อไฟล์กฎตัวอย่าง")
    gi = gsub.add_parser("init", help="สร้างไฟล์กฎจากตัวอย่าง")
    gi.add_argument("path")
    gi.add_argument("--example", default="desk-arm-2axis")
    gi.add_argument("--force", action="store_true")
    gv = gsub.add_parser("validate", help="ตรวจไฟล์กฎ")
    gv.add_argument("profile")
    gc = gsub.add_parser("check", help="ตรวจคำสั่ง JSON ทีละบรรทัด")
    gc.add_argument("profile")
    gc.add_argument("commands", nargs="?", default="-", help="ไฟล์ .jsonl (ค่าเริ่มต้น - = อ่านจาก stdin)")
    gc.add_argument("--state", help='ค่าปัจจุบัน เช่น \'{"x": 0, "y": 0.3}\' หรือไฟล์ JSON')
    gc.add_argument("--log", help="บันทึก audit log (JSONL)")
    g.set_defaults(func=cmd_gate)

    s = sub.add_parser("stop", help="ระยะหยุดของชั้นป้องกัน หยุดทันไหม")
    s.add_argument("--speed", type=float, required=True, help="ความเร็วสูงสุดตอนตรวจพบ (m/s)")
    s.add_argument("--react", type=float, required=True, help="เวลาตอบสนองรวม: อ่านเซนเซอร์ + ตัดสินใจ + รีเลย์/เบรกเริ่มทำงาน (วินาที)")
    s.add_argument("--decel", type=float, required=True, help="อัตราหน่วงตอนเบรก (m/s²) วัดจากการหยุดจริง")
    s.add_argument("--available", type=float, required=True, help="ระยะจากจุดตรวจพบถึงจุดที่ชนแล้วเสียหาย (m)")
    s.add_argument("--safety-factor", type=float, default=1.5, help="ตัวคูณเผื่อ (ค่าเริ่มต้น 1.5)")
    s.add_argument("--unit", default="m", help="หน่วยระยะที่แสดง เช่น m หรือ rad")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_stop)

    t = sub.add_parser("tune", help="หาค่า PID เริ่มต้นจากค่าของเครื่อง และทดสอบความทนต่อค่าที่คลาด")
    t.add_argument("--mass", type=float, required=True, help="มวล kg (แกนหมุน: โมเมนต์ความเฉื่อย kg·m²)")
    t.add_argument("--friction", type=float, required=True, help="แรงเสียดทานเชิงเส้น N·s/m (แกนหมุน: N·m·s/rad)")
    t.add_argument("--max-force", type=float, required=True, help="แรงสูงสุดของมอเตอร์ N (แกนหมุน: N·m)")
    t.add_argument("--motor-lag", type=float, default=0.02, help="ความหน่วงของมอเตอร์ วินาที (ค่าเริ่มต้น 0.02)")
    t.add_argument("--step", type=float, default=0.1, help="ระยะเคลื่อนที่ทั่วไป")
    t.add_argument("--travel", type=float, help="ระยะไกลสุดที่สั่งได้ (ทดสอบตอนมอเตอร์อิ่มตัว)")
    t.add_argument("--max-overshoot", type=float, default=5.0, help="เกินเป้าได้ไม่เกินกี่ %% (ค่าเริ่มต้น 5)")
    t.add_argument("--uncertainty", type=float, default=0.3, help="ค่าที่วัดอาจคลาดเท่าไร (0.3 = ±30%%)")
    t.add_argument("--svg", help="เขียนกราฟทุกกรณีเป็น SVG")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_tune)
    return p


def main(argv=None) -> int:
    _utf8()
    args = build_parser().parse_args(argv)
    return args.func(args)
