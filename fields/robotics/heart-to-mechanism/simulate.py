#!/usr/bin/env python3
"""simulate.py — จาก "หัวใจ" (คำสั่ง) สู่ "กลไก" (แรง ความเร็ว ตำแหน่ง) ของหุ่นยนต์ 1 แกน

ใช้ไลบรารีมาตรฐานของ Python อย่างเดียว ไม่ต้องมีฮาร์ดแวร์ ไม่ต้องมี ROS ไม่ต้องมี API key

สายส่งที่จำลอง (ตรงกับบทเรียน ../01-heart-to-mechanism.md):
    หัวใจ (decide)  ->  ด่านความปลอดภัย (gate)  ->  ตัวควบคุม (PID)  ->  ตัวขับเคลื่อน (มอเตอร์)  ->  กลไก (มวลบนราง)

ส่วน "หัวใจ" ในไฟล์นี้เป็นตัวอ่านคำสั่งแบบกฎง่ายๆ แทน AI เพื่อให้ผลซ้ำได้ทุกครั้ง
ในงานจริงส่วนนี้คือ LLM หรือโมเดลอื่นที่คืน JSON รูปแบบเดียวกัน ส่วนที่เหลือของสายส่งไม่เปลี่ยน

ข้อจำกัด: เป็นแบบจำลองของเล่น (มวลเดียว แรงเสียดทานเชิงเส้น มอเตอร์หน่วงลำดับหนึ่ง) ไม่ใช่หุ่นยนต์จริง
หุ่นยนต์จริงต้องวัดพารามิเตอร์จากตัวเครื่อง (system identification) และมีมาตรการความปลอดภัยของฮาร์ดแวร์

ตัวอย่าง:
    python simulate.py "ไปที่ 1 เมตร"
    python simulate.py "move to 1.5" --kp 80 --kd 4
    python simulate.py --compare --svg compare.svg
"""
import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, replace
from xml.sax.saxutils import escape

# ---------- หัวใจ: คำสั่งภาษาคน -> JSON ----------

ALLOWED_ACTIONS = {"move_to", "stop"}
_NUMBER = r"(-?\d+(?:\.\d+)?)"
_PATTERNS = [
    (re.compile(r"(?:ไปที่|ไปยัง|move to|go to)\s*" + _NUMBER, re.I), "absolute"),
    (re.compile(r"(?:เดินหน้า|ไปข้างหน้า|forward)\s*" + _NUMBER, re.I), "forward"),
    (re.compile(r"(?:ถอยหลัง|ถอย|back(?:ward)?)\s*" + _NUMBER, re.I), "backward"),
]
_STOP = re.compile(r"หยุด|\bstop\b", re.I)


class CommandError(ValueError):
    """คำสั่งที่ไม่เข้าใจ หรือที่ด่านความปลอดภัยไม่ยอมให้ผ่าน"""


def decide(text: str, start_m: float = 0.0) -> dict:
    """แปลงคำสั่งเป็น JSON {"action", "target_m"} ด้วยกฎง่ายๆ (ตัวแทนของ AI)

    คำสั่งแบบสัมพัทธ์ (เดินหน้า/ถอยหลัง) นับจากตำแหน่งเริ่มต้น ถ้าไม่เข้าใจจะ raise CommandError
    ไม่เดาแทนผู้ใช้ เพราะการเดาผิดในโลกกายภาพมีราคาสูงกว่าการถามซ้ำ
    """
    if _STOP.search(text):
        return {"action": "stop"}
    for pattern, kind in _PATTERNS:
        match = pattern.search(text)
        if match:
            value = float(match.group(1))
            target = {"absolute": value, "forward": start_m + value, "backward": start_m - abs(value)}[kind]
            return {"action": "move_to", "target_m": target}
    raise CommandError(f"ไม่เข้าใจคำสั่ง: {text!r} (ลอง: 'ไปที่ 1.5 เมตร', 'เดินหน้า 2 เมตร', 'ถอยหลัง 1 เมตร', 'หยุด')")


# ---------- ด่านความปลอดภัย: ไม่ว่าหัวใจจะตอบอะไรมา ต้องผ่านตรงนี้ ----------

@dataclass(frozen=True)
class Limits:
    workspace_m: float = 2.0          # ราวเดินได้ ±2 เมตรจากจุดศูนย์


def gate(command: dict, limits: Limits = Limits()) -> dict:
    """ตรวจคำสั่งที่ AI ส่งมาก่อนถึงกลไก คืนคำสั่งที่ผ่านแล้ว หรือ raise CommandError

    หลักการ: ปฏิเสธ ไม่ใช่ปรับค่าให้เงียบๆ (การ clamp เงียบๆ ทำให้ผู้ใช้คิดว่าหุ่นยนต์ทำตามที่สั่ง)
    ตรวจเป็นกฎตายตัวที่ไม่พึ่งความมั่นใจของโมเดล เพราะค่าความมั่นใจที่โมเดลรายงานเองไม่ใช่ตัวกันความปลอดภัย
    """
    if not isinstance(command, dict):
        raise CommandError("คำสั่งต้องเป็น JSON object")
    action = command.get("action")
    if action not in ALLOWED_ACTIONS:
        raise CommandError(f"ไม่อนุญาต action {action!r} (อนุญาตเฉพาะ {sorted(ALLOWED_ACTIONS)})")
    extra = set(command) - {"action", "target_m"}
    if extra:
        raise CommandError(f"พบฟิลด์ที่ไม่รู้จัก {sorted(extra)} จึงปฏิเสธทั้งคำสั่ง")
    if action == "stop":
        return {"action": "stop"}
    target = command.get("target_m")
    if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target):
        raise CommandError("target_m ต้องเป็นตัวเลขที่จำกัดค่า (ไม่ใช่ NaN หรือ infinity)")
    if abs(target) > limits.workspace_m:
        raise CommandError(f"เป้าหมาย {target} m อยู่นอกพื้นที่ที่อนุญาต ±{limits.workspace_m} m")
    return {"action": "move_to", "target_m": float(target)}


# ---------- ตัวควบคุม + ตัวขับเคลื่อน + กลไก ----------

@dataclass(frozen=True)
class Params:
    kp: float = 40.0
    ki: float = 2.0
    kd: float = 12.0
    max_force: float = 20.0           # แรงสูงสุดที่มอเตอร์ให้ได้ (นิวตัน)
    anti_windup: bool = True          # หยุดสะสมอินทิกรัลเมื่อมอเตอร์อิ่มตัว
    mass: float = 1.0                 # กิโลกรัม
    friction: float = 0.8             # นิวตัน-วินาทีต่อเมตร
    motor_lag: float = 0.02           # วินาที (มอเตอร์ไม่ให้แรงทันที)
    dt: float = 0.001
    duration: float = 6.0


@dataclass
class Result:
    t: list
    pos: list
    force: list
    target: float
    metrics: dict


def simulate(target_m: float, p: Params = Params(), start_m: float = 0.0) -> Result:
    """จำลองการเคลื่อนที่ไปยังเป้าหมาย คืนเส้นเวลาและตัวชี้วัดคุณภาพการควบคุม"""
    x, v, force_actual, integral = start_m, 0.0, 0.0, 0.0
    ts, xs, fs = [], [], []
    steps = int(round(p.duration / p.dt))
    for i in range(steps):
        error = target_m - x
        derivative_term = -p.kd * v                       # อนุพันธ์จากค่าที่วัดได้ ไม่ใช่จาก error (กันแรงกระชากตอนเปลี่ยนเป้า)
        unsaturated = p.kp * error + p.ki * integral + derivative_term
        command = max(-p.max_force, min(p.max_force, unsaturated))
        saturated = command != unsaturated
        if not (p.anti_windup and saturated and (unsaturated - command) * error > 0):
            integral += error * p.dt
        force_actual += (command - force_actual) * (p.dt / p.motor_lag)   # มอเตอร์หน่วงลำดับหนึ่ง
        accel = (force_actual - p.friction * v) / p.mass
        v += accel * p.dt                                  # semi-implicit Euler
        x += v * p.dt
        if i % 5 == 0:
            ts.append(i * p.dt)
            xs.append(x)
            fs.append(force_actual)
    return Result(ts, xs, fs, target_m, _metrics(ts, xs, fs, target_m, start_m, p))


def _metrics(ts, xs, fs, target, start, p: Params) -> dict:
    step = target - start
    if abs(step) < 1e-9:
        return {"overshoot_pct": 0.0, "rise_time_s": 0.0, "settling_time_s": 0.0,
                "final_error_m": abs(target - xs[-1]), "peak_force_n": max(abs(f) for f in fs)}
    sign = 1.0 if step > 0 else -1.0
    progress = [(x - start) * sign / abs(step) for x in xs]          # 0 = เริ่ม, 1 = ถึงเป้า
    rise = next((t for t, q in zip(ts, progress) if q >= 0.9), None)
    start10 = next((t for t, q in zip(ts, progress) if q >= 0.1), None)
    band = 0.02
    settle = 0.0
    for t, q in zip(ts, progress):
        if abs(q - 1.0) > band:
            settle = t
    settled = settle < ts[-1] - 1e-9 and abs(progress[-1] - 1.0) <= band
    return {
        "overshoot_pct": max(0.0, (max(progress) - 1.0) * 100.0),
        "rise_time_s": None if rise is None or start10 is None else rise - start10,
        "settling_time_s": settle if settled else None,        # None = ยังไม่นิ่งในเวลาที่จำลอง
        "final_error_m": abs(target - xs[-1]),
        "peak_force_n": max(abs(f) for f in fs),
    }


# ---------- แสดงผล ----------

def _fmt(value, unit=""):
    return "ไม่ถึง/ไม่นิ่ง" if value is None else f"{value:.2f}{unit}"


def describe(result: Result) -> str:
    m = result.metrics
    return (f"  เกินเป้าสูงสุด {_fmt(m['overshoot_pct'], ' %')} | เวลาขึ้น (10-90%) {_fmt(m['rise_time_s'], ' s')} | "
            f"นิ่งภายใน ±2% ที่ {_fmt(m['settling_time_s'], ' s')} | คลาดเคลื่อนสุดท้าย {m['final_error_m'] * 1000:.1f} mm | "
            f"แรงสูงสุด {m['peak_force_n']:.1f} N")


SCENARIOS = [
    ("นุ่มเกินไป (kp ต่ำ ตอบช้า)", dict(kp=6.0, ki=0.0, kd=12.0)),
    ("จูนแล้ว (PID)", dict()),
    ("แรงเกินไป (kp สูง ไม่มีตัวหน่วง แกว่ง)", dict(kp=200.0, ki=0.0, kd=1.0)),
    ("อิ่มตัวและสะสมอินทิกรัล (ไม่มี anti-windup)", dict(ki=60.0, max_force=8.0, anti_windup=False)),
    ("อิ่มตัวแต่มี anti-windup", dict(ki=60.0, max_force=8.0, anti_windup=True)),
]
COLORS = ["#8a8a8a", "#d4af37", "#e5534b", "#c678dd", "#56b6c2"]


def write_svg(path: str, runs: list, target: float) -> None:
    """เขียนกราฟตำแหน่งตามเวลาเป็นไฟล์ SVG (ไม่ใช้ไลบรารีภายนอก) เพื่อใช้ทำภาพประกอบ"""
    w, left, right, top = 760, 70, 24, 40
    bottom = 64 + 20 * len(runs)                      # เผื่อที่ให้คำอธิบายสีไว้ใต้กราฟ ไม่ให้ทับเส้น
    h = top + 300 + bottom
    t_max = max(r.t[-1] for _, r in runs)
    lo = min(min(r.pos) for _, r in runs)
    hi = max(max(r.pos) for _, r in runs)
    pad = (hi - lo) * 0.08 or 0.1
    y_lo, y_hi = min(lo, 0.0) - pad, max(hi, target) + pad

    def sx(t):
        return left + (w - left - right) * t / t_max

    def sy(y):
        return top + (h - top - bottom) * (1 - (y - y_lo) / (y_hi - y_lo))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
             'font-family="Leelawadee UI, Tahoma, sans-serif" font-size="13">',
             f'<rect width="{w}" height="{h}" fill="#0a0a0b"/>',
             f'<text x="{left}" y="24" fill="#f5d76e" font-size="16">ตำแหน่งของหุ่นยนต์ตามเวลา (เป้าหมาย {target:g} เมตร)</text>']
    for i in range(6):
        y = y_lo + (y_hi - y_lo) * i / 5
        parts.append(f'<line x1="{left}" x2="{w - right}" y1="{sy(y):.1f}" y2="{sy(y):.1f}" stroke="#222"/>')
        parts.append(f'<text x="{left - 8}" y="{sy(y) + 4:.1f}" fill="#999" text-anchor="end">{y:.2f}</text>')
    for i in range(7):
        t = t_max * i / 6
        parts.append(f'<text x="{sx(t):.1f}" y="{h - bottom + 20}" fill="#999" text-anchor="middle">{t:.1f}</text>')
    axis_bottom = top + 300
    parts.append(f'<text x="{(left + w - right) / 2:.0f}" y="{axis_bottom + 40}" fill="#999" text-anchor="middle">เวลา (วินาที)</text>')
    parts.append(f'<line x1="{left}" x2="{w - right}" y1="{sy(target):.1f}" y2="{sy(target):.1f}" '
                 'stroke="#f5d76e" stroke-dasharray="6 4"/>')
    for index, (label, result) in enumerate(runs):
        points = " ".join(f"{sx(t):.1f},{sy(x):.1f}" for t, x in zip(result.t, result.pos))
        color = COLORS[index % len(COLORS)]
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}"/>')
        legend_y = axis_bottom + 62 + index * 20
        parts.append(f'<rect x="{left}" y="{legend_y - 11}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{left + 20}" y="{legend_y}" fill="#ddd">{escape(label)}</text>')
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")


def run_pipeline(text: str, params: Params, limits: Limits, start_m: float = 0.0) -> Result | None:
    print(f"[หัวใจ]            คำสั่ง: {text!r}")
    command = decide(text, start_m)
    print(f"[หัวใจ -> JSON]    {json.dumps(command, ensure_ascii=False)}")
    command = gate(command, limits)
    print(f"[ด่านความปลอดภัย]  ผ่าน (พื้นที่ ±{limits.workspace_m:g} m)")
    if command["action"] == "stop":
        print("[ตัวควบคุม]        หยุด: แรง = 0 ไม่ต้องจำลอง")
        return None
    print(f"[ตัวควบคุม]        PID kp={params.kp:g} ki={params.ki:g} kd={params.kd:g} "
          f"anti-windup={'เปิด' if params.anti_windup else 'ปิด'}")
    print(f"[ตัวขับเคลื่อน]    แรงสูงสุด {params.max_force:g} N หน่วงมอเตอร์ {params.motor_lag * 1000:g} ms")
    result = simulate(command["target_m"], params, start_m)
    print(f"[กลไก]             มวล {params.mass:g} kg เสียดทาน {params.friction:g} N·s/m")
    print(describe(result))
    return result


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="จำลองสายส่งจากคำสั่งสู่กลไกของหุ่นยนต์ 1 แกน")
    parser.add_argument("text", nargs="*", help='คำสั่ง เช่น "ไปที่ 1.5 เมตร" (ค่าเริ่มต้น: ไปที่ 1 เมตร)')
    parser.add_argument("--compare", action="store_true", help="เทียบ 5 สถานการณ์ของตัวควบคุม")
    parser.add_argument("--svg", help="เขียนกราฟเป็นไฟล์ SVG")
    parser.add_argument("--workspace", type=float, default=Limits.workspace_m, help="พื้นที่ที่อนุญาต ± เมตร")
    for name in ("kp", "ki", "kd", "max_force"):
        parser.add_argument(f"--{name.replace('_', '-')}", type=float, default=getattr(Params, name))
    parser.add_argument("--no-anti-windup", action="store_true")
    args = parser.parse_args(argv)

    params = Params(kp=args.kp, ki=args.ki, kd=args.kd, max_force=args.max_force, anti_windup=not args.no_anti_windup)
    limits = Limits(workspace_m=args.workspace)
    text = " ".join(args.text) or "ไปที่ 1 เมตร"
    try:
        if args.compare:
            command = gate(decide(text), limits)
            if command["action"] == "stop":
                raise CommandError("คำสั่งหยุดไม่มีอะไรให้เทียบ")
            runs = []
            for label, overrides in SCENARIOS:
                result = simulate(command["target_m"], replace(params, **overrides))
                runs.append((label, result))
                print(f"{label}\n{describe(result)}")
        else:
            result = run_pipeline(text, params, limits)
            runs = [("ผลการจำลอง", result)] if result else []
    except CommandError as exc:
        print(f"ปฏิเสธ: {exc}", file=sys.stderr)
        return 2
    if args.svg and runs:
        write_svg(args.svg, runs, runs[0][1].target)
        print(f"เขียนกราฟแล้ว: {args.svg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
