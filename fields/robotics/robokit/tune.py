"""หาค่า PID เริ่มต้นจากค่าของเครื่องคุณ แล้วทดสอบว่าทนต่อค่าที่วัดคลาดได้ไหม

ใช้แบบจำลองเดียวกับเดโมบทที่ 1 (มวล + แรงเสียดทานเชิงเส้น + มอเตอร์หน่วงลำดับหนึ่ง + แรงจำกัด)
แกนหมุนใช้ได้ด้วยการแทนค่า: มวล -> โมเมนต์ความเฉื่อย (kg·m²), แรงเสียดทาน -> ความหน่วง (N·m·s/rad),
แรง -> แรงบิด (N·m), ระยะ -> มุม (rad)

วิธีหา: ไล่ค่าความถี่ธรรมชาติ (wn) และอัตราหน่วง (zeta) ที่ต้องการ แปลงเป็น kp = m·wn², kd = 2·zeta·wn·m - b
แล้วจำลองทุกชุดบน "กรณีเลวร้าย" (มวลและแรงเสียดทานคลาดจากที่วัด ±uncertainty, ระยะสั้นและระยะเต็ม)
เลือกชุดที่นิ่งเร็วที่สุดในกรณีที่แย่ที่สุด โดยไม่มีกรณีไหนเกินเป้าเกินสเปก

ข้อจำกัด: แบบจำลองไม่มีแรงโน้มถ่วง แรงเสียดทานแบบคูลอมบ์ ช่องฟรีของเฟือง หรือสัญญาณรบกวน จึงตั้ง ki = 0
ค่าที่ได้เป็นจุดเริ่มต้นสำหรับจูนบนของจริง ไม่ใช่ค่าสุดท้าย
"""
from __future__ import annotations

import importlib.util
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

_DEMO = Path(__file__).resolve().parents[1] / "heart-to-mechanism" / "simulate.py"


def _load_model():
    """ใช้แบบจำลองจากเดโมบทที่ 1 ตัวเดียวกัน (มีชุดทดสอบ 33 ข้อคุมอยู่) แทนการเขียนซ้ำ"""
    spec = importlib.util.spec_from_file_location("robokit_demo_model", _DEMO)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


model = _load_model()


@dataclass(frozen=True)
class Plant:
    mass: float               # kg (หรือ kg·m² สำหรับแกนหมุน)
    friction: float           # N·s/m (หรือ N·m·s/rad)
    max_force: float          # N (หรือ N·m)
    motor_lag: float = 0.02   # วินาที
    step: float = 0.1         # ระยะเคลื่อนที่ทั่วไป
    travel: float | None = None   # ระยะไกลสุดที่สั่งได้ (ทดสอบตอนมอเตอร์อิ่มตัว) ไม่ใส่ = เท่ากับ step

    def check(self) -> None:
        for name in ("mass", "max_force", "motor_lag", "step"):
            value = getattr(self, name)
            if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
                raise ValueError(f"{name} ต้องเป็นตัวเลขบวก")
        if not (math.isfinite(self.friction) and self.friction >= 0):
            raise ValueError("friction ต้องไม่ติดลบ")
        if self.travel is not None and not (math.isfinite(self.travel) and self.travel > 0):
            raise ValueError("travel ต้องเป็นตัวเลขบวก")


@dataclass
class Tuning:
    ok: bool
    kp: float
    ki: float
    kd: float
    wn: float
    zeta: float
    worst_overshoot_pct: float
    worst_settling_s: float | None
    cases: list               # [(ชื่อกรณี, metrics)]
    tried: int


def _params(plant: Plant, mass: float, friction: float, kp: float, kd: float, duration: float):
    dt = max(1e-5, min(0.001, plant.motor_lag / 10))
    return replace(model.Params(), kp=kp, ki=0.0, kd=kd, max_force=plant.max_force, mass=mass, friction=friction,
                   motor_lag=plant.motor_lag, dt=dt, duration=duration, anti_windup=True,
                   guard=False, hard_stop_m=1e12)           # จูนตัวควบคุมอย่างเดียว ไม่ให้ชั้นป้องกันหรือปลายรางรบกวน


def cases_for(plant: Plant, uncertainty: float) -> list:
    """กรณีที่ใช้ทดสอบ: ค่าที่วัดได้ และค่าที่คลาดไปทางเลวร้าย (หนักและลื่นกว่า = เกินเป้ามากขึ้น)"""
    u = uncertainty
    variants = [("ค่าที่วัดได้", 1.0, 1.0), (f"หนักขึ้น {u:.0%} ลื่นขึ้น {u:.0%}", 1 + u, 1 - u),
                (f"เบาลง {u:.0%} ฝืดขึ้น {u:.0%}", 1 - u, 1 + u)] if u > 0 else [("ค่าที่วัดได้", 1.0, 1.0)]
    distances = [plant.step] + ([plant.travel] if plant.travel and plant.travel != plant.step else [])
    return [(f"{label} · ระยะ {d:g}", plant.mass * mf, plant.friction * ff, d)
            for label, mf, ff in variants for d in distances]


def _duration(plant: Plant, wn: float, zeta: float, distance: float) -> float:
    travel_time = 2 * math.sqrt(2 * distance * plant.mass / plant.max_force)   # เร่งเต็มแรงครึ่งทาง เบรกครึ่งทาง
    return min(120.0, max(1.0, 8 / (zeta * wn) + 3 * travel_time + 20 * plant.motor_lag))


def evaluate(plant: Plant, kp: float, kd: float, cases: list, duration: float) -> list:
    results = []
    for label, mass, friction, distance in cases:
        r = model.simulate(distance, _params(plant, mass, friction, kp, kd, duration))
        results.append((label, r))
    return results


def tune(plant: Plant, max_overshoot_pct: float = 5.0, uncertainty: float = 0.3) -> Tuning:
    plant.check()
    if not 0 <= uncertainty < 1:
        raise ValueError("uncertainty ต้องอยู่ระหว่าง 0 ถึง 1 (เช่น 0.3 = ±30%)")
    cases = cases_for(plant, uncertainty)
    wn_max = 1 / (3 * plant.motor_lag)         # เร็วกว่ามอเตอร์ไม่ได้ ตั้งเพดานไว้ 1/3 ของแบนด์วิดท์มอเตอร์
    wn_min = wn_max / 200
    best, fallback, tried = None, None, 0
    for i in range(16):
        wn = wn_min * (wn_max / wn_min) ** (i / 15)
        for zeta in (0.7, 0.8, 0.9, 1.0, 1.2, 1.5):
            kp = plant.mass * wn * wn
            kd = max(0.0, 2 * zeta * wn * plant.mass - plant.friction)
            duration = max(_duration(plant, wn, zeta, d) for *_, d in cases)
            runs = evaluate(plant, kp, kd, cases, duration)
            tried += 1
            overshoot = max(r.metrics["overshoot_pct"] for _, r in runs)
            settles = [r.metrics["settling_time_s"] for _, r in runs]
            worst_settle = None if any(s is None for s in settles) else max(settles)
            entry = (kp, kd, wn, zeta, overshoot, worst_settle, runs)
            if fallback is None or overshoot < fallback[4]:
                fallback = entry
            if worst_settle is not None and overshoot <= max_overshoot_pct:
                if best is None or worst_settle < best[5]:
                    best = entry
    ok = best is not None
    kp, kd, wn, zeta, overshoot, settle, runs = best or fallback
    return Tuning(ok, kp, 0.0, kd, wn, zeta, overshoot, settle,
                  [(label, r.metrics) for label, r in runs], tried)


def describe(t: Tuning, plant: Plant, max_overshoot_pct: float) -> str:
    lines = []
    if t.ok:
        lines.append(f"ได้ค่าเริ่มต้น (ลอง {t.tried} ชุด): kp = {t.kp:.4g}  ki = 0  kd = {t.kd:.4g}")
    else:
        lines.append(f"ไม่มีชุดไหนผ่านสเปกในทุกกรณี (ลอง {t.tried} ชุด) ชุดที่เกินเป้าน้อยที่สุดคือ "
                     f"kp = {t.kp:.4g} kd = {t.kd:.4g}")
        lines.append("ลอง: เพิ่มแรงมอเตอร์ ลดระยะเคลื่อนที่ต่อครั้ง ผ่อนสเปกการเกินเป้า หรือวัดค่าให้แม่นขึ้น (ลด uncertainty)")
    lines.append(f"(wn = {t.wn:.3g} rad/s, zeta = {t.zeta:g}) สเปก: เกินเป้าไม่เกิน {max_overshoot_pct:g}% ในทุกกรณี")
    lines.append("")
    lines.append(f"{'กรณี':<42} {'เกินเป้า':>9} {'นิ่งที่':>9} {'แรงสูงสุด':>10}")
    for label, m in t.cases:
        settle = "ไม่นิ่ง" if m["settling_time_s"] is None else f"{m['settling_time_s']:.2f} s"
        lines.append(f"{label:<42} {m['overshoot_pct']:>8.2f}% {settle:>9} {m['peak_force_n']:>8.3g} N")
    lines += [
        "",
        "นำไปใช้กับของจริง:",
        "1. ค่านี้มีหน่วยเป็นแรงต่อระยะ ถ้าตัวขับรับคำสั่งเป็นกระแสหรือ PWM ต้องแปลงด้วยค่าคงที่ของมอเตอร์ก่อน",
        "2. เริ่มที่ราว 50% ของ kp และ kd แล้วค่อยเพิ่ม ดูการแกว่งทุกครั้ง มีมือวางที่ปุ่มหยุดฉุกเฉิน",
        "3. ถ้าแกนมีภาระคงที่ (เช่น แกนตั้งรับแรงโน้มถ่วง) จะค้างห่างเป้า ให้เพิ่ม ki ทีละน้อยพร้อม anti-windup",
        "4. ค่ามวลและแรงเสียดทานควรวัดจากเครื่องจริง (system identification) ไม่ใช่เดา",
    ]
    return "\n".join(lines)


def write_chart(path: str, plant: Plant, t: Tuning, uncertainty: float) -> None:
    cases = cases_for(plant, uncertainty)
    duration = max(_duration(plant, t.wn, t.zeta, d) for *_, d in cases)
    runs = evaluate(plant, t.kp, t.kd, cases, duration)
    model.write_svg(path, runs, None, (), f"PID kp={t.kp:.4g} kd={t.kd:.4g} ในทุกกรณีที่ทดสอบ",
                    note="แต่ละเส้นคือค่ามวลและแรงเสียดทานที่ต่างกัน ถ้าทุกเส้นถึงเป้าโดยไม่แกว่ง ค่านี้ทนต่อการวัดคลาด")
