"""คำนวณระยะหยุด: ชั้นป้องกันของกลไกหยุดทันก่อนชนจริงไหม

หลังชั้นป้องกันตรวจพบความผิดปกติ หุ่นยนต์ยังเคลื่อนต่ออีกสองช่วง
1. ช่วงตอบสนอง: ยังวิ่งด้วยความเร็วเดิมระหว่างที่เซนเซอร์อ่าน ตัวตัดสินใจตัด และรีเลย์หรือเบรกเริ่มทำงาน
       d_react = v * t_react
2. ช่วงเบรก: ลดความเร็วด้วยอัตราหน่วงคงที่ a
       d_brake = v^2 / (2a)

ระยะหยุดรวม = d_react + d_brake  ต้องไม่เกินระยะที่มีจริงจากจุดตรวจพบถึงจุดที่ชนแล้วเสียหาย
ใช้กับแกนหมุนได้ด้วยสูตรเดียวกัน (ความเร็วเชิงมุม rad/s, อัตราหน่วง rad/s^2, ระยะเป็น rad)

ข้อจำกัด: สมมติอัตราหน่วงคงที่และความเร็วไม่เพิ่มระหว่างช่วงตอบสนอง (ของจริงอาจเร่งต่อถ้ามอเตอร์ยังมีกำลัง)
ค่าที่ใช้ต้องมาจากการวัดหยุดจริงบนเครื่อง ไม่ใช่จากสเปกในแคตตาล็อกอย่างเดียว
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass
class StopReport:
    speed: float
    react_s: float
    decel: float
    available: float
    safety_factor: float
    react_distance: float
    brake_distance: float
    total: float
    required: float          # ระยะหยุดรวม x ตัวคูณเผื่อ
    margin: float            # ระยะที่มี - ระยะที่ต้องใช้ (ติดลบ = ไม่ผ่าน)
    ok: bool
    max_safe_speed: float    # ความเร็วสูงสุดที่ยังหยุดทันในระยะที่มี (รวมตัวคูณเผื่อแล้ว)
    needed_decel: float | None   # อัตราหน่วงที่ต้องมีเพื่อหยุดทันที่ความเร็วนี้ (None = เบรกแรงแค่ไหนก็ไม่ทัน)

    def as_dict(self) -> dict:
        return asdict(self)


def stopping_distance(speed: float, react_s: float, decel: float) -> tuple[float, float]:
    if speed < 0 or react_s < 0 or decel <= 0:
        raise ValueError("ความเร็วและเวลาตอบสนองต้องไม่ติดลบ และอัตราหน่วงต้องมากกว่า 0")
    return speed * react_s, speed * speed / (2 * decel)


def max_speed_for(distance: float, react_s: float, decel: float) -> float:
    """ความเร็วสูงสุดที่ v*t + v^2/(2a) <= distance (แก้สมการกำลังสอง)"""
    if distance <= 0:
        return 0.0
    return decel * (-react_s + math.sqrt(react_s * react_s + 2 * distance / decel))


def check(speed: float, react_s: float, decel: float, available: float, safety_factor: float = 1.5) -> StopReport:
    if available < 0 or safety_factor < 1:
        raise ValueError("ระยะที่มีต้องไม่ติดลบ และตัวคูณเผื่อต้องไม่น้อยกว่า 1")
    react_d, brake_d = stopping_distance(speed, react_s, decel)
    total = react_d + brake_d
    required = total * safety_factor
    budget = available / safety_factor
    room = budget - speed * react_s
    needed = speed * speed / (2 * room) if room > 0 else None
    return StopReport(speed, react_s, decel, available, safety_factor, react_d, brake_d, total, required,
                      available - required, required <= available, max_speed_for(budget, react_s, decel), needed)


def describe(r: StopReport, unit: str = "m") -> str:
    v = f"{unit}/s"
    lines = [
        f"ความเร็วตอนตรวจพบ        {r.speed:g} {v}",
        f"ช่วงตอบสนอง {r.react_s * 1000:g} ms        วิ่งต่อ {r.react_distance:.3f} {unit}",
        f"ช่วงเบรก (หน่วง {r.decel:g} {unit}/s²)  วิ่งต่อ {r.brake_distance:.3f} {unit}",
        f"ระยะหยุดรวม               {r.total:.3f} {unit}",
        f"ต้องการ (x{r.safety_factor:g} เผื่อ)        {r.required:.3f} {unit}",
        f"ระยะที่มีถึงจุดชน          {r.available:.3f} {unit}",
        "",
    ]
    if r.ok:
        lines.append(f"ผ่าน: เหลือระยะเผื่อ {r.margin:.3f} {unit}")
    else:
        lines.append(f"ไม่ผ่าน: ขาดอีก {-r.margin:.3f} {unit}")
    lines.append(f"ความเร็วสูงสุดที่ยังหยุดทัน: {r.max_safe_speed:.3f} {v}")
    if r.needed_decel is None:
        lines.append("ที่ความเร็วนี้ ช่วงตอบสนองอย่างเดียวก็กินระยะหมดแล้ว ต้องลดเวลาตอบสนองหรือความเร็ว")
    elif not r.ok:
        lines.append(f"หรือต้องเบรกให้หน่วงอย่างน้อย {r.needed_decel:.3f} {unit}/s²")
    if not r.ok:
        lines.append("ทางแก้ที่ได้ผลที่สุดมักเป็นการจำกัดความเร็ว เพราะระยะเบรกโตตามความเร็วยกกำลังสอง")
    return "\n".join(lines)
